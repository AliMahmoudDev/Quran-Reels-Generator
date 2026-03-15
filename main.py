import re
import sys
import io
import os
import uuid
import shutil
import threading
import time
import datetime
import logging
import traceback
import gc
import random
import requests
import json
import sqlite3
import zipfile
from functools import lru_cache  # ✅ Added for caching
from flask import Flask, request, jsonify, send_file, g
from flask_cors import CORS
from contextlib import contextmanager

# Media Processing Imports
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import PIL.Image

# Patch for older PIL versions if needed
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

from moviepy.editor import (
    ImageClip, VideoFileClip, AudioFileClip, 
    CompositeVideoClip, ColorClip, concatenate_videoclips
)
from moviepy.config import change_settings
from proglog import ProgressBarLogger
from pydub import AudioSegment
from deep_translator import GoogleTranslator

# ==========================================
# ⚙️ Configuration & Setup
# ==========================================

STUDIO_DRY_FILTER = (
    "highpass=f=60, "
    "equalizer=f=200:width_type=h:width=200:g=3, "
    "equalizer=f=8000:width_type=h:width=1000:g=2, "
    "acompressor=threshold=-21dB:ratio=4:attack=200:release=1000, "
    "extrastereo=m=1.3, "
    "loudnorm=I=-16:TP=-1.5:LRA=11"
)


def app_dir():
    if getattr(sys, "frozen", False): return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

EXEC_DIR = app_dir()
BUNDLE_DIR = EXEC_DIR 

PEXELS_API_KEYS =[
    "AmAgE0J5AuBbsvR6dmG7qQLIc5uYZvDim2Vx250F5QoHNKnGdCofFerx",
    "Fv0qzUGYwbGr6yHsauaXuNKiNR9L7OE7VLr5Wq6SngcLjavmkCEAskb2",
    "1NK8BaBXGsXm4Uxzcesxm0Jxh2yCILOwqqsj4GiM57dXcb7b8bbDYyOu",
    "C9KJNtJET2wAnmD42Gbu0OolTlmhoT02CX7fyst3kKEvnjRRWLiAqQ9t" 
]

LOCAL_BGS_DIR = os.path.join(BUNDLE_DIR, "local_bgs")
os.makedirs(LOCAL_BGS_DIR, exist_ok=True)

FFMPEG_EXE = "ffmpeg"
os.environ["FFMPEG_BINARY"] = FFMPEG_EXE

try:
    change_settings({"IMAGEMAGICK_BINARY": os.getenv("IMAGEMAGICK_BINARY", "convert")})
except:
    pass

AudioSegment.converter = FFMPEG_EXE
AudioSegment.ffmpeg = FFMPEG_EXE

# Asset Paths
FONT_DIR = os.path.join(EXEC_DIR, "fonts")
FONT_PATH_ARABIC = os.path.join(FONT_DIR, "Arabic.ttf") 
FONT_PATH_ENGLISH = os.path.join(FONT_DIR, "English.otf")
VISION_DIR = os.path.join(BUNDLE_DIR, "vision")
UI_PATH = os.path.join(BUNDLE_DIR, "UI.html")

# Master Temp Directory
BASE_TEMP_DIR = os.path.join(EXEC_DIR, "temp_workspaces")
OUTPUTS_DIR = os.path.join(EXEC_DIR, "outputs")
os.makedirs(BASE_TEMP_DIR, exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)
os.makedirs(VISION_DIR, exist_ok=True)

# ==========================================
# 🗄️ Database Setup (SQLite for Persistence)
# ==========================================
DB_PATH = os.path.join(EXEC_DIR, "quran_jobs.db")

