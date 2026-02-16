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
from functools import lru_cache
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

# Media Processing Imports
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import PIL.Image

if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

from moviepy.editor import (
    ImageClip, VideoFileClip, AudioFileClip, 
    CompositeVideoClip, ColorClip, concatenate_videoclips
)
from moviepy.config import change_settings
from proglog import ProgressBarLogger
from pydub import AudioSegment, silence
from deep_translator import GoogleTranslator

# ==========================================
# ⚙️ Configuration & Setup
# ==========================================

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def app_dir():
    if getattr(sys, "frozen", False): return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

EXEC_DIR = app_dir()
BUNDLE_DIR = EXEC_DIR 

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
AUDIO_CACHE_DIR = os.path.join(EXEC_DIR, "cache_audio_slices")  # ⚡ NEW: Persistent Cache
os.makedirs(BASE_TEMP_DIR, exist_ok=True)
os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)
os.makedirs(VISION_DIR, exist_ok=True)

# Data Constants
VERSE_COUNTS = {1: 7, 2: 286, 3: 200, 4: 176, 5: 120, 6: 165, 7: 206, 8: 75, 9: 129, 10: 109, 11: 123, 12: 111, 13: 43, 14: 52, 15: 99, 16: 128, 17: 111, 18: 110, 19: 98, 20: 135, 21: 112, 22: 78, 23: 118, 24: 64, 25: 77, 26: 227, 27: 93, 28: 88, 29: 69, 30: 60, 31: 34, 32: 30, 33: 73, 34: 54, 35: 45, 36: 83, 37: 182, 38: 88, 39: 75, 40: 85, 41: 54, 42: 53, 43: 89, 44: 59, 45: 37, 46: 35, 47: 38, 48: 29, 49: 18, 50: 45, 51: 60, 52: 49, 53: 62, 54: 55, 55: 78, 56: 96, 57: 29, 58: 22, 59: 24, 60: 13, 61: 14, 62: 11, 63: 11, 64: 18, 65: 12, 66: 12, 67: 30, 68: 52, 69: 52, 70: 44, 71: 28, 72: 28, 73: 20, 74: 56, 75: 40, 76: 31, 77: 50, 78: 40, 79: 46, 80: 42, 81: 29, 82: 19, 83: 36, 84: 25, 85: 22, 86: 17, 87: 19, 88: 26, 89: 30, 90: 20, 91: 15, 92: 21, 93: 11, 94: 8, 95: 8, 96: 19, 97: 5, 98: 8, 99: 8, 100: 11, 101: 11, 102: 8, 103: 3, 104: 9, 105: 5, 106: 4, 107: 7, 108: 3, 109: 6, 110: 3, 111: 5, 112: 4, 113: 5, 114: 6}
SURAH_NAMES = ['الفاتحة', 'البقرة', 'آل عمران', 'النساء', 'المائدة', 'الأنعام', 'الأعراف', 'الأنفال', 'التوبة', 'يونس', 'هود', 'يوسف', 'الرعد', 'إبراهيم', 'الحجر', 'النحل', 'الإسراء', 'الكهف', 'مريم', 'طه', 'الأنبياء', 'الحج', 'المؤمنون', 'النور', 'الفرقان', 'الشعراء', 'النمل', 'القصص', 'العنكبوت', 'الروم', 'لقمان', 'السجدة', 'الأحزاب', 'سبأ', 'فاطر', 'يس', 'الصافات', 'ص', 'الزمر', 'غافر', 'فصلت', 'الشورى', 'الزخرف', 'الدخان', 'الجاثية', 'الأحقاف', 'محمد', 'الفتح', 'الحجرات', 'ق', 'الذاريات', 'الطور', 'النجم', 'القمر', 'الرحمن', 'الواقعة', 'الحديد', 'المجادلة', 'الحشر', 'الممتحنة', 'الصف', 'الجمعة', 'المنافقون', 'التغابن', 'الطلاق', 'التحريم', 'الملك', 'القلم', 'الحاقة', 'المعارج', 'نوح', 'الجن', 'المزمل', 'المدثر', 'القيامة', 'الإنسان', 'المرسلات', 'النبأ', 'النازعات', 'عبس', 'التكوير', 'الانفطار', 'المطففين', 'الانشقاق', 'البروج', 'الطارق', 'الأعلى', 'الغاشية', 'الفجر', 'البلد', 'الشمس', 'الليل', 'الضحى', 'الشرح', 'التين', 'العلق', 'القدر', 'البينة', 'الزلزلة', 'العاديات', 'القارعة', 'التكاثر', 'العصر', 'الهمزة', 'الفيل', 'قريش', 'الماعون', 'الكوثر', 'الكافرون', 'النصر', 'المسد', 'الإخلاص', 'الفلق', 'الناس']

