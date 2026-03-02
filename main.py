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

ETHEREAL_AUDIO_FILTER = (
    "highpass=f=80, "
    "equalizer=f=200:width_type=h:width=200:g=3, "
    "equalizer=f=8000:width_type=h:width=1000:g=4, "
    "acompressor=threshold=-21dB:ratio=4:attack=200:release=1000, "
    "aecho=0.8:0.9:60|1000:0.4|0.2, "
    "extrastereo=m=1.3, "
    "loudnorm=I=-16:TP=-1.5:LRA=11"
)

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ==========================================
# 🚀 API Keys & Local Fallback Setup
# ==========================================

def app_dir():
    if getattr(sys, "frozen", False): return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

EXEC_DIR = app_dir()
BUNDLE_DIR = EXEC_DIR 

# PEXELS_API_KEYS = [
#     "AmAgE0J5AuBbsvR6dmG7qQLIc5uYZvDim2Vx250F5QoHNKnGdCofFerx",
#     "Fv0qzUGYwbGr6yHsauaXuNKiNR9L7OE7VLr5Wq6SngcLjavmkCEAskb2",
#     "1NK8BaBXGsXm4Uxzcesxm0Jxh2yCILOwqqsj4GiM57dXcb7b8bbDYyOu",
#  "C9KJNtJET2wAnmD42Gbu0OolTlmhoT02CX7fyst3kKEvnjRRWLiAqQ9t" 
# ]
# مفاتيح تجريبية، يفضل استخدام مفتاحك الخاص
PEXELS_API_KEYS = ["Your_Pexels_Key_Here"] if "Your_Pexels_Key_Here" != "Your_Pexels_Key_Here" else []


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
# تأكد من وجود هذه الخطوط في مجلد fonts بجوار ملف الـ exe
FONT_PATH_ARABIC = os.path.join(FONT_DIR, "Arabic.ttf") 
FONT_PATH_ENGLISH = os.path.join(FONT_DIR, "English.otf")
VISION_DIR = os.path.join(BUNDLE_DIR, "vision")
UI_PATH = os.path.join(BUNDLE_DIR, "UI.html") # تم تعديل الاسم ليتطابق مع ملفك

# Master Temp Directory
BASE_TEMP_DIR = os.path.join(EXEC_DIR, "temp_workspaces")
os.makedirs(BASE_TEMP_DIR, exist_ok=True)
os.makedirs(VISION_DIR, exist_ok=True)