def get_db():
    """Get database connection for current request"""
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(exception):
    """Close database connection at end of request"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Initialize database tables"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Jobs table - for persistence across restarts
    c.execute('''CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        status TEXT NOT NULL DEFAULT 'pending',
        percent INTEGER DEFAULT 0,
        eta TEXT DEFAULT '--:--',
        output_path TEXT,
        error TEXT,
        should_stop INTEGER DEFAULT 0,
        created_at REAL,
        completed_at REAL,
        config_json TEXT,
        workspace TEXT
    )''')
    
    # History table - for user download history
    c.execute('''CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT,
        title TEXT,
        reciter TEXT,
        surah INTEGER,
        start_ayah INTEGER,
        end_ayah INTEGER,
        quality TEXT,
        fps TEXT,
        download_filename TEXT,
        created_at REAL,
        FOREIGN KEY (job_id) REFERENCES jobs(id)
    )''')
    
    # Batch jobs table - for batch export
    c.execute('''CREATE TABLE IF NOT EXISTS batch_jobs (
        id TEXT PRIMARY KEY,
        status TEXT NOT NULL DEFAULT 'pending',
        total_jobs INTEGER DEFAULT 0,
        completed_jobs INTEGER DEFAULT 0,
        failed_jobs INTEGER DEFAULT 0,
        current_job_id TEXT,
        current_job_index INTEGER DEFAULT 0,
        config_json TEXT,
        created_at REAL,
        started_at REAL,
        completed_at REAL
    )''')
    
    # Batch items table - individual jobs in a batch
    c.execute('''CREATE TABLE IF NOT EXISTS batch_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id TEXT,
        job_id TEXT,
        position INTEGER,
        surah INTEGER,
        start_ayah INTEGER,
        end_ayah INTEGER,
        status TEXT DEFAULT 'pending',
        output_path TEXT,
        error TEXT,
        created_at REAL,
        FOREIGN KEY (batch_id) REFERENCES batch_jobs(id),
        FOREIGN KEY (job_id) REFERENCES jobs(id)
    )''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully!")

def db_create_job(job_id, workspace, config=None):
    """Create a new job in database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO jobs (id, status, percent, created_at, workspace, config_json)
                VALUES (?, ?, ?, ?, ?, ?)''', 
              (job_id, 'pending', 0, time.time(), workspace, json.dumps(config) if config else None))
    conn.commit()
    conn.close()

def db_update_job(job_id, **kwargs):
    """Update job in database"""
    if not kwargs:
        return
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    set_clause = ', '.join([f"{k} = ?" for k in kwargs.keys()])
    values = list(kwargs.values()) + [job_id]
    
    c.execute(f"UPDATE jobs SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()

def db_get_job(job_id):
    """Get job from database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    row = c.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

def db_get_all_jobs(status=None, limit=50):
    """Get all jobs, optionally filtered by status"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    if status:
        c.execute("SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?", (status, limit))
    else:
        c.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))
    
    rows = c.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def db_get_pending_jobs():
    """Get all pending/processing jobs for recovery"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM jobs WHERE status IN ('pending', 'processing')")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def db_add_history(job_id, title, reciter, surah, start_ayah, end_ayah, quality, fps, filename):
    """Add entry to history"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO history (job_id, title, reciter, surah, start_ayah, end_ayah, quality, fps, download_filename, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (job_id, title, reciter, surah, start_ayah, end_ayah, quality, fps, filename, time.time()))
    conn.commit()
    conn.close()

def db_get_history(limit=20):
    """Get history entries"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''SELECT h.*, j.output_path, j.status 
                 FROM history h 
                 LEFT JOIN jobs j ON h.job_id = j.id 
                 ORDER BY h.created_at DESC LIMIT ?''', (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def db_cleanup_old_jobs(hours=24):
    """Clean up jobs older than specified hours"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    threshold = time.time() - (hours * 3600)
    
    # Get old completed jobs
    c.execute("SELECT id, workspace, output_path FROM jobs WHERE created_at < ? AND status IN ('complete', 'error', 'cancelled')", (threshold,))
    old_jobs = c.fetchall()
    
    # Clean up files
    for job in old_jobs:
        # حذف مجلد العمل المؤقت
        if job['workspace'] and os.path.exists(job['workspace']):
            try:
                shutil.rmtree(job['workspace'], ignore_errors=True)
            except:
                pass
        
        # حذف ملف الفيديو النهائي من outputs
        if job['output_path'] and os.path.exists(job['output_path']):
            try:
                os.remove(job['output_path'])
            except:
                pass
    
    # Delete from database
    c.execute("DELETE FROM jobs WHERE created_at < ? AND status IN ('complete', 'error', 'cancelled')", (threshold,))
    c.execute("DELETE FROM history WHERE created_at < ?", (threshold,))
    
    conn.commit()
    conn.close()
    print(f"🧹 Cleaned up {len(old_jobs)} old jobs and their video files")

# ==========================================
# 📦 Batch Job Management Functions
# ==========================================

def db_create_batch(batch_id, total_jobs, config):
    """Create a new batch job in database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO batch_jobs (id, status, total_jobs, completed_jobs, failed_jobs, config_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)''', 
              (batch_id, 'pending', total_jobs, 0, 0, json.dumps(config), time.time()))
    conn.commit()
    conn.close()

def db_update_batch(batch_id, **kwargs):
    """Update batch job in database"""
    if not kwargs:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    set_clause = ', '.join([f"{k} = ?" for k in kwargs.keys()])
    values = list(kwargs.values()) + [batch_id]
    c.execute(f"UPDATE batch_jobs SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()

def db_get_batch(batch_id):
    """Get batch job from database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM batch_jobs WHERE id = ?", (batch_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def db_add_batch_item(batch_id, job_id, position, surah, start_ayah, end_ayah):
    """Add an item to batch"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO batch_items (batch_id, job_id, position, surah, start_ayah, end_ayah, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (batch_id, job_id, position, surah, start_ayah, end_ayah, 'pending', time.time()))
    conn.commit()
    conn.close()

def db_update_batch_item(batch_id, job_id, **kwargs):
    """Update batch item"""
    if not kwargs:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    set_clause = ', '.join([f"{k} = ?" for k in kwargs.keys()])
    values = list(kwargs.values()) + [batch_id, job_id]
    c.execute(f"UPDATE batch_items SET {set_clause} WHERE batch_id = ? AND job_id = ?", values)
    conn.commit()
    conn.close()

def db_get_batch_items(batch_id):
    """Get all items in a batch"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM batch_items WHERE batch_id = ? ORDER BY position", (batch_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def db_get_pending_batches():
    """Get all pending/running batches"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM batch_jobs WHERE status IN ('pending', 'running')")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# Data Constants
VERSE_COUNTS = {1: 7, 2: 286, 3: 200, 4: 176, 5: 120, 6: 165, 7: 206, 8: 75, 9: 129, 10: 109, 11: 123, 12: 111, 13: 43, 14: 52, 15: 99, 16: 128, 17: 111, 18: 110, 19: 98, 20: 135, 21: 112, 22: 78, 23: 118, 24: 64, 25: 77, 26: 227, 27: 93, 28: 88, 29: 69, 30: 60, 31: 34, 32: 30, 33: 73, 34: 54, 35: 45, 36: 83, 37: 182, 38: 88, 39: 75, 40: 85, 41: 54, 42: 53, 43: 89, 44: 59, 45: 37, 46: 35, 47: 38, 48: 29, 49: 18, 50: 45, 51: 60, 52: 49, 53: 62, 54: 55, 55: 78, 56: 96, 57: 29, 58: 22, 59: 24, 60: 13, 61: 14, 62: 11, 63: 11, 64: 18, 65: 12, 66: 12, 67: 30, 68: 52, 69: 52, 70: 44, 71: 28, 72: 28, 73: 20, 74: 56, 75: 40, 76: 31, 77: 50, 78: 40, 79: 46, 80: 42, 81: 29, 82: 19, 83: 36, 84: 25, 85: 22, 86: 17, 87: 19, 88: 26, 89: 30, 90: 20, 91: 15, 92: 21, 93: 11, 94: 8, 95: 8, 96: 19, 97: 5, 98: 8, 99: 8, 100: 11, 101: 11, 102: 8, 103: 3, 104: 9, 105: 5, 106: 4, 107: 7, 108: 3, 109: 6, 110: 3, 111: 5, 112: 4, 113: 5, 114: 6}
SURAH_NAMES =['الفاتحة', 'البقرة', 'آل عمران', 'النساء', 'المائدة', 'الأنعام', 'الأعراف', 'الأنفال', 'التوبة', 'يونس', 'هود', 'يوسف', 'الرعد', 'إبراهيم', 'الحجر', 'النحل', 'الإسراء', 'الكهف', 'مريم', 'طه', 'الأنبياء', 'الحج', 'المؤمنون', 'النور', 'الفرقان', 'الشعراء', 'النمل', 'القصص', 'العنكبوت', 'الروم', 'لقمان', 'السجدة', 'الأحزاب', 'سبأ', 'فاطر', 'يس', 'الصافات', 'ص', 'الزمر', 'غافر', 'فصلت', 'الشورى', 'الزخرف', 'الدخان', 'الجاثية', 'الأحقاف', 'محمد', 'الفتح', 'الحجرات', 'ق', 'الذاريات', 'الطور', 'النجم', 'القمر', 'الرحمن', 'الواقعة', 'الحديد', 'المجادلة', 'الحشر', 'الممتحنة', 'الصف', 'الجمعة', 'المنافقون', 'التغابن', 'الطلاق', 'التحريم', 'الملك', 'القلم', 'الحاقة', 'المعارج', 'نوح', 'الجن', 'المزمل', 'المدثر', 'القيامة', 'الإنسان', 'المرسلات', 'النبأ', 'النازعات', 'عبس', 'التكوير', 'الانفطار', 'المطففين', 'الانشقاق', 'البروج', 'الطارق', 'الأعلى', 'الغاشية', 'الفجر', 'البلد', 'الشمس', 'الليل', 'الضحى', 'الشرح', 'التين', 'العلق', 'القدر', 'البينة', 'الزلزلة', 'العاديات', 'القارعة', 'التكاثر', 'العصر', 'الهمزة', 'الفيل', 'قريش', 'الماعون', 'الكوثر', 'الكافرون', 'النصر', 'المسد', 'الإخلاص', 'الفلق', 'الناس']

# 🚀 Reciters Config
NEW_RECITERS_CONFIG = {
    'احمد النفيس': (259, "https://server16.mp3quran.net/nufais/Rewayat-Hafs-A-n-Assem/"),
    'وديع اليماني': (219, "https://server6.mp3quran.net/wdee3/"),
    'بندر بليلة': (217, "https://server6.mp3quran.net/balilah/"),
    'ادريس أبكر': (12, "https://server6.mp3quran.net/abkr/"),
    'منصور السالمي': (245, "https://server14.mp3quran.net/mansor/"),
    'رعد الكردي': (221, "https://server6.mp3quran.net/kurdi/"),
}

OLD_RECITERS_MAP = {
    'أبو بكر الشاطري':'Abu_Bakr_Ash-Shaatree_128kbps',
    'ياسر الدوسري':'Yasser_Ad-Dussary_128kbps', 
    ' عبدالرحمن السديس': 'Abdurrahmaan_As-Sudais_64kbps', 
    ' ماهر المعيقلي': 'Maher_AlMuaiqly_64kbps', 
    ' سعود الشريم': 'Saood_ash-Shuraym_64kbps', 
    ' مشاري العفاسي': 'Alafasy_64kbps',
    'ناصر القطامي':'Nasser_Alqatami_128kbps', 
}

RECITERS_MAP = {**{k: k for k in NEW_RECITERS_CONFIG.keys()}, **OLD_RECITERS_MAP}

app = Flask(__name__, static_folder=EXEC_DIR)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Register the teardown function
app.teardown_appcontext(close_db)

# ==========================================
# 🧠 Job Management (RAM + SQLite for Persistence)
# ==========================================
JOBS = {}  # RAM cache for fast access
JOBS_LOCK = threading.Lock()

# ==========================================
def create_job(config=None):
    """Create a new job - stores in RAM and SQLite"""
    job_id = str(uuid.uuid4())
    job_dir = os.path.join(BASE_TEMP_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    
    # Store in RAM for fast access
    with JOBS_LOCK:
        JOBS[job_id] = {
            'id': job_id, 
            'percent': 0, 
            'status': 'pending', 
            'eta': '--:--', 
            'is_running': True, 
            'is_complete': False, 
            'output_path': None, 
            'error': None, 
            'should_stop': False, 
            'created_at': time.time(), 
            'workspace': job_dir
        }
    
    # Store in SQLite for persistence
    db_create_job(job_id, job_dir, config)
    
    return job_id

def update_job_status(job_id, percent, status, eta=None):
    """Update job status - RAM + SQLite"""
    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id]['percent'] = percent
            JOBS[job_id]['status'] = status
            if eta: JOBS[job_id]['eta'] = eta
    
    # Update in SQLite ( throttled - every 5% or on completion)
    if percent % 5 == 0 or percent >= 100 or 'complete' in status.lower() or 'error' in status.lower():
        db_data = {'percent': percent, 'status': status}
        if eta:
            db_data['eta'] = eta
        db_update_job(job_id, **db_data)

def get_job(job_id):
    """Get job - try RAM first, then SQLite"""
    with JOBS_LOCK:
        if job_id in JOBS:
            return JOBS[job_id]
    
    # Not in RAM, try SQLite
    db_job = db_get_job(job_id)
    if db_job:
        # Reconstruct job dict for compatibility
        return {
            'id': db_job['id'],
            'percent': db_job['percent'],
            'status': db_job['status'],
            'eta': db_job['eta'],
            'is_running': db_job['status'] in ('pending', 'processing'),
            'is_complete': db_job['status'] == 'complete',
            'output_path': db_job['output_path'],
            'error': db_job['error'],
            'should_stop': bool(db_job['should_stop']),
            'created_at': db_job['created_at'],
            'workspace': db_job['workspace']
        }
    return None

def check_stop(job_id):
    """Check if job should stop"""
    job = get_job(job_id)
    if not job:
        # Job not found in RAM or SQLite - might have been cleaned up
        # Don't raise error, just log and continue (job might have been completed)
        print(f"[WARNING] Job {job_id} not found in check_stop - assuming completed or cleaned up")
        return
    if job.get('should_stop', False):
        raise Exception("Stopped by user")

def cleanup_job(job_id):
    """Remove job from RAM (keep in SQLite for history)"""
    with JOBS_LOCK:
        job = JOBS.pop(job_id, None)
    # Don't delete files - keep them for download
    # Files will be cleaned up by background_cleanup after 24h

class ScopedQuranLogger(ProgressBarLogger):
    def __init__(self, job_id):
        super().__init__()
        self.job_id = job_id
        self.start_time = None

    def bars_callback(self, bar, attr, value, old_value=None):
        if bar == 't':
            check_stop(self.job_id)
            total = self.bars[bar]['total']
            if total > 0:
                percent = int((value / total) * 100)
                if self.start_time is None: self.start_time = time.time()
                elapsed = time.time() - self.start_time
                rem_str = "00:00"
                if elapsed > 0 and value > 0:
                    rate = value / elapsed
                    remaining = (total - value) / rate
                    rem_str = str(datetime.timedelta(seconds=int(remaining)))[2:] if remaining > 0 else "00:00"
                update_job_status(self.job_id, percent, f"جاري التصدير... {percent}%", eta=rem_str)

# ==========================================
# 🛠️ Helper Functions & Optimization
# ==========================================

@lru_cache(maxsize=10)
def get_cached_font(font_path, size):
    try: return ImageFont.truetype(font_path, size)
    except: return ImageFont.load_default()

def detect_silence(sound, thresh):
    t = 0
    while t < len(sound) and sound[t:t+10].dBFS < thresh: t += 10
    return t

def smart_download(url, dest_path, job_id):
    check_stop(job_id)
    try:
        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(dest_path, 'wb') as f:
                counter = 0
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk: 
                        f.write(chunk)
                        counter += 1
                        if counter % 100 == 0: 
                            check_stop(job_id)
        # Verify file was downloaded
        if not os.path.exists(dest_path) or os.path.getsize(dest_path) == 0:
            raise Exception(f"Downloaded file is empty or missing: {dest_path}")
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to download {url}: {e}")
        raise Exception(f"Failed to download: {url}")

def detect_leading_silence(sound, silence_threshold=-50.0, chunk_size=10):
    trim_ms = 0
    assert chunk_size > 0
    while trim_ms < len(sound) and sound[trim_ms:trim_ms+chunk_size].dBFS < silence_threshold:
        trim_ms += chunk_size
    return trim_ms

def process_mp3quran_audio(reciter_name, surah, ayah, idx, workspace_dir, job_id):
    reciter_id, server_url = NEW_RECITERS_CONFIG[reciter_name]
    cache_dir = os.path.join(EXEC_DIR, "cache_mp3quran", str(reciter_id))
    os.makedirs(cache_dir, exist_ok=True)
    full_audio_path = os.path.join(cache_dir, f"{surah:03d}.mp3")
    timings_path = os.path.join(cache_dir, f"{surah:03d}.json")

    if not os.path.exists(full_audio_path) or not os.path.exists(timings_path):
        smart_download(f"{server_url}{surah:03d}.mp3", full_audio_path, job_id)
        check_stop(job_id)
        t_data = requests.get(f"https://mp3quran.net/api/v3/ayat_timing?surah={surah}&read={reciter_id}").json()
        timings = {item['ayah']: {'start': item['start_time'], 'end': item['end_time']} for item in t_data}
        with open(timings_path, 'w') as f: json.dump(timings, f)

    with open(timings_path, 'r') as f:
        t = json.load(f)[str(ayah)]
    
    check_stop(job_id)
    seg = AudioSegment.from_file(full_audio_path)[t['start']:t['end']]
    silence_thresh = seg.dBFS - 25 # جعلنا المقص ألطف

    start_trim = detect_leading_silence(seg, silence_threshold=silence_thresh)
    end_trim = detect_leading_silence(seg.reverse(), silence_threshold=silence_thresh)
    duration = len(seg)
    
    # 🚀 التعديل السحري: إضافة مقص إجباري في البداية لقتل "التسريب"
    aggressive_start_trim = max(0,start_trim- 30)  # قص 150 ملي ثانية إضافية من أول الآية
    
    # ترك مساحة أمان في النهاية للحفاظ على صدى الشيخ
    # 🧪 تجربة البتر: هنجبره يقص 300 ملي ثانية زيادة من آخر الآية عشان نكتشف مصدر الصوت!
    experiment_cut = 500
    
    # لاحظ خلينا الـ end_trim يزيد عليه 300 ملي ثانية عشان ياكل من آخر الصوت
    safe_end_trim = max(0,end_trim-experiment_cut )
    
    if duration - start_trim - safe_end_trim > 200: 
        seg = seg[start_trim:duration-safe_end_trim].fade_out(50)
        
    out = os.path.join(workspace_dir, f'part{idx}.mp3')
    seg.export(out, format="mp3")
    return out

def download_audio(reciter_key, surah, ayah, idx, workspace_dir, job_id):
    if reciter_key in NEW_RECITERS_CONFIG:
        return process_mp3quran_audio(reciter_key, surah, ayah, idx, workspace_dir, job_id)
    
    url = f'https://everyayah.com/data/{reciter_key}/{surah:03d}{ayah:03d}.mp3'
    out = os.path.join(workspace_dir, f'part{idx}.mp3')
    smart_download(url, out, job_id)
    
    snd = AudioSegment.from_file(out)
    start, end = detect_silence(snd, snd.dBFS-20), detect_silence(snd.reverse(), snd.dBFS-20)
    trimmed = snd[max(0, start-30):len(snd)-max(0, end-30)]
    (AudioSegment.silent(duration=50) + trimmed.fade_in(20).fade_out(20)).export(out, format='mp3')
    return out

def get_text(surah, ayah):
    try:
        t = requests.get(f'https://api.alquran.cloud/v1/ayah/{surah}:{ayah}/quran-simple').json()['data']['text']
        if surah not in [1, 9] and ayah == 1:
            t = re.sub(r'^بِسْمِ [^ ]+ [^ ]+[^ ]+', '', t).strip()
            t = t.replace("بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ", "").strip()
        return t
    except: return "Text Error"

def get_en_text(surah, ayah):
    try: return requests.get(f'http://api.alquran.cloud/v1/ayah/{surah}:{ayah}/en.sahih').json()['data']['text']
    except: return ""

# 🆕 دالة تقطيع النصوص للريلز (5 كلمات كحد أقصى للسطر)
def split_into_chunks(text, words_per_chunk=5):
    words = text.split()
    if not words: return []
    return [" ".join(words[i:i + words_per_chunk]) for i in range(0, len(words), words_per_chunk)]

def create_vignette_mask(w, h):
    Y, X = np.ogrid[:h, :w]
    mask = np.clip((np.sqrt((X - w/2)**2 + (Y - h/2)**2) / np.sqrt((w/2)**2 + (h/2)**2)) * 1.16, 0, 1) ** 3 
    mask_img = np.zeros((h, w, 4), dtype=np.uint8)
    mask_img[:, :, 3] = (mask * 255).astype(np.uint8)
    return ImageClip(mask_img, ismask=False)

# ==========================================
# 🎨 Visual Elements
# ==========================================

def create_text_clip(text, duration, target_w, scale_factor=1.0, glow=False, style=None):
    if style is None: style = {}
    
    color = style.get('arColor', '#ffffff')
    size_mult = float(style.get('arSize', '1.0'))
    stroke_c = style.get('arOutC', '#000000')
    stroke_w = int(style.get('arOutW', '4'))
    has_shadow = style.get('arShadow', False)
    shadow_c = style.get('arShadowC', '#000000')

    # الخط كبير لأنه سطر واحد
    final_fs = int(55 * scale_factor * size_mult)
    font = get_cached_font(FONT_PATH_ARABIC, final_fs)
    
    img = Image.new('RGBA', (target_w, int(180 * scale_factor * size_mult)), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    w = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_w)[2]
    x = (target_w - w) // 2
    curr_y = 20
        
    if has_shadow:
        draw.text((x+4, curr_y+4), text, font=font, fill=shadow_c)
    if glow: 
        draw.text((x, curr_y), text, font=font, fill=(255,255,255,40), stroke_width=stroke_w+4, stroke_fill=(255,255,255,20))
    
    draw.text((x, curr_y), text, font=font, fill=color, stroke_width=stroke_w, stroke_fill=stroke_c)
    
    return ImageClip(np.array(img)).set_duration(duration).crossfadein(0.35).crossfadeout(0.35)

def create_english_clip(text, duration, target_w, scale_factor=1.0, glow=False, style=None):
    if style is None: style = {}
    
    color = style.get('enColor', '#FFD700')
    size_mult = float(style.get('enSize', '1.0'))
    stroke_c = style.get('enOutC', '#000000')
    stroke_w = int(style.get('enOutW', '3'))
    has_shadow = style.get('enShadow', False)
    shadow_c = style.get('enShadowC', '#000000')

    final_fs = int(32 * scale_factor * size_mult)
    font = get_cached_font(FONT_PATH_ENGLISH, final_fs)
    
    h = int(150 * size_mult)
    img = Image.new('RGBA', (target_w, h), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    
    y_pos = 20
    if has_shadow:
        draw.text((target_w/2 + 2, y_pos + 2), text, font=font, fill=shadow_c, align='center', anchor="ma")

    draw.text((target_w/2, y_pos), text, font=font, fill=color, align='center', anchor="ma", stroke_width=stroke_w, stroke_fill=stroke_c)
    
    return ImageClip(np.array(img)).set_duration(duration).crossfadein(0.35).crossfadeout(0.35)

def fetch_video_pool(user_key, custom_query, count=1, job_id=None):
    pool =[]
    active_key = user_key if user_key and len(user_key) > 10 else random.choice(PEXELS_API_KEYS) if PEXELS_API_KEYS else ""
    
    SAFE_WHITELIST =[
        'nature', 'sky', 'sea', 'ocean', 'water', 'rain', 'cloud', 'mountain',
        'forest', 'tree', 'desert', 'sand', 'star', 'galaxy', 'space', 'moon',
        'sun', 'sunset', 'sunrise', 'mosque', 'islam', 'kaaba', 'makkah',
        'snow', 'winter', 'landscape', 'river', 'fog', 'mist', 'earth', 'bird'
    ]

    safe_topics =['sky clouds timelapse', 'galaxy stars space', 'ocean waves slow motion', 'forest trees drone', 'desert sand dunes', 'waterfall nature', 'mountains fog', 'mosque architecture', 'islamic pattern']

    if custom_query and len(custom_query) > 2:
        try: 
            q_trans = GoogleTranslator(source='auto', target='en').translate(custom_query.strip()).lower()
            is_safe = any(safe_word in q_trans for safe_word in SAFE_WHITELIST)
            q = f"{q_trans} landscape scenery atmospheric no people" if is_safe else f"{random.choice(safe_topics)} no people"
        except: 
            q = f"{random.choice(safe_topics)} no people"
    else:
        q = f"{random.choice(safe_topics)} no people"

    if active_key:
        try:
            check_stop(job_id)
            url = f"https://api.pexels.com/videos/search?query={q}&per_page={count+5}&page={random.randint(1, 10)}&orientation=portrait"
            r = requests.get(url, headers={'Authorization': active_key}, timeout=10)
            if r.status_code == 200:
                vids = r.json().get('videos',[])
                random.shuffle(vids)
                for vid in vids:
                    if len(pool) >= count: break
                    check_stop(job_id)
                    f = next((vf for vf in vid['video_files'] if vf['width'] <= 1080 and vf['height'] > vf['width']), None)
                    if not f and vid['video_files']: f = vid['video_files'][0]
                    if f:
                        path = os.path.join(VISION_DIR, f"bg_{vid['id']}.mp4")
                        if not os.path.exists(path): smart_download(f['link'], path, job_id)
                        pool.append(path)
        except: pass

    if not pool:
        try:
            local_files =[os.path.join(LOCAL_BGS_DIR, f) for f in os.listdir(LOCAL_BGS_DIR) if f.lower().endswith(('.mp4', '.mov', '.mkv'))]
            if local_files: pool = random.choices(local_files, k=count)
        except: pass
            
    return pool

# ==========================================
# ⚡ Optimized Video Builder (Segmented / Chunked)
# ==========================================
def build_video_task(job_id, user_pexels_key, reciter_id, surah, start, end, quality, bg_query, fps, dynamic_bg, use_glow, use_vignette, style):
    job = get_job(job_id)
    if not job:
        raise Exception(f"Job {job_id} not found - cannot process video")
    
    workspace = job['workspace']
    if not workspace:
        raise Exception(f"Job {job_id} has no workspace")
    
    target_w, target_h = (1080, 1920) if quality == '1080' else (720, 1280)
    scale = 1.0 if quality == '1080' else 0.67
    last = min(end if end else start+9, VERSE_COUNTS.get(surah, 286))
    total_ayahs = (last - start) + 1
    
    # مصفوفات لتخزين الملفات المفتوحة لإغلاقها في الـ finally لعدم تسريب الذاكرة
    audio_clips_to_close =[]
    video_clips_to_close = []
    final_segments =[]

    try:
        # 1. Fetch Backgrounds
        vpool = fetch_video_pool(user_pexels_key, bg_query, count=total_ayahs if dynamic_bg else 1, job_id=job_id)
        
        # 2. Prepare Base Background
        if not vpool:
            base_bg_clip = ColorClip((target_w, target_h), color=(15, 20, 35))
        else:
            base_bg_clip = VideoFileClip(vpool[0]).resize(height=target_h).crop(width=target_w, height=target_h, x_center=target_w/2, y_center=target_h/2)
            video_clips_to_close.append(base_bg_clip)

        overlays_static =[ColorClip((target_w, target_h), color=(0,0,0)).set_opacity(0.3)]
        if use_vignette:
            overlays_static.append(create_vignette_mask(target_w, target_h))

        current_bg_time = 0.0
        
        # 4. معالجة الآيات 
        for i, ayah in enumerate(range(start, last+1)):
            check_stop(job_id)
            update_job_status(job_id, int((i / total_ayahs) * 80), f'Processing Ayah {ayah}...')

            # تحميل الصوت مع التحقق
            try:
                ap = download_audio(reciter_id, surah, ayah, i, workspace, job_id)
                if not os.path.exists(ap):
                    raise Exception(f"Audio file not found: {ap}")
                full_audioclip = AudioFileClip(ap)
                if full_audioclip.duration <= 0:
                    raise Exception(f"Invalid audio duration: {full_audioclip.duration}")
                audio_clips_to_close.append(full_audioclip)
            except Exception as audio_err:
                print(f"[ERROR] Audio download/processing failed for ayah {ayah}: {audio_err}")
                continue  # Skip this ayah and continue with the next

            full_ar_text = get_text(surah, ayah)
            full_en_text = get_en_text(surah, ayah)
            
            # التحقق من وجود نص عربي
            if not full_ar_text or full_ar_text == "Text Error" or len(full_ar_text.strip()) == 0:
                print(f"[ERROR] Failed to get Arabic text for ayah {ayah}")
                continue  # Skip this ayah
            
            # تقطيع النصوص (العربي والإنجليزي)
            ar_chunks = split_into_chunks(full_ar_text, words_per_chunk=5)
            
            # التحقق من وجود قطع
            if not ar_chunks or len(ar_chunks) == 0:
                print(f"[ERROR] No text chunks created for ayah {ayah}")
                continue  # Skip this ayah
                
            en_words = full_en_text.split()
            avg_en_per_ar = len(en_words) / len(ar_chunks) if len(ar_chunks) > 0 else 0
            
            current_audio_time = 0.0
            
            # فتح فيديو الخلفية مرة واحدة للآية (إذا كان متغيراً) لتقليل استهلاك الرام
            if dynamic_bg and i < len(vpool):
                ayah_bg_clip = VideoFileClip(vpool[i % len(vpool)]).resize(height=target_h).crop(width=target_w, height=target_h, x_center=target_w/2, y_center=target_h/2)
                video_clips_to_close.append(ayah_bg_clip)
                ayah_bg_time = 0.0

            # الدوران على قطع الآية (السطور)
            # الدوران على قطع الآية (السطور)
            for chunk_idx, ar_chunk in enumerate(ar_chunks):
                
                # 1. تحديد وقت النهاية بدقة شديدة
                if chunk_idx == len(ar_chunks) - 1:
                    t_end = full_audioclip.duration # القطعة الأخيرة تاخد كل الباقي
                else:
                    ratio = len(ar_chunk.replace(" ", "")) / max(1, len(full_ar_text.replace(" ", "")))
                    t_end = min(current_audio_time + (ratio * full_audioclip.duration), full_audioclip.duration)

                # حماية من الأوقات الصفرية
                if t_end - current_audio_time <= 0.05: 
                    t_end = min(current_audio_time + 0.1, full_audioclip.duration)

                # 2. قص الصوت أولاً
                chunk_audio = full_audioclip.subclip(current_audio_time, t_end).audio_fadein(0.05).audio_fadeout(0.05)
                
                # 🚀 3. الحل الجذري: نعتمد وقت الصوت الفعلي كأساس لوقت الفيديو!
                actual_duration = chunk_audio.duration
                if actual_duration <= 0: continue
                
                # ج. اقتطاع الترجمة الإنجليزية
                start_en = int(chunk_idx * avg_en_per_ar)
                end_en = int((chunk_idx + 1) * avg_en_per_ar)
                if chunk_idx == len(ar_chunks) - 1:
                    en_chunk = " ".join(en_words[start_en:])
                    display_ar = f"{ar_chunk} ({ayah})" 
                else:
                    en_chunk = " ".join(en_words[start_en:end_en])
                    display_ar = ar_chunk

                # د. إنشاء الكليبات البصرية (نستخدم actual_duration بدل chunk_duration)
                ac = create_text_clip(display_ar, actual_duration, target_w, scale, use_glow, style=style)
                ec = create_english_clip(en_chunk, actual_duration, target_w, scale, use_glow, style=style)

                # هـ. تحديد المواقع
                ar_size_mult = float(style.get('arSize', '1.0'))
                base_y = 0.35 if ar_size_mult <= 1.2 else 0.30
                ar_y_pos = target_h * base_y
                
                ac = ac.set_position(('center', ar_y_pos))
                ec = ec.set_position(('center', ar_y_pos + ac.h + (10 * scale)))

                # و. معالجة الخلفية للقطعة (نستخدم actual_duration)
                if dynamic_bg and i < len(vpool):
                    bg_slice = ayah_bg_clip.loop().subclip(ayah_bg_time, ayah_bg_time + actual_duration)
                    if chunk_idx == 0: bg_slice = bg_slice.fadein(0.5)
                    if chunk_idx == len(ar_chunks) - 1: bg_slice = bg_slice.fadeout(0.5)
                    ayah_bg_time += actual_duration
                else:
                    bg_slice = base_bg_clip.loop().subclip(current_bg_time, current_bg_time + actual_duration)
                    current_bg_time += actual_duration
                
                # ز. تجميع القطعة
                segment_overlays =[o.set_duration(actual_duration) for o in overlays_static]
                full_segment = CompositeVideoClip([bg_slice] + segment_overlays + [ac, ec]).set_audio(chunk_audio)
                final_segments.append(full_segment)

                # تحديث الوقت للقطعة القادمة
                current_audio_time = t_end

        # 5. الدمج والرندر النهائي
        # التحقق من وجود مقاطع للدمج
        if not final_segments or len(final_segments) == 0:
            raise Exception("لم يتم إنشاء أي مقاطع فيديو - قد يكون هناك مشكلة في تحميل الصوت أو النصوص")

        update_job_status(job_id, 85, "Merging All Chunks...")
        final_video = concatenate_videoclips(final_segments, method="compose")
        
        # حفظ الفيديو النهائي في مجلد outputs
        final_output_path = os.path.join(OUTPUTS_DIR, f"{job_id}.mp4")
        temp_mix_path = os.path.join(workspace, f"temp_mix_{job_id}.mp4")
        
        update_job_status(job_id, 90, "Rendering Video (Mixing)...")
        final_video.write_videofile(
            temp_mix_path, 
            fps=fps, 
            codec='libx264', 
            audio_codec='aac', 
            audio_bitrate='192k',
            preset='ultrafast', 
            threads=os.cpu_count() or 4,
            logger=ScopedQuranLogger(job_id)
        )

        # 6. معالجة وتوحيد الصوت (Studio Dry Filter)
        update_job_status(job_id, 98, "Mastering Audio (Dry Studio)...")
        cmd = (
            f'ffmpeg -y -i "{temp_mix_path}" '
            f'-af "{STUDIO_DRY_FILTER}" '
            f'-c:v copy '
            f'-c:a aac -b:a 192k '
            f'"{final_output_path}"'
        )
        
        if os.system(cmd) != 0: 
            # في حال فشل الفلتر لأي سبب، نستخدم النسخة الأصلية
            shutil.move(temp_mix_path, final_output_path)
        else:
            if os.path.exists(temp_mix_path): os.remove(temp_mix_path)

        with JOBS_LOCK: 
            if job_id in JOBS:
                JOBS[job_id].update({'output_path': final_output_path, 'is_complete': True, 'is_running': False, 'percent': 100, 'status': "complete"})
            else:
                # أضف للـ RAM لو مش موجودة
                JOBS[job_id] = {'id': job_id, 'output_path': final_output_path, 'is_complete': True, 'is_running': False, 'percent': 100, 'status': "complete"}
        
        # Update in SQLite and add to history
        db_update_job(job_id, output_path=final_output_path, status='complete', percent=100, completed_at=time.time())
        
        # Get config from DB to add to history
        db_job = db_get_job(job_id)
        if db_job and db_job.get('config_json'):
            try:
                config = json.loads(db_job['config_json'])
                surah = config.get('surah', 1)
                start_ayah = config.get('startAyah', 1)
                end_ayah = config.get('endAyah', start_ayah)
                reciter = config.get('reciter', 'Unknown')
                quality = config.get('quality', '720')
                fps = config.get('fps', '20')
                
                title = f"{SURAH_NAMES[surah-1] if surah <= len(SURAH_NAMES) else 'سورة'} (آية {start_ayah}-{end_ayah})"
                filename = f"Quran_{surah}_{start_ayah}.mp4"
                
                db_add_history(job_id, title, reciter, surah, start_ayah, end_ayah, quality, fps, filename)
            except Exception as e:
                print(f"Error adding to history: {e}")

    except Exception as e:
        msg = str(e)
        traceback.print_exc()
        status = "cancelled" if msg == "Stopped" else "error"
        with JOBS_LOCK: 
            if job_id in JOBS:
                JOBS[job_id].update({'error': msg, 'status': status, 'is_running': False})
            else:
                # أضف للـ RAM لو مش موجودة
                JOBS[job_id] = {'id': job_id, 'error': msg, 'status': status, 'is_running': False, 'percent': 0}
        # Update in SQLite
        db_update_job(job_id, status=status, error=msg)
    
    finally:
        # إغلاق جميع الملفات المفتوحة بحرص شديد
        for ac in audio_clips_to_close:
            try: ac.close()
            except: pass
            
        for vc in video_clips_to_close:
            try: vc.close()
            except: pass
            
        try:
            if 'final_video' in locals(): final_video.close()
            for s in final_segments: s.close()
        except: pass
        gc.collect()
        
        # 🧹 حذف جميع الملفات المؤقتة
        try:
            # حذف مجلد العمل المؤقت بالكامل
            if workspace and os.path.exists(workspace):
                shutil.rmtree(workspace, ignore_errors=True)
                print(f"🧹 Cleaned workspace: {job_id}")
        except Exception as cleanup_err:
            print(f"⚠️ Cleanup error: {cleanup_err}")

@app.route('/')
def ui(): return send_file(UI_PATH) if os.path.exists(UI_PATH) else "API Running"

@app.route('/api/generate', methods=['POST'])
def gen():
    d = request.json
    
    # Create job with config for persistence
    config = {
        'surah': int(d['surah']),
        'startAyah': int(d['startAyah']),
        'endAyah': int(d.get('endAyah', 0)),
        'reciter': d['reciter'],
        'quality': d.get('quality', '720'),
        'fps': d.get('fps', '20'),
        'bgQuery': d.get('bgQuery', ''),
        'dynamicBg': d.get('dynamicBg', False),
        'useGlow': d.get('useGlow', False),
        'useVignette': d.get('useVignette', False),
        'pexelsKey': d.get('pexelsKey', ''),
        'style': d.get('style', {})
    }
    
    job_id = create_job(config)
    style_settings = d.get('style', {}) 
    
    # Update status to processing
    update_job_status(job_id, 0, 'processing')
    
    threading.Thread(
        target=build_video_task, 
        args=(
            job_id, 
            d['pexelsKey'], 
            d['reciter'], 
            int(d['surah']), 
            int(d['startAyah']), 
            int(d.get('endAyah',0)), 
            d.get('quality','720'), 
            d.get('bgQuery',''), 
            int(d.get('fps',20)), 
            d.get('dynamicBg',False), 
            d.get('useGlow',False), 
            d.get('useVignette',False),
            style_settings
        ), 
        daemon=True
    ).start()
    
    return jsonify({'ok': True, 'jobId': job_id})

@app.route('/api/progress')
def prog(): 
    job = get_job(request.args.get('jobId'))
    if job:
        # Add download URL if complete
        if job.get('status') == 'complete' and job.get('output_path'):
            job['download_url'] = f"/api/download?jobId={job['id']}"
    return jsonify(job)

@app.route('/api/download')
def download_result():
    job = get_job(request.args.get('jobId'))
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    output_path = job.get('output_path')
    if not output_path or not os.path.exists(output_path):
        return jsonify({'error': 'File not found'}), 404
    
    # Get filename from history or use default
    filename = f"Quran_video_{request.args.get('jobId')[:8]}.mp4"
    return send_file(output_path, as_attachment=True, download_name=filename)

@app.route('/api/cancel', methods=['POST'])
def cancel_process():
    d = request.json
    job_id = d.get('jobId')
    if job_id:
        with JOBS_LOCK:
            if job_id in JOBS:
                JOBS[job_id]['should_stop'] = True
                JOBS[job_id]['status'] = 'cancelling'
        # Update in SQLite
        db_update_job(job_id, should_stop=1, status='cancelling')
    return jsonify({'ok': True})

@app.route('/api/history')
def get_history():
    """Get user's video history from database"""
    limit = request.args.get('limit', 20, type=int)
    history = db_get_history(limit)
    
    result = []
    for h in history:
        item = {
            'id': h['id'],
            'jobId': h['job_id'],
            'title': h['title'],
            'reciter': h['reciter'],
            'surah': h['surah'],
            'startAyah': h['start_ayah'],
            'endAyah': h['end_ayah'],
            'quality': h['quality'],
            'fps': h['fps'],
            'filename': h['download_filename'],
            'status': h['status'],
            'createdAt': h['created_at'],
        }
        
        # Add download URL if video exists
        if h['output_path'] and os.path.exists(h['output_path']):
            item['downloadUrl'] = f"/api/download?jobId={h['job_id']}"
        
        result.append(item)
    
    return jsonify({'ok': True, 'history': result})

@app.route('/api/history/<int:history_id>', methods=['DELETE'])
def delete_history_item(history_id):
    """Delete a single history item"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get the history item first to clean up files
    c.execute("SELECT job_id FROM history WHERE id = ?", (history_id,))
    row = c.fetchone()
    
    if row:
        job_id = row[0]
        # Delete from history
        c.execute("DELETE FROM history WHERE id = ?", (history_id,))
        # Also delete the job if exists
        c.execute("SELECT workspace FROM jobs WHERE id = ?", (job_id,))
        job_row = c.fetchone()
        if job_row and job_row[0]:
            workspace = job_row[0]
            if os.path.exists(workspace):
                try:
                    shutil.rmtree(workspace, ignore_errors=True)
                except:
                    pass
        c.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    
    conn.commit()
    conn.close()
    
    return jsonify({'ok': True})

@app.route('/api/history/clear', methods=['POST'])
def clear_all_history():
    """Clear all history"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get all workspaces to clean up files
    c.execute("SELECT workspace FROM jobs WHERE workspace IS NOT NULL")
    workspaces = c.fetchall()
    
    for ws in workspaces:
        if ws[0] and os.path.exists(ws[0]):
            try:
                shutil.rmtree(ws[0], ignore_errors=True)
            except:
                pass
    
    # Delete all history and jobs
    c.execute("DELETE FROM history")
    c.execute("DELETE FROM jobs")
    conn.commit()
    conn.close()
    
    # Also clear RAM
    with JOBS_LOCK:
        JOBS.clear()
    
    return jsonify({'ok': True})

@app.route('/api/my-jobs')
def get_my_jobs():
    """Get all jobs for current session (from SQLite)"""
    status = request.args.get('status')  # pending, processing, complete, error
    jobs = db_get_all_jobs(status=status, limit=50)
    
    result = []
    for j in jobs:
        item = {
            'id': j['id'],
            'status': j['status'],
            'percent': j['percent'],
            'eta': j['eta'],
            'createdAt': j['created_at'],
            'completedAt': j['completed_at'],
        }
        
        # Add download URL if complete
        if j['status'] == 'complete' and j['output_path'] and os.path.exists(j['output_path']):
            item['downloadUrl'] = f"/api/download?jobId={j['id']}"
        
        if j['error']:
            item['error'] = j['error']
        
        result.append(item)
    
    return jsonify({'ok': True, 'jobs': result})

@app.route('/api/job/<job_id>')
def get_job_by_id(job_id):
    """Get specific job details"""
    job = get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(job)

@app.route('/api/config')
def conf(): return jsonify({'surahs': SURAH_NAMES, 'verseCounts': VERSE_COUNTS, 'reciters': RECITERS_MAP})

# ==========================================
# 🔧 Utility Functions
# ==========================================

def background_cleanup():
    """Cleanup old jobs and files every 10 minutes"""
    while True:
        time.sleep(600)  # Every 10 minutes
        try:
            db_cleanup_old_jobs(hours=1)  # Clean jobs older than 1 hour
            print("🧹 Background cleanup completed (1 hour expiry)")
        except Exception as e:
            print(f"Cleanup error: {e}")

def recover_pending_jobs():
    """Resume pending/processing jobs on server restart"""
    pending = db_get_pending_jobs()
    
    if not pending:
        return
    
    print(f"🔄 Found {len(pending)} pending jobs - resuming...")
    
    for job in pending:
        job_id = job['id']
        
        # Check if workspace still exists
        workspace = job.get('workspace')
        if not workspace or not os.path.exists(workspace):
            print(f"⚠️ Job {job_id} workspace missing - marking as error")
            db_update_job(job_id, status='error', error='Workspace deleted')
            continue
        
        # Get config
        config_json = job.get('config_json')
        if not config_json:
            print(f"⚠️ Job {job_id} has no config - marking as error")
            db_update_job(job_id, status='error', error='Config missing')
            continue
        
        try:
            config = json.loads(config_json)
            
            # Reset job status
            db_update_job(job_id, status='pending', percent=0)
            
            # Re-add to RAM
            with JOBS_LOCK:
                JOBS[job_id] = {
                    'id': job_id,
                    'percent': 0,
                    'status': 'pending',
                    'eta': '--:--',
                    'is_running': True,
                    'is_complete': False,
                    'output_path': None,
                    'error': None,
                    'should_stop': False,
                    'created_at': job.get('created_at', time.time()),
                    'workspace': workspace
                }
            
            # Start processing in background
            style_settings = config.get('style', {})
            
            def start_job(jid, cfg, style):
                threading.Thread(
                    target=build_video_task,
                    args=(
                        jid,
                        cfg.get('pexelsKey', ''),
                        cfg.get('reciter', ''),
                        int(cfg.get('surah', 1)),
                        int(cfg.get('startAyah', 1)),
                        int(cfg.get('endAyah', 0)),
                        cfg.get('quality', '720'),
                        cfg.get('bgQuery', ''),
                        int(cfg.get('fps', 20)),
                        cfg.get('dynamicBg', False),
                        cfg.get('useGlow', False),
                        cfg.get('useVignette', False),
                        style
                    ),
                    daemon=True
                ).start()
            
            # Delay start to allow server to fully initialize
            threading.Timer(2.0, start_job, args=(job_id, config, style_settings)).start()
            
            print(f"✅ Job {job_id} resumed successfully")
            
        except Exception as e:
            print(f"❌ Failed to resume job {job_id}: {e}")
            db_update_job(job_id, status='error', error=str(e))
    
    print(f"🚀 Resume complete - {len(pending)} jobs restarted")

threading.Thread(target=background_cleanup, daemon=True).start()

if __name__ == "__main__":
    # Initialize database on startup
    init_db()
    
    # Recover any pending jobs from previous session
    recover_pending_jobs()
    
    print("🚀 Quran Reels Generator starting...")
    app.run(host='0.0.0.0', port=7860, threaded=True)