# 🚀 Reciters Config
NEW_RECITERS_CONFIG = {
    'ادريس أبكر': (12, "https://server6.mp3quran.net/abkr/"),
    'منصور السالمي': (245, "https://server14.mp3quran.net/mansor/"),
    'رعد الكردي': (221, "https://server6.mp3quran.net/kurdi/"),
}

OLD_RECITERS_MAP = {
    'ياسر الدوسري':'Yasser_Ad-Dussary_128kbps', 
    'الشيخ عبدالرحمن السديس': 'Abdurrahmaan_As-Sudais_64kbps', 
    'الشيخ ماهر المعيقلي': 'Maher_AlMuaiqly_64kbps', 
    'الشيخ سعود الشريم': 'Saood_ash-Shuraym_64kbps', 
    'الشيخ مشاري العفاسي': 'Alafasy_64kbps',
    'ناصر القطامي':'Nasser_Alqatami_128kbps', 
}

# 🆕 Full Surah Reciters (Islam Sobhi)
FULL_SURAH_RECITERS = {
    'إسلام صبحي': 'https://server14.mp3quran.net/islam/Rewayat-Hafs-A-n-Assem/' 
}

RECITERS_MAP = {**{k: k for k in NEW_RECITERS_CONFIG.keys()}, **OLD_RECITERS_MAP, **{k: k for k in FULL_SURAH_RECITERS.keys()}}

app = Flask(__name__, static_folder=EXEC_DIR)
CORS(app)

# ==========================================
# 🧠 Job Management
# ==========================================
JOBS = {}
JOBS_LOCK = threading.Lock()

def create_job():
    job_id = str(uuid.uuid4())
    job_dir = os.path.join(BASE_TEMP_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    with JOBS_LOCK:
        JOBS[job_id] = {'id': job_id, 'percent': 0, 'status': 'جاري التحضير...', 'eta': '--:--', 'is_running': True, 'is_complete': False, 'output_path': None, 'error': None, 'should_stop': False, 'created_at': time.time(), 'workspace': job_dir}
    return job_id

def update_job_status(job_id, percent, status, eta=None):
    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id]['percent'] = percent
            JOBS[job_id]['status'] = status
            if eta: JOBS[job_id]['eta'] = eta

def get_job(job_id):
    with JOBS_LOCK: return JOBS.get(job_id)

def check_stop(job_id):
    job = get_job(job_id)
    if not job or job.get('should_stop', False):
        raise Exception("Stopped")

# ==========================================
# 📊 Scoped Logger
# ==========================================
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
    try:
        return ImageFont.truetype(font_path, size)
    except:
        return ImageFont.load_default()

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
    except Exception as e:
        print(f"Download Error: {e}")
        raise e