# Data Constants
VERSE_COUNTS = {1: 7, 2: 286, 3: 200, 4: 176, 5: 120, 6: 165, 7: 206, 8: 75, 9: 129, 10: 109, 11: 123, 12: 111, 13: 43, 14: 52, 15: 99, 16: 128, 17: 111, 18: 110, 19: 98, 20: 135, 21: 112, 22: 78, 23: 118, 24: 64, 25: 77, 26: 227, 27: 93, 28: 88, 29: 69, 30: 60, 31: 34, 32: 30, 33: 73, 34: 54, 35: 45, 36: 83, 37: 182, 38: 88, 39: 75, 40: 85, 41: 54, 42: 53, 43: 89, 44: 59, 45: 37, 46: 35, 47: 38, 48: 29, 49: 18, 50: 45, 51: 60, 52: 49, 53: 62, 54: 55, 55: 78, 56: 96, 57: 29, 58: 22, 59: 24, 60: 13, 61: 14, 62: 11, 63: 11, 64: 18, 65: 12, 66: 12, 67: 30, 68: 52, 69: 52, 70: 44, 71: 28, 72: 28, 73: 20, 74: 56, 75: 40, 76: 31, 77: 50, 78: 40, 79: 46, 80: 42, 81: 29, 82: 19, 83: 36, 84: 25, 85: 22, 86: 17, 87: 19, 88: 26, 89: 30, 90: 20, 91: 15, 92: 21, 93: 11, 94: 8, 95: 8, 96: 19, 97: 5, 98: 8, 99: 8, 100: 11, 101: 11, 102: 8, 103: 3, 104: 9, 105: 5, 106: 4, 107: 7, 108: 3, 109: 6, 110: 3, 111: 5, 112: 4, 113: 5, 114: 6}
SURAH_NAMES = ['الفاتحة', 'البقرة', 'آل عمران', 'النساء', 'المائدة', 'الأنعام', 'الأعراف', 'الأنفال', 'التوبة', 'يونس', 'هود', 'يوسف', 'الرعد', 'إبراهيم', 'الحجر', 'النحل', 'الإسراء', 'الكهف', 'مريم', 'طه', 'الأنبياء', 'الحج', 'المؤمنون', 'النور', 'الفرقان', 'الشعراء', 'النمل', 'القصص', 'العنكبوت', 'الروم', 'لقمان', 'السجدة', 'الأحزاب', 'سبأ', 'فاطر', 'يس', 'الصافات', 'ص', 'الزمر', 'غافر', 'فصلت', 'الشورى', 'الزخرف', 'الدخان', 'الجاثية', 'الأحقاف', 'محمد', 'الفتح', 'الحجرات', 'ق', 'الذاريات', 'الطور', 'النجم', 'القمر', 'الرحمن', 'الواقعة', 'الحديد', 'المجادلة', 'الحشر', 'الممتحنة', 'الصف', 'الجمعة', 'المنافقون', 'التغابن', 'الطلاق', 'التحريم', 'الملك', 'القلم', 'الحاقة', 'المعارج', 'نوح', 'الجن', 'المزمل', 'المدثر', 'القيامة', 'الإنسان', 'المرسلات', 'النبأ', 'النازعات', 'عبس', 'التكوير', 'الانفطار', 'المطففين', 'الانشقاق', 'البروج', 'الطارق', 'الأعلى', 'الغاشية', 'الفجر', 'البلد', 'الشمس', 'الليل', 'الضحى', 'الشرح', 'التين', 'العلق', 'القدر', 'البينة', 'الزلزلة', 'العاديات', 'القارعة', 'التكاثر', 'العصر', 'الهمزة', 'الفيل', 'قريش', 'الماعون', 'الكوثر', 'الكافرون', 'النصر', 'المسد', 'الإخلاص', 'الفلق', 'الناس']

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

def cleanup_job(job_id):
    with JOBS_LOCK: job = JOBS.pop(job_id, None)
    if job and os.path.exists(job['workspace']):
        try: shutil.rmtree(job['workspace'])
        except: pass

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

# ✅ Cache fonts to prevent repeated disk I/O
@lru_cache(maxsize=10)
def get_cached_font(font_path, size):
    try:
        return ImageFont.truetype(font_path, size)
    except:
        print(f"⚠️ Warning: Could not load font at {font_path}. Using default.")
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
        print(f"Download error for {url}: {e}")
        raise e

def process_mp3quran_audio(reciter_name, surah, ayah, idx, workspace_dir, job_id):
    reciter_id, server_url = NEW_RECITERS_CONFIG[reciter_name]
    cache_dir = os.path.join(EXEC_DIR, "cache_mp3quran", str(reciter_id))
    os.makedirs(cache_dir, exist_ok=True)
    full_audio_path = os.path.join(cache_dir, f"{surah:03d}.mp3")
    timings_path = os.path.join(cache_dir, f"{surah:03d}.json")

    if not os.path.exists(full_audio_path) or not os.path.exists(timings_path):
        smart_download(f"{server_url}{surah:03d}.mp3", full_audio_path, job_id)
        check_stop(job_id)
        try:
            t_data = requests.get(f"https://mp3quran.net/api/v3/ayat_timing?surah={surah}&read={reciter_id}", timeout=15).json()
            timings = {item['ayah']: {'start': item['start_time'], 'end': item['end_time']} for item in t_data}
            with open(timings_path, 'w') as f: json.dump(timings, f)
        except Exception as e:
            print(f"Error fetching timings: {e}")
            raise Exception("فشل في جلب توقيتات الآيات من المصدر")

    with open(timings_path, 'r') as f:
        t = json.load(f)[str(ayah)]
    
    check_stop(job_id)
    
    seg = AudioSegment.from_file(full_audio_path)[t['start']:t['end']]
    
    silence_thresh = seg.dBFS - 16 
    start_trim = detect_leading_silence(seg, silence_threshold=silence_thresh)
    end_trim = detect_leading_silence(seg.reverse(), silence_threshold=silence_thresh)
    duration = len(seg)
    
    if duration - start_trim - end_trim > 200: 
        seg = seg[start_trim:duration-end_trim]
    
    seg = seg.fade_in(20).fade_out(20) 
    
    out = os.path.join(workspace_dir, f'ayah_{ayah}_full.mp3')
    seg.export(out, format="mp3")
    return out