# ⚡ OPTIMIZED ESTIMATOR (Faster Seek)
def estimate_ayah_timings(audio_path, ayah_texts, silence_thresh_offset=-16, min_silence_len=700):
    sound = AudioSegment.from_file(audio_path)
    total_duration_sec = sound.duration_seconds
    db_thresh = sound.dBFS + silence_thresh_offset
    
    # seek_step=50 is much faster than default (1ms) or 10ms
    chunks_ms = silence.detect_nonsilent(
        sound, 
        min_silence_len=min_silence_len, 
        silence_thresh=db_thresh,
        seek_step=50 
    )
    
    num_ayahs = len(ayah_texts)
    num_chunks = len(chunks_ms)
    timings = []
    
    if num_chunks == num_ayahs:
        print(f"✅ Exact match found! ({num_chunks} chunks)")
        for i, (start_ms, end_ms) in enumerate(chunks_ms):
            start_sec = max(0, (start_ms / 1000.0) - 0.1)
            end_sec = min(total_duration_sec, (end_ms / 1000.0) + 0.1)
            
            if i < num_chunks - 1:
                next_start = chunks_ms[i+1][0] / 1000.0
                if next_start > end_sec: end_sec = next_start
            
            timings.append({'ayah': i + 1, 'start': start_sec, 'end': end_sec})
    else:
        print(f"⚠️ Mismatch ({num_chunks} chunks vs {num_ayahs} Ayahs). Using Text Ratio.")
        clean_texts = [t.replace(" ", "").strip() for t in ayah_texts]
        total_chars = sum(len(t) for t in clean_texts)
        current_time = 0.0
        
        for i, text in enumerate(clean_texts):
            ratio = len(text) / total_chars
            duration = ratio * total_duration_sec
            end_time = current_time + duration
            timings.append({'ayah': i + 1, 'start': round(current_time, 2), 'end': round(end_time, 2)})
            current_time = end_time

    return timings

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
    out = os.path.join(workspace_dir, f'part{idx}.mp3')
    seg.fade_in(50).fade_out(50).export(out, format="mp3")
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
            t = re.sub(r'^بِسْمِ [^ ]+ [^ ]+ [^ ]+', '', t).strip()
            t = t.replace("بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ", "").strip()
        return t
    except: return "Text Error"

def get_en_text(surah, ayah):
    try: return requests.get(f'http://api.alquran.cloud/v1/ayah/{surah}:{ayah}/en.sahih').json()['data']['text']
    except: return ""

def wrap_text(text, per_line):
    words = text.split()
    return '\n'.join([' '.join(words[i:i+per_line]) for i in range(0, len(words), per_line)])

def create_vignette_mask(w, h):
    Y, X = np.ogrid[:h, :w]
    mask = np.clip((np.sqrt((X - w/2)**2 + (Y - h/2)**2) / np.sqrt((w/2)**2 + (h/2)**2)) * 1.16, 0, 1) ** 3 
    mask_img = np.zeros((h, w, 4), dtype=np.uint8)
    mask_img[:, :, 3] = (mask * 255).astype(np.uint8)
    return ImageClip(mask_img, ismask=False)

def create_text_clip(arabic, duration, target_w, scale_factor=1.0, glow=False):
    words = arabic.split()
    wc = len(words)
    if wc > 60: base_fs, pl = 30, 12
    elif wc > 40: base_fs, pl = 35, 10
    elif wc > 25: base_fs, pl = 41, 9
    elif wc > 15: base_fs, pl = 46, 8
    else: base_fs, pl = 48, 7
    final_fs = int(base_fs * scale_factor)
    font = get_cached_font(FONT_PATH_ARABIC, final_fs)
    wrapped_text = wrap_text(arabic, pl)
    lines = wrapped_text.split('\n')
    dummy = Image.new('RGBA', (target_w, 100))
    d = ImageDraw.Draw(dummy)
    line_metrics = []
    total_h = 0
    GAP = 10 * scale_factor
    for l in lines:
        bbox = d.textbbox((0, 0), l, font=font)
        h = bbox[3] - bbox[1]
        line_metrics.append(h)
        total_h += h + GAP
    total_h += 40 
    img = Image.new('RGBA', (target_w, int(total_h)), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    curr_y = 20
    for i, line in enumerate(lines):
        w = draw.textbbox((0, 0), line, font=font)[2]
        x = (target_w - w) // 2
        if glow: draw.text((x, curr_y), line, font=font, fill=(255,255,255,40), stroke_width=5, stroke_fill=(255,255,255,40))
        draw.text((x+1, curr_y+1), line, font=font, fill=(0,0,0,180))
        draw.text((x, curr_y), line, font=font, fill='white', stroke_width=2, stroke_fill='black')
        curr_y += line_metrics[i] + GAP
    return ImageClip(np.array(img)).set_duration(duration).fadein(0.2).fadeout(0.2)

def create_english_clip(text, duration, target_w, scale_factor=1.0, glow=False):
    font = get_cached_font(FONT_PATH_ENGLISH, int(30 * scale_factor))
    img = Image.new('RGBA', (target_w, 200), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    draw.text((target_w/2, 20), wrap_text(text, 10), font=font, fill='#FFD700', align='center', anchor="ma", stroke_width=1, stroke_fill='black')
    return ImageClip(np.array(img)).set_duration(duration).fadein(0.2).fadeout(0.2)

def fetch_video_pool(user_key, custom_query, count=1, job_id=None):
    pool = []
    if custom_query and len(custom_query) > 2:
        try: q_base = GoogleTranslator(source='auto', target='en').translate(custom_query.strip())
        except: q_base = "nature landscape"
    else:
        safe_topics = ['nature landscape', 'mosque architecture', 'sky clouds', 'galaxy stars', 'ocean waves', 'forest trees', 'desert dunes', 'waterfall', 'mountains']
        q_base = random.choice(safe_topics)
    q = f"{q_base} no people"
    try:
        check_stop(job_id)
        random_page = random.randint(1, 10)
        url = f"https://api.pexels.com/videos/search?query={q}&per_page={count+5}&page={random_page}&orientation=portrait"
        r = requests.get(url, headers={'Authorization': user_key}, timeout=15)
        if r.status_code == 200:
            vids = r.json().get('videos', [])
            random.shuffle(vids)
            for vid in vids:
                if len(pool) >= count: break
                check_stop(job_id)
                # ⚡ ONLY DOWNLOAD 1080p OR LOWER
                f = next((vf for vf in vid['video_files'] if vf['width'] == 1080 and vf['height'] == 1920), None)
                if not f: f = next((vf for vf in vid['video_files'] if vf['width'] <= 1080 and vf['height'] > vf['width']), None)
                if f:
                    path = os.path.join(VISION_DIR, f"bg_{vid['id']}.mp4")
                    if not os.path.exists(path):
                        smart_download(f['link'], path, job_id)
                    pool.append(path)
    except Exception as e: print(f"Fetch Error: {e}")
    return pool

# ==========================================
# ⚡ SUPER OPTIMIZED BUILDER (CACHING)
# ==========================================
def build_video_task(job_id, user_pexels_key, reciter_id, surah, start, end, quality, bg_query, fps, dynamic_bg, use_glow, use_vignette):
    job = get_job(job_id)
    workspace = job['workspace']
    target_w, target_h = (1080, 1920) if quality == '1080' else (720, 1280)
    scale = 1.0 if quality == '1080' else 0.67
    last = min(end if end else start+9, VERSE_COUNTS.get(surah, 286))
    total_ayahs = (last - start) + 1
    
    try:
        # 1. Backgrounds
        vpool = fetch_video_pool(user_pexels_key, bg_query, count=total_ayahs if dynamic_bg else 1, job_id=job_id)
        
        # ⚡ PRE-RENDER BACKGROUND (Crucial for Speed)
        processed_bg_paths = []
        update_job_status(job_id, 5, "Optimizing Background Video...")
        if not vpool:
            base_bg_path = os.path.join(workspace, "optimized_bg_0.mp4")
            ColorClip((target_w, target_h), color=(15, 20, 35), duration=10).write_videofile(
                base_bg_path, fps=fps, codec='libx264', preset='ultrafast', logger=None
            )
            processed_bg_paths.append(base_bg_path)
        else:
            for idx, vid_path in enumerate(vpool):
                optimized_path = os.path.join(workspace, f"optimized_bg_{idx}.mp4")
                clip = VideoFileClip(vid_path)
                if clip.w != target_w or clip.h != target_h:
                    clip = clip.resize(height=target_h)
                    clip = clip.crop(width=target_w, height=target_h, x_center=target_w/2, y_center=target_h/2)
                if clip.duration > 15: clip = clip.subclip(0, 15)
                clip.write_videofile(optimized_path, fps=fps, codec='libx264', preset='ultrafast', threads=4, logger=None)
                clip.close()
                processed_bg_paths.append(optimized_path)

        overlays_static = [ColorClip((target_w, target_h), color=(0,0,0)).set_opacity(0.3)]
        if use_vignette: overlays.append(create_vignette_mask(target_w, target_h))

        segments = []
        is_full_surah_mode = reciter_id in FULL_SURAH_RECITERS
        sliced_audio_map = {}
        
        # ⚡ ISLAM SOBHI LOGIC (WITH PERSISTENT CACHING)
        if is_full_surah_mode:
            update_job_status(job_id, 10, "Checking Audio Cache...")
            
            # Create a persistent cache folder for this specific reciter/surah
            reciter_safe_name = re.sub(r'[^a-zA-Z0-9]', '_', reciter_id)
            surah_cache_dir = os.path.join(AUDIO_CACHE_DIR, reciter_safe_name, str(surah))
            os.makedirs(surah_cache_dir, exist_ok=True)
            
            # Check if we already have the slices for the requested ayahs
            missing_slices = False
            for a in range(start, last+1):
                if not os.path.exists(os.path.join(surah_cache_dir, f"{a}.mp3")):
                    missing_slices = True
                    break
            
            if missing_slices:
                update_job_status(job_id, 15, "Processing Audio (First Run Only)...")
                # We need to download and process
                base_url = FULL_SURAH_RECITERS[reciter_id]
                full_audio_url = f"{base_url}{surah:03d}.mp3"
                full_audio_path = os.path.join(workspace, "full_surah.mp3")
                
                smart_download(full_audio_url, full_audio_path, job_id)
                
                # Get all texts for the WHOLE surah to map correctly
                # (Or at least up to the last ayah needed)
                # To be safe, we fetch texts for the requested range to map relative timing
                all_texts = [get_text(surah, a) for a in range(start, last+1)]
                
                timings = estimate_ayah_timings(full_audio_path, all_texts)
                
                full_audio = AudioSegment.from_file(full_audio_path)
                for t_idx, t in enumerate(timings):
                    actual_ayah_num = start + t_idx
                    cached_slice_path = os.path.join(surah_cache_dir, f"{actual_ayah_num}.mp3")
                    
                    start_ms = int(t['start'] * 1000)
                    end_ms = int(t['end'] * 1000)
# ==========================================
# ⚡ SUPER OPTIMIZED BUILDER (FIXED SLICING)
# ==========================================
def build_video_task(job_id, user_pexels_key, reciter_id, surah, start, end, quality, bg_query, fps, dynamic_bg, use_glow, use_vignette):
    job = get_job(job_id)
    workspace = job['workspace']
    target_w, target_h = (1080, 1920) if quality == '1080' else (720, 1280)
    scale = 1.0 if quality == '1080' else 0.67
    
    # 1. Determine Range
    surah_total_verses = VERSE_COUNTS.get(surah, 286)
    last_requested = min(end if end else start+9, surah_total_verses)
    total_ayahs_to_render = (last_requested - start) + 1
    
    try:
        # 2. Backgrounds (Optimized)
        vpool = fetch_video_pool(user_pexels_key, bg_query, count=total_ayahs_to_render if dynamic_bg else 1, job_id=job_id)
        
        processed_bg_paths = []
        update_job_status(job_id, 5, "Optimizing Background Video...")
        
        if not vpool:
            base_bg_path = os.path.join(workspace, "optimized_bg_0.mp4")
            ColorClip((target_w, target_h), color=(15, 20, 35), duration=10).write_videofile(
                base_bg_path, fps=fps, codec='libx264', preset='ultrafast', logger=None
            )
            processed_bg_paths.append(base_bg_path)
        else:
            for idx, vid_path in enumerate(vpool):
                optimized_path = os.path.join(workspace, f"optimized_bg_{idx}.mp4")
                clip = VideoFileClip(vid_path)
                if clip.w != target_w or clip.h != target_h:
                    clip = clip.resize(height=target_h)
                    clip = clip.crop(width=target_w, height=target_h, x_center=target_w/2, y_center=target_h/2)
                if clip.duration > 15: clip = clip.subclip(0, 15)
                clip.write_videofile(optimized_path, fps=fps, codec='libx264', preset='ultrafast', threads=4, logger=None)
                clip.close()
                processed_bg_paths.append(optimized_path)

        # 3. Static Overlays
        overlays_static = [ColorClip((target_w, target_h), color=(0,0,0)).set_opacity(0.3)]
        if use_vignette: overlays_static.append(create_vignette_mask(target_w, target_h))

        segments = []
        is_full_surah_mode = reciter_id in FULL_SURAH_RECITERS
        sliced_audio_map = {}
        
        # =========================================================
        # ⚡ ISLAM SOBHI LOGIC (FIXED: MAP FULL SURAH FIRST)
        # =========================================================
        if is_full_surah_mode:
            update_job_status(job_id, 10, "Checking Audio Cache...")
            
            reciter_safe_name = re.sub(r'[^a-zA-Z0-9]', '_', reciter_id)
            surah_cache_dir = os.path.join(AUDIO_CACHE_DIR, reciter_safe_name, str(surah))
            os.makedirs(surah_cache_dir, exist_ok=True)
            
            # Check if we have the specific ayahs requested
            missing_slices = False
            for a in range(start, last_requested+1):
                if not os.path.exists(os.path.join(surah_cache_dir, f"{a}.mp3")):
                    missing_slices = True
                    break
            
            if missing_slices:
                update_job_status(job_id, 15, "Analyzing Full Surah (One Time)...")
                
                base_url = FULL_SURAH_RECITERS[reciter_id]
                full_audio_url = f"{base_url}{surah:03d}.mp3"
                full_audio_path = os.path.join(workspace, "full_surah.mp3")
                
                smart_download(full_audio_url, full_audio_path, job_id)
                
                # 🛑 FIX: Download Text for ALL ayahs in Surah (1 to Total)
                # This ensures the audio chunks align 1:1 with the text lines.
                all_surah_texts = []
                for a_num in range(1, surah_total_verses + 1):
                    all_surah_texts.append(get_text(surah, a_num))
                
                # Run Estimator on the FULL Set
                timings = estimate_ayah_timings(full_audio_path, all_surah_texts)
                
                full_audio = AudioSegment.from_file(full_audio_path)
                
                # Save ALL slices to cache (so next time it's instant)
                for t in timings:
                    ayah_num = t['ayah'] # This is the actual Ayah number (1, 2, 3...)
                    cached_slice_path = os.path.join(surah_cache_dir, f"{ayah_num}.mp3")
                    
                    start_ms = int(t['start'] * 1000)
                    end_ms = int(t['end'] * 1000)
                    
                    # Export slice
                    full_audio[start_ms:end_ms].fade_in(50).fade_out(50).export(cached_slice_path, format="mp3", bitrate="64k")
            
            # Now Map ONLY the requested ayahs
            for a in range(start, last_requested+1):
                sliced_audio_map[a] = os.path.join(surah_cache_dir, f"{a}.mp3")

        # 4. Main Generation Loop
        for i, ayah in enumerate(range(start, last_requested+1)):
            check_stop(job_id)
            update_job_status(job_id, 20 + int((i / total_ayahs_to_render) * 70), f'Rendering Ayah {ayah}...')

            if is_full_surah_mode:
                ap = sliced_audio_map.get(ayah)
                # Fallback check
                if not ap or not os.path.exists(ap):
                     ap = download_audio(reciter_id, surah, ayah, i, workspace, job_id)
            else:
                ap = download_audio(reciter_id, surah, ayah, i, workspace, job_id)
                
            audioclip = AudioFileClip(ap)
            duration = audioclip.duration

            # ... (Rest of logic remains identical) ...
            ar_text = f"{get_text(surah, ayah)} ({ayah})"
            en_text = get_en_text(surah, ayah)
            
            ac = create_text_clip(ar_text, duration, target_w, scale, use_glow)
            ec = create_english_clip(en_text, duration, target_w, scale, use_glow)

            ar_y_pos = target_h * 0.32
            en_y_pos = ar_y_pos + ac.h + (20 * scale)
            ac = ac.set_position(('center', ar_y_pos))
            ec = ec.set_position(('center', en_y_pos))

            bg_source_path = processed_bg_paths[i % len(processed_bg_paths)] if dynamic_bg else processed_bg_paths[0]
            bg_clip = VideoFileClip(bg_source_path)
            
            if bg_clip.duration < duration:
                bg_clip = bg_clip.loop(duration=duration)
            else:
                max_start = max(0, bg_clip.duration - duration)
                start_t = random.uniform(0, max_start)
                bg_clip = bg_clip.subclip(start_t, start_t + duration)

            bg_clip = bg_clip.set_duration(duration).fadein(0.5).fadeout(0.5)
            
            segment_overlays = [o.set_duration(duration) for o in overlays_static]
            segment = CompositeVideoClip([bg_clip] + segment_overlays + [ac, ec]).set_audio(audioclip)
            segments.append(segment)

        update_job_status(job_id, 95, "Merging Clips...")
        final_video = concatenate_videoclips(segments, method="compose")
        out_p = os.path.join(workspace, f"out_{job_id}.mp4")
        
        final_video.write_videofile(
            out_p, fps=fps, codec='libx264', audio_codec='aac', 
            preset='ultrafast', threads=os.cpu_count() or 4, logger=ScopedQuranLogger(job_id)
        )
        
        with JOBS_LOCK: JOBS[job_id].update({'output_path': out_p, 'is_complete': True, 'is_running': False, 'percent': 100, 'status': "Done!"})
    
    except Exception as e:
        msg = str(e)
        traceback.print_exc()
        status = "Cancelled" if msg == "Stopped" else "Error"
        with JOBS_LOCK: JOBS[job_id].update({'error': msg, 'status': status, 'is_running': False})
    
    finally:
        try:
            if 'final_video' in locals(): final_video.close()
            for p in processed_bg_paths:
                try: os.remove(p)
                except: pass
            for s in segments: s.close()
        except: pass
        gc.collect()

def background_cleanup():
    while True:
        time.sleep(3600)
        current_time = time.time()
        # Clean up old jobs
        with JOBS_LOCK:
            to_delete = []
            for jid, job in JOBS.items():
                if current_time - job['created_at'] > 3600: to_delete.append(jid)
            for jid in to_delete: del JOBS[jid]
        # Clean up workspaces (BUT NOT AUDIO CACHE)
        try:
            if os.path.exists(BASE_TEMP_DIR):
                for folder in os.listdir(BASE_TEMP_DIR):
                    folder_path = os.path.join(BASE_TEMP_DIR, folder)
                    if os.path.isdir(folder_path):
                        if current_time - os.path.getctime(folder_path) > 3600: shutil.rmtree(folder_path, ignore_errors=True)
        except: pass

threading.Thread(target=background_cleanup, daemon=True).start()

@app.route('/')
def ui(): return send_file(UI_PATH) if os.path.exists(UI_PATH) else "API Running"

@app.route('/api/generate', methods=['POST'])
def gen():
    d = request.json
    job_id = create_job()
    threading.Thread(target=build_video_task, args=(job_id, d['pexelsKey'], d['reciter'], int(d['surah']), int(d['startAyah']), int(d.get('endAyah',0)), d.get('quality','720'), d.get('bgQuery',''), int(d.get('fps',20)), d.get('dynamicBg',False), d.get('useGlow',False), d.get('useVignette',False)), daemon=True).start()
    return jsonify({'ok': True, 'jobId': job_id})

@app.route('/api/progress')
def prog(): return jsonify(get_job(request.args.get('jobId')))

@app.route('/api/download')
def download_result(): return send_file(get_job(request.args.get('jobId'))['output_path'], as_attachment=True)

@app.route('/api/cancel', methods=['POST'])
def cancel_process():
    d = request.json
    job_id = d.get('jobId')
    if job_id:
        with JOBS_LOCK:
            if job_id in JOBS:
                JOBS[job_id]['should_stop'] = True
                JOBS[job_id]['status'] = "Stopping..."
    return jsonify({'ok': True})

@app.route('/api/config')
def conf(): return jsonify({'surahs': SURAH_NAMES, 'verseCounts': VERSE_COUNTS, 'reciters': RECITERS_MAP})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, threaded=True)