def detect_leading_silence(sound, silence_threshold=-50.0, chunk_size=10):
    trim_ms = 0
    assert chunk_size > 0
    while trim_ms < len(sound) and sound[trim_ms:trim_ms+chunk_size].dBFS < silence_threshold:
        trim_ms += chunk_size
    return trim_ms

def download_audio(reciter_key, surah, ayah, idx, workspace_dir, job_id):
    if reciter_key in NEW_RECITERS_CONFIG:
        return process_mp3quran_audio(reciter_key, surah, ayah, idx, workspace_dir, job_id)
    
    url = f'https://everyayah.com/data/{reciter_key}/{surah:03d}{ayah:03d}.mp3'
    out = os.path.join(workspace_dir, f'ayah_{ayah}_full.mp3')
    smart_download(url, out, job_id)
    
    snd = AudioSegment.from_file(out)
    start, end = detect_silence(snd, snd.dBFS-20), detect_silence(snd.reverse(), snd.dBFS-20)
    trimmed = snd[max(0, start-30):len(snd)-max(0, end-30)]
    (AudioSegment.silent(duration=50) + trimmed.fade_in(20).fade_out(20)).export(out, format='mp3')
    return out

def get_text(surah, ayah):
    try:
        t = requests.get(f'https://api.alquran.cloud/v1/ayah/{surah}:{ayah}/quran-simple', timeout=10).json()['data']['text']
        if surah not in [1, 9] and ayah == 1:
            t = re.sub(r'^بِسْمِ [^ ]+ [^ ]+ [^ ]+', '', t).strip()
            t = t.replace("بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ", "").strip()
        return t
    except: return "خطأ في جلب النص"

def get_en_text(surah, ayah):
    try: return requests.get(f'http://api.alquran.cloud/v1/ayah/{surah}:{ayah}/en.sahih', timeout=10).json()['data']['text']
    except: return ""

# ==========================================
# 🆕 وظيفة جديدة لتقسيم النص إلى كلمات
# ==========================================
def chunk_text_by_words(text, max_words=5):
    """تقسيم النص إلى أجزاء، كل جزء يحتوي على عدد محدد من الكلمات"""
    if not text: return []
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_words):
        chunk = " ".join(words[i:i+max_words])
        chunks.append(chunk)
    return chunks

def wrap_text(text, per_line):
    words = text.split()
    return '\n'.join([' '.join(words[i:i+per_line]) for i in range(0, len(words), per_line)])

def create_vignette_mask(w, h):
    Y, X = np.ogrid[:h, :w]
    mask = np.clip((np.sqrt((X - w/2)**2 + (Y - h/2)**2) / np.sqrt((w/2)**2 + (h/2)**2)) * 1.16, 0, 1) ** 3 
    mask_img = np.zeros((h, w, 4), dtype=np.uint8)
    mask_img[:, :, 3] = (mask * 255).astype(np.uint8)
    return ImageClip(mask_img, ismask=False)

# ==========================================
# 🎨 Updated Text Drawing Functions
# ==========================================

def create_text_clip(text, duration, target_w, scale_factor=1.0, glow=False, style=None, force_single_line=False):
    if style is None: style = {}
    
    color = style.get('arColor', '#ffffff')
    size_mult = float(style.get('arSize', '1.0'))
    stroke_c = style.get('arOutC', '#000000')
    stroke_w = int(style.get('arOutW', '4'))
    has_shadow = style.get('arShadow', False)
    shadow_c = style.get('arShadowC', '#000000')

    words = text.split()
    wc = len(words)
    
    # 🆕 تعديل هام: إذا كان النص قصيراً أو مطلوب سطر واحد، نمنع الالتفاف
    if force_single_line or wc <= 5:
        base_fs = 55 # خط أكبر قليلاً للنصوص القصيرة
        pl = 100 # رقم كبير لمنع التفاف النص
    elif wc > 60: base_fs, pl = 30, 12
    elif wc > 40: base_fs, pl = 35, 10
    elif wc > 25: base_fs, pl = 41, 9
    elif wc > 15: base_fs, pl = 46, 8
    else: base_fs, pl = 48, 7
    
    final_fs = int(base_fs * scale_factor * size_mult)
    font = get_cached_font(FONT_PATH_ARABIC, final_fs)

    wrapped_text = wrap_text(text, pl)
    lines = wrapped_text.split('\n')
    
    dummy = Image.new('RGBA', (target_w, 100))
    d = ImageDraw.Draw(dummy)
    line_metrics = []
    total_h = 0
    GAP = 15 * scale_factor * size_mult
    
    for l in lines:
        bbox = d.textbbox((0, 0), l, font=font, stroke_width=stroke_w)
        h = bbox[3] - bbox[1]
        line_metrics.append(h)
        total_h += h + GAP
        
    total_h += 40 
    
    img = Image.new('RGBA', (target_w, int(total_h)), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    curr_y = 20
    
    for i, line in enumerate(lines):
        w = draw.textbbox((0, 0), line, font=font, stroke_width=stroke_w)[2]
        x = (target_w - w) // 2
        
        if has_shadow:
            draw.text((x+4, curr_y+4), line, font=font, fill=shadow_c)

        if glow: 
            draw.text((x, curr_y), line, font=font, fill=(255,255,255,40), stroke_width=stroke_w+4, stroke_fill=(255,255,255,20))
        
        draw.text((x, curr_y), line, font=font, fill=color, stroke_width=stroke_w, stroke_fill=stroke_c)
        
        curr_y += line_metrics[i] + GAP
        
    # 🆕 تقليل مدة الـ crossfade للظهور الأسرع بين الكلمات
    return ImageClip(np.array(img)).set_duration(duration).crossfadein(0.1).crossfadeout(0.1)

def create_english_clip(text, duration, target_w, scale_factor=1.0, glow=False, style=None):
    if style is None: style = {}
    if not text: return ColorClip((target_w, 10), color=(0,0,0,0)).set_duration(duration)
    
    color = style.get('enColor', '#FFD700')
    size_mult = float(style.get('enSize', '1.0'))
    stroke_c = style.get('enOutC', '#000000')
    stroke_w = int(style.get('enOutW', '3'))
    has_shadow = style.get('enShadow', False)
    shadow_c = style.get('enShadowC', '#000000')

    final_fs = int(30 * scale_factor * size_mult)
    font = get_cached_font(FONT_PATH_ENGLISH, final_fs)
    
    h = int(250 * size_mult)
    img = Image.new('RGBA', (target_w, h), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    
    wrapped = wrap_text(text, 10)
    
    y_pos = 20
    
    if has_shadow:
        draw.text((target_w/2 + 2, y_pos + 2), wrapped, font=font, fill=shadow_c, align='center', anchor="ma")

    draw.text((target_w/2, y_pos), wrapped, font=font, fill=color, align='center', anchor="ma", stroke_width=stroke_w, stroke_fill=stroke_c)
    
    return ImageClip(np.array(img)).set_duration(duration).crossfadein(0.1).crossfadeout(0.1)

def fetch_video_pool(user_key, custom_query, count=1, job_id=None):
    pool = []
    if user_key and len(user_key) > 10: active_key = user_key
    else: active_key = random.choice(PEXELS_API_KEYS) if PEXELS_API_KEYS else ""
    
    SAFE_WHITELIST = [
        'nature', 'sky', 'sea', 'ocean', 'water', 'rain', 'cloud', 'mountain',
        'forest', 'tree', 'desert', 'sand', 'star', 'galaxy', 'space', 'moon',
        'sun', 'sunset', 'sunrise', 'mosque', 'islam', 'kaaba', 'makkah',
        'snow', 'winter', 'landscape', 'river', 'fog', 'mist', 'earth', 'bird', 'flowers'
    ]

    safe_topics = [
        'sky clouds timelapse', 'galaxy stars space', 'ocean waves slow motion', 
        'forest trees drone', 'desert sand dunes', 'waterfall nature', 
        'mountains fog', 'mosque architecture', 'islamic pattern', 'beautiful flowers'
    ]

    if custom_query and len(custom_query) > 2:
        try: 
            q_trans = GoogleTranslator(source='auto', target='en').translate(custom_query.strip()).lower()
            is_safe = any(safe_word in q_trans for safe_word in SAFE_WHITELIST)
            if is_safe: q = f"{q_trans} landscape scenery atmospheric no people"
            else: q = f"{random.choice(safe_topics)} no people"
        except: q = f"{random.choice(safe_topics)} no people"
    else:
        q = f"{random.choice(safe_topics)} no people"

    if active_key:
        try:
            check_stop(job_id)
            random_page = random.randint(1, 5)
            url = f"https://api.pexels.com/videos/search?query={q}&per_page={count+3}&page={random_page}&orientation=portrait"
            r = requests.get(url, headers={'Authorization': active_key}, timeout=15)
            if r.status_code == 200:
                vids = r.json().get('videos', [])
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
        except Exception as e: print(f"⚠️ Fetch Error: {e}")

    if not pool:
        print("🔄 Switching to Local Fallback...")
        try:
            local_files = [os.path.join(LOCAL_BGS_DIR, f) for f in os.listdir(LOCAL_BGS_DIR) if f.lower().endswith(('.mp4', '.mov', '.mkv'))]
            if local_files: pool = random.choices(local_files, k=count)
        except: pass
            
    return pool

# ==========================================
# ⚡ Optimized Video Builder (Segmented - The Big Change!)
# ==========================================
def build_video_task(job_id, user_pexels_key, reciter_id, surah, start, end, quality, bg_query, fps, dynamic_bg, use_glow, use_vignette, style):
    job = get_job(job_id)
    workspace = job['workspace']
    target_w, target_h = (1080, 1920) if quality == '1080' else (720, 1280)
    scale = 1.0 if quality == '1080' else 0.67
    last = min(end if end else start+9, VERSE_COUNTS.get(surah, 286))
    total_ayahs = (last - start) + 1
    
    try:
        # 1. Fetch Backgrounds
        # نحتاج خلفية واحدة على الأقل كاحتياط
        vpool = fetch_video_pool(user_pexels_key, bg_query, count=total_ayahs + 2, job_id=job_id)
        
        # 2. Prepare Base Background
        if not vpool:
            # لون ثابت في حال فشل كل شيء
            base_bg_clip = ColorClip((target_w, target_h), color=(15, 20, 35))
            bg_is_video = False
        else:
            # استخدام أول فيديو كخلفية أساسية
            base_bg_clip = VideoFileClip(vpool[0]).resize(height=target_h).crop(width=target_w, height=target_h, x_center=target_w/2, y_center=target_h/2)
            bg_is_video = True

        # 3. Prepare Static Overlays
        overlays_static = [ColorClip((target_w, target_h), color=(0,0,0)).set_opacity(0.3)]
        if use_vignette:
            overlays_static.append(create_vignette_mask(target_w, target_h))

        final_segments = []
        current_bg_time = 0.0
        bg_index = 0

        # 4. Sequential Processing (Ayah by Ayah)
        for i, ayah in enumerate(range(start, last+1)):
            check_stop(job_id)
            update_job_status(job_id, int((i / total_ayahs) * 70), f'Processing Ayah {ayah}...')

            # A. Get Full Verse Data (Audio & Text)
            full_audio_path = download_audio(reciter_id, surah, ayah, i, workspace, job_id)
            full_audioclip = AudioFileClip(full_audio_path)
            
            full_ar_text = get_text(surah, ayah)
            # تنظيف النص من رقم الآية للتقسيم
            clean_ar_text = full_ar_text.replace(f" ({ayah})", "")
            
            # B. Split Text into Chunks (4-5 words max)
            # 🆕 هنا يتم تقسيم النص
            ar_chunks = chunk_text_by_words(clean_ar_text, max_words=5)
            
            # C. Calculate Timing Proportions (Estimation based on character count)
            # 🆕 هنا يتم تقدير زمن كل جزء بناءً على عدد حروفه مقارنة بالإجمالي
            # حساب عدد الحروف (بدون مسافات) لتقدير أدق
            total_chars = len(clean_ar_text.replace(" ", ""))
            if total_chars == 0: total_chars = 1 # تجنب القسمة على صفر

            current_audio_start = 0.0
            ayah_sub_segments = []

            for chunk_idx, chunk_text in enumerate(ar_chunks):
                # 1. Calculate Chunk Duration
                chunk_chars = len(chunk_text.replace(" ", ""))
                
                # إذا كان هو الجزء الأخير، يأخذ كل الوقت المتبقي لضمان عدم ضياع أجزاء من الثانية
                if chunk_idx == len(ar_chunks) - 1:
                    chunk_duration = full_audioclip.duration - current_audio_start
                else:
                    # المعادلة: نسبة حروف الجزء / إجمالي الحروف * المدة الكلية
                    chunk_duration = (chunk_chars / total_chars) * full_audioclip.duration
                
                # حماية إضافية: تأكد أن المدة ليست صفر أو سالبة
                if chunk_duration <= 0.1: chunk_duration = 0.1

                # 2. Slice Audio
                # قص جزء الصوت المقابل لهذا النص
                chunk_audioclip = full_audioclip.subclip(current_audio_start, current_audio_start + chunk_duration)
                current_audio_start += chunk_duration

                # 3. Create Text Clips (Forced single line)
                # إضافة رقم الآية فقط في آخر جزء منها
                display_text = chunk_text
                if chunk_idx == len(ar_chunks) - 1:
                     display_text += f" ({ayah})"

                # 🆕 استخدام force_single_line=True
                ac_chunk = create_text_clip(display_text, chunk_duration, target_w, scale, use_glow, style=style, force_single_line=True)
                
                # (الترجمة الإنجليزية حالياً لا نقسمها لعدم وجود طريقة ربط دقيقة، نعرضها فارغة أو كاملة)
                # الأفضل حالياً عرضها فارغة للأجزاء المقسمة لتجنب التشتت، أو يمكن تطويرها لاحقاً
                ec_chunk = create_english_clip("", chunk_duration, target_w, scale, use_glow, style=style)

                # Positioning
                ar_size_mult = float(style.get('arSize', '1.0'))
                base_y = 0.35 # تمركز أفضل في المنتصف
                ar_y_pos = target_h * base_y
                ac_chunk = ac_chunk.set_position(('center', ar_y_pos))

                # 4. Handle Background Slice for this Chunk
                if dynamic_bg and bg_is_video and bg_index < len(vpool):
                    # خلفية متغيرة: نستخدم فيديو جديد لكل آية (ولليس لكل جزء من الآية)
                    # إذا كنا في أول جزء من الآية، نجهز الخلفية الجديدة
                    if chunk_idx == 0:
                         current_bg_clip = VideoFileClip(vpool[bg_index]).resize(height=target_h).crop(width=target_w, height=target_h, x_center=target_w/2, y_center=target_h/2)
                         if current_bg_clip.duration < full_audioclip.duration: current_bg_clip = current_bg_clip.loop(duration=full_audioclip.duration)
                         bg_slice_start = 0.0
                    
                    bg_slice = current_bg_clip.subclip(bg_slice_start, bg_slice_start + chunk_duration).set_duration(chunk_duration)
                    bg_slice_start += chunk_duration
                    
                    # تأثير انتقال ناعم فقط في أول جزء من الآية
                    if chunk_idx == 0: bg_slice = bg_slice.fadein(0.5)
                    if chunk_idx == len(ar_chunks) -1: bg_index += 1 # الانتقال للخلفية التالية بعد انتهاء الآية

                else:
                    # خلفية ثابتة: استمرار الفيديو الأساسي
                    if bg_is_video:
                        bg_slice = base_bg_clip.loop().subclip(current_bg_time, current_bg_time + chunk_duration).set_duration(chunk_duration)
                    else:
                        bg_slice = base_bg_clip.set_duration(chunk_duration)
                    current_bg_time += chunk_duration
                
                # 5. Compose Chunk Segment
                segment_overlays = [o.set_duration(chunk_duration) for o in overlays_static]
                chunk_segment = CompositeVideoClip([bg_slice] + segment_overlays + [ac_chunk, ec_chunk]).set_audio(chunk_audioclip)
                ayah_sub_segments.append(chunk_segment)
            
            # تجميع أجزاء الآية الواحدة
            if ayah_sub_segments:
                final_segments.extend(ayah_sub_segments)
            
            # تنظيف الذاكرة بعد كل آية
            full_audioclip.close()
            del full_audioclip
            gc.collect()

        # 5. Concatenate All Segments
        update_job_status(job_id, 85, "Merging Clips...")
        final_video = concatenate_videoclips(final_segments, method="compose")
        
        out_p = os.path.join(workspace, f"out_{job_id}.mp4")
        temp_mix_path = os.path.join(workspace, f"temp_mix_{job_id}.mp4")
        
        # ==========================================
        # 6. The "Studio Dry" Workflow
        # ==========================================
        STUDIO_DRY_FILTER = (
            "highpass=f=60, "
            "equalizer=f=200:width_type=h:width=200:g=3, "
            "equalizer=f=8000:width_type=h:width=1000:g=2, "
            "acompressor=threshold=-21dB:ratio=4:attack=200:release=1000, "
            "extrastereo=m=1.3, "
            "loudnorm=I=-16:TP=-1.5:LRA=11"
        )
        
        update_job_status(job_id, 90, "Rendering Video...")
        final_video.write_videofile(
            temp_mix_path, fps=fps, codec='libx264', audio_codec='aac', audio_bitrate='192k',
            preset='ultrafast', threads=os.cpu_count() or 4, logger=ScopedQuranLogger(job_id)
        )

        update_job_status(job_id, 98, "Mastering Audio...")
        cmd = (f'ffmpeg -y -i "{temp_mix_path}" -af "{STUDIO_DRY_FILTER}" -c:v copy -c:a aac -b:a 192k "{out_p}"')
        if os.system(cmd) != 0: 
            # في حال فشل الفلتر، استخدم الملف الأصلي
            shutil.move(temp_mix_path, out_p)
        else:
             if os.path.exists(temp_mix_path): os.remove(temp_mix_path)

        with JOBS_LOCK: 
            JOBS[job_id].update({'output_path': out_p, 'is_complete': True, 'is_running': False, 'percent': 100, 'status': "Done!"})

    except Exception as e:
        msg = str(e)
        traceback.print_exc()
        status = "Cancelled" if "Stopped" in msg else "Error"
        with JOBS_LOCK: JOBS[job_id].update({'error': msg, 'status': status, 'is_running': False})
    
    finally:
        # تنظيف شامل للموارد
        try:
            if 'final_video' in locals() and final_video: final_video.close()
            if 'base_bg_clip' in locals() and base_bg_clip: base_bg_clip.close()
            if 'vpool' in locals():
                 for v in vpool: 
                     try: VideoFileClip(v).close() 
                     except: pass
            for s in final_segments: 
                try: s.close() 
                except: pass
        except: pass
        gc.collect()

@app.route('/')
def ui(): return send_file(UI_PATH) if os.path.exists(UI_PATH) else "API Running"

@app.route('/api/generate', methods=['POST'])
def gen():
    d = request.json
    job_id = create_job()
    style_settings = d.get('style', {}) 
    threading.Thread(
        target=build_video_task, 
        args=(
            job_id, d.get('pexelsKey'), d['reciter'], int(d['surah']), 
            int(d['startAyah']), int(d.get('endAyah',0)), d.get('quality','720'), 
            d.get('bgQuery',''), int(d.get('fps',20)), d.get('dynamicBg',False), 
            d.get('useGlow',False), d.get('useVignette',False), style_settings
        ), daemon=True
    ).start()
    return jsonify({'ok': True, 'jobId': job_id})

@app.route('/api/progress')
def prog(): return jsonify(get_job(request.args.get('jobId')))

@app.route('/api/download')
def download_result(): 
    job = get_job(request.args.get('jobId'))
    if job and job.get('output_path') and os.path.exists(job['output_path']):
        return send_file(job['output_path'], as_attachment=True)
    return "File not found", 404

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

def background_cleanup():
    while True:
        time.sleep(3600)
        current_time = time.time()
        with JOBS_LOCK:
            to_delete = []
            for jid, job in JOBS.items():
                if current_time - job['created_at'] > 3600: to_delete.append(jid)
            for jid in to_delete: del JOBS[jid]
        try:
            if os.path.exists(BASE_TEMP_DIR):
                for folder in os.listdir(BASE_TEMP_DIR):
                    folder_path = os.path.join(BASE_TEMP_DIR, folder)
                    if os.path.isdir(folder_path):
                        if current_time - os.path.getctime(folder_path) > 3600: shutil.rmtree(folder_path, ignore_errors=True)
        except: pass

threading.Thread(target=background_cleanup, daemon=True).start()

if __name__ == "__main__":
    # تأكد من أن اسم ملف الـ HTML صحيح
    if not os.path.exists(UI_PATH):
        print(f"⚠️ Warning: UI file not found at {UI_PATH}")
        
    app.run(host='0.0.0.0', port=8000, threaded=True)

