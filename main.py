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
from functools import lru_cache  # ✅ Added for caching
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
    "aecho=0.8:0.9:60|1000:0.4|0.2, "  # 🚨 FIXED: Used '|' instead of ':'
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

PEXELS_API_KEYS = [
    "AmAgE0J5AuBbsvR6dmG7qQLIc5uYZvDim2Vx250F5QoHNKnGdCofFerx",
    "Fv0qzUGYwbGr6yHsauaXuNKiNR9L7OE7VLr5Wq6SngcLjavmkCEAskb2",
    "1NK8BaBXGsXm4Uxzcesxm0Jxh2yCILOwqqsj4GiM57dXcb7b8bbDYyOu",
    
 "C9KJNtJET2wAnmD42Gbu0OolTlmhoT02CX7fyst3kKEvnjRRWLiAqQ9t" 
]

LOCAL_BGS_DIR = os.path.join(BUNDLE_DIR, "local_bgs")
os.makedirs(LOCAL_BGS_DIR, exist_ok=True)
# 💡 ملحوظة: ابقى اعمل فولدر اسمه local_bgs وحط فيه كام فيديو خلفية للطوارئ

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
os.makedirs(BASE_TEMP_DIR, exist_ok=True)
os.makedirs(VISION_DIR, exist_ok=True)

# Data Constants
VERSE_COUNTS = {1: 7, 2: 286, 3: 200, 4: 176, 5: 120, 6: 165, 7: 206, 8: 75, 9: 129, 10: 109, 11: 123, 12: 111, 13: 43, 14: 52, 15: 99, 16: 128, 17: 111, 18: 110, 19: 98, 20: 135, 21: 112, 22: 78, 23: 118, 24: 64, 25: 77, 26: 227, 27: 93, 28: 88, 29: 69, 30: 60, 31: 34, 32: 30, 33: 73, 34: 54, 35: 45, 36: 83, 37: 182, 38: 88, 39: 75, 40: 85, 41: 54, 42: 53, 43: 89, 44: 59, 45: 37, 46: 35, 47: 38, 48: 29, 49: 18, 50: 45, 51: 60, 52: 49, 53: 62, 54: 55, 55: 78, 56: 96, 57: 29, 58: 22, 59: 24, 60: 13, 61: 14, 62: 11, 63: 11, 64: 18, 65: 12, 66: 12, 67: 30, 68: 52, 69: 52, 70: 44, 71: 28, 72: 28, 73: 20, 74: 56, 75: 40, 76: 31, 77: 50, 78: 40, 79: 46, 80: 42, 81: 29, 82: 19, 83: 36, 84: 25, 85: 22, 86: 17, 87: 19, 88: 26, 89: 30, 90: 20, 91: 15, 92: 21, 93: 11, 94: 8, 95: 8, 96: 19, 97: 5, 98: 8, 99: 8, 100: 11, 101: 11, 102: 8, 103: 3, 104: 9, 105: 5, 106: 4, 107: 7, 108: 3, 109: 6, 110: 3, 111: 5, 112: 4, 113: 5, 114: 6}
SURAH_NAMES = ['الفاتحة', 'البقرة', 'آل عمران', 'النساء', 'المائدة', 'الأنعام', 'الأعراف', 'الأنفال', 'التوبة', 'يونس', 'هود', 'يوسف', 'الرعد', 'إبراهيم', 'الحجر', 'النحل', 'الإسراء', 'الكهف', 'مريم', 'طه', 'الأنبياء', 'الحج', 'المؤمنون', 'النور', 'الفرقان', 'الشعراء', 'النمل', 'القصص', 'العنكبوت', 'الروم', 'لقمان', 'السجدة', 'الأحزاب', 'سبأ', 'فاطر', 'يس', 'الصافات', 'ص', 'الزمر', 'غافر', 'فصلت', 'الشورى', 'الزخرف', 'الدخان', 'الجاثية', 'الأحقاف', 'محمد', 'الفتح', 'الحجرات', 'ق', 'الذاريات', 'الطور', 'النجم', 'القمر', 'الرحمن', 'الواقعة', 'الحديد', 'المجادلة', 'الحشر', 'الممتحنة', 'الصف', 'الجمعة', 'المنافقون', 'التغابن', 'الطلاق', 'التحريم', 'الملك', 'القلم', 'الحاقة', 'المعارج', 'نوح', 'الجن', 'المزمل', 'المدثر', 'القيامة', 'الإنسان', 'المرسلات', 'النبأ', 'النازعات', 'عبس', 'التكوير', 'الانفطار', 'المطففين', 'الانشقاق', 'البروج', 'الطارق', 'الأعلى', 'الغاشية', 'الفجر', 'البلد', 'الشمس', 'الليل', 'الضحى', 'الشرح', 'التين', 'العلق', 'القدر', 'البينة', 'الزلزلة', 'العاديات', 'القارعة', 'التكاثر', 'العصر', 'الهمزة', 'الفيل', 'قريش', 'الماعون', 'الكوثر', 'الكافرون', 'النصر', 'المسد', 'الإخلاص', 'الفلق', 'الناس']

# 🚀 Reciters Config
NEW_RECITERS_CONFIG = {
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
        return ImageFont.load_default()

def detect_silence(sound, thresh):
    t = 0
    while t < len(sound) and sound[t:t+10].dBFS < thresh: t += 10
    return t

def smart_download(url, dest_path, job_id):
    check_stop(job_id)
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

def process_mp3quran_audio(reciter_name, surah, ayah, idx, workspace_dir, job_id):
    reciter_id, server_url = NEW_RECITERS_CONFIG[reciter_name]
    cache_dir = os.path.join(EXEC_DIR, "cache_mp3quran", str(reciter_id))
    os.makedirs(cache_dir, exist_ok=True)
    full_audio_path = os.path.join(cache_dir, f"{surah:03d}.mp3")
    timings_path = os.path.join(cache_dir, f"{surah:03d}.json")

    # [Download Logic Remains the Same...]
    if not os.path.exists(full_audio_path) or not os.path.exists(timings_path):
        smart_download(f"{server_url}{surah:03d}.mp3", full_audio_path, job_id)
        check_stop(job_id)
        t_data = requests.get(f"https://mp3quran.net/api/v3/ayat_timing?surah={surah}&read={reciter_id}").json()
        timings = {item['ayah']: {'start': item['start_time'], 'end': item['end_time']} for item in t_data}
        with open(timings_path, 'w') as f: json.dump(timings, f)

    with open(timings_path, 'r') as f:
        t = json.load(f)[str(ayah)]
    
    check_stop(job_id)
    
    # 1. Load the raw segment based on API timestamps
    seg = AudioSegment.from_file(full_audio_path)[t['start']:t['end']]
    
    # ---------------------------------------------------------
    # 🚀 NEW: SILENCE REMOVAL LOGIC
    # ---------------------------------------------------------
    
    # Dynamic threshold: 16dB quieter than the peak of this specific clip
    silence_thresh = seg.dBFS - 16 

    # Find where the sound actually starts
    start_trim = detect_leading_silence(seg, silence_threshold=silence_thresh)
    
    # Find where the sound actually ends (by reversing audio)
    end_trim = detect_leading_silence(seg.reverse(), silence_threshold=silence_thresh)
    
    # Calculate duration
    duration = len(seg)
    
    # Safety check: prevent trimming the whole file if it's very short or quiet
    if duration - start_trim - end_trim > 200: 
        seg = seg[start_trim:duration-end_trim]
    
    # Add a tighter fade to ensure smoothness without gaps
    # Reduced fade from 50ms to 20ms to keep it snappy
    seg = seg.fade_in(20).fade_out(20) 
    
    # ---------------------------------------------------------

    out = os.path.join(workspace_dir, f'part{idx}.mp3')
    seg.export(out, format="mp3")
    return out

def detect_leading_silence(sound, silence_threshold=-50.0, chunk_size=10):
    '''
    sound is a pydub.AudioSegment
    silence_threshold in dB
    chunk_size in ms
    iterate over chunks until you find the first one with sound
    '''
    trim_ms = 0 # ms
    assert chunk_size > 0 # to avoid infinite loop
    while trim_ms < len(sound) and sound[trim_ms:trim_ms+chunk_size].dBFS < silence_threshold:
        trim_ms += chunk_size

    return trim_ms

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

# ==========================================
# 🎨 Updated Text Drawing Functions (Supports Custom Styles)
# ==========================================

def create_text_clip(text, duration, target_w, scale_factor=1.0, glow=False, style=None):
    # 1. Setup Defaults if style is missing
    if style is None: style = {}
    
    color = style.get('arColor', '#ffffff')
    size_mult = float(style.get('arSize', '1.0'))
    stroke_c = style.get('arOutC', '#000000')
    stroke_w = int(style.get('arOutW', '4'))
    has_shadow = style.get('arShadow', False)
    shadow_c = style.get('arShadowC', '#000000')

    # 2. Font Sizing
    words = text.split()
    wc = len(words)
    
    if wc > 60: base_fs, pl = 30, 12
    elif wc > 40: base_fs, pl = 35, 10
    elif wc > 25: base_fs, pl = 41, 9
    elif wc > 15: base_fs, pl = 46, 8
    else: base_fs, pl = 48, 7
    
    # Apply user size multiplier
    final_fs = int(base_fs * scale_factor * size_mult)
    font = get_cached_font(FONT_PATH_ARABIC, final_fs)

    wrapped_text = wrap_text(text, pl)
    lines = wrapped_text.split('\n')
    
    # 3. Measure Text
    dummy = Image.new('RGBA', (target_w, 100))
    d = ImageDraw.Draw(dummy)
    line_metrics = []
    total_h = 0
    GAP = 15 * scale_factor * size_mult # Dynamic Gap
    
    for l in lines:
        bbox = d.textbbox((0, 0), l, font=font, stroke_width=stroke_w)
        h = bbox[3] - bbox[1]
        line_metrics.append(h)
        total_h += h + GAP
        
    total_h += 40 
    
    # 4. Draw
    img = Image.new('RGBA', (target_w, int(total_h)), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    curr_y = 20
    
    for i, line in enumerate(lines):
        w = draw.textbbox((0, 0), line, font=font, stroke_width=stroke_w)[2]
        x = (target_w - w) // 2
        
        # A. Shadow (Optional)
        if has_shadow:
            draw.text((x+4, curr_y+4), line, font=font, fill=shadow_c)

        # B. Glow (Optional)
        if glow: 
            draw.text((x, curr_y), line, font=font, fill=(255,255,255,40), stroke_width=stroke_w+4, stroke_fill=(255,255,255,20))
        
        # C. Main Text with Stroke
        draw.text((x, curr_y), line, font=font, fill=color, stroke_width=stroke_w, stroke_fill=stroke_c)
        
        curr_y += line_metrics[i] + GAP
        
    # 🚀 استخدمنا crossfade عشان نتحكم في الشفافية (Alpha) مش اللون الأسود
    return ImageClip(np.array(img)).set_duration(duration).crossfadein(0.35).crossfadeout(0.35)

def create_english_clip(text, duration, target_w, scale_factor=1.0, glow=False, style=None):
    if style is None: style = {}
    
    color = style.get('enColor', '#FFD700')
    size_mult = float(style.get('enSize', '1.0'))
    stroke_c = style.get('enOutC', '#000000')
    stroke_w = int(style.get('enOutW', '3'))
    has_shadow = style.get('enShadow', False)
    shadow_c = style.get('enShadowC', '#000000')

    final_fs = int(30 * scale_factor * size_mult)
    font = get_cached_font(FONT_PATH_ENGLISH, final_fs)
    
    # Estimated height based on font size (approx 3 lines max)
    h = int(250 * size_mult)
    img = Image.new('RGBA', (target_w, h), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    
    wrapped = wrap_text(text, 10)
    
    # Center text roughly
    y_pos = 20
    
    # Shadow
    if has_shadow:
        draw.text((target_w/2 + 2, y_pos + 2), wrapped, font=font, fill=shadow_c, align='center', anchor="ma")

    # Main Text
    draw.text((target_w/2, y_pos), wrapped, font=font, fill=color, align='center', anchor="ma", stroke_width=stroke_w, stroke_fill=stroke_c)
    
    # 🚀 نفس الكلام هنا للترجمة
    return ImageClip(np.array(img)).set_duration(duration).crossfadein(0.35).crossfadeout(0.35)
    
def fetch_video_pool(user_key, custom_query, count=1, job_id=None):
    pool = []
    
    # 1. قائمة الممنوعات (الكلمات اللي لو ظهرت في وصف الفيديو نرفضه)
    FORBIDDEN_TAGS = [
        'woman', 'girl', 'female', 'lady', 'model', 'face', 'people', 'person', 
        'man', 'boy', 'couple', 'fashion', 'dance', 'yoga', 'fitness', 'body',
        'portrait', 'smile', 'happy', 'human', 'crowd', 'street', 'walking'
    ]

    # 2. تحديد المفتاح
    if user_key and len(user_key) > 10:
        active_key = user_key
    else:
        active_key = random.choice(PEXELS_API_KEYS) if PEXELS_API_KEYS else ""
    
    # 3. نظام القائمة البيضاء (الصارم) 🛡️
    SAFE_WHITELIST = [
        'nature', 'sky', 'sea', 'ocean', 'water', 'rain', 'cloud', 'mountain',
        'forest', 'tree', 'desert', 'sand', 'star', 'galaxy', 'space', 'moon',
        'sun', 'sunset', 'sunrise', 'mosque', 'islam', 'kaaba', 'makkah',
        'snow', 'winter', 'landscape', 'river', 'fog', 'mist', 'earth', 'bird'
    ]

    safe_topics = [
        'sky clouds timelapse', 'galaxy stars space', 'ocean waves slow motion', 
        'forest trees drone', 'desert sand dunes', 'waterfall nature', 
        'mountains fog', 'mosque architecture', 'islamic pattern'
    ]

    if custom_query and len(custom_query) > 2:
        try: 
            # بنترجم كلمة المستخدم للإنجليزي ونخليها حروف صغيرة
            q_trans = GoogleTranslator(source='auto', target='en').translate(custom_query.strip()).lower()
            
            # 🛑 الفحص: هل كلمته موجودة في القائمة البيضاء؟
            is_safe = any(safe_word in q_trans for safe_word in SAFE_WHITELIST)
            
            if is_safe:
                # الكلمة أمان، استخدمها
                q = f"{q_trans} landscape scenery atmospheric no people"
            else:
def fetch_video_pool(user_key, custom_query, count=1, job_id=None):
    pool = []
    
    # 1. تحديد المفتاح
    if user_key and len(user_key) > 10:
        active_key = user_key
    else:
        active_key = random.choice(PEXELS_API_KEYS) if PEXELS_API_KEYS else ""
    
    # 2. نظام القائمة البيضاء (الصارم) 🛡️
    SAFE_WHITELIST = [
        'nature', 'sky', 'sea', 'ocean', 'water', 'rain', 'cloud', 'mountain',
        'forest', 'tree', 'desert', 'sand', 'star', 'galaxy', 'space', 'moon',
        'sun', 'sunset', 'sunrise', 'mosque', 'islam', 'kaaba', 'makkah',
        'snow', 'winter', 'landscape', 'river', 'fog', 'mist', 'earth', 'bird'
    ]

    safe_topics = [
        'sky clouds timelapse', 'galaxy stars space', 'ocean waves slow motion', 
        'forest trees drone', 'desert sand dunes', 'waterfall nature', 
        'mountains fog', 'mosque architecture', 'islamic pattern'
    ]

    # 3. معالجة كلمة البحث
    if custom_query and len(custom_query) > 2:
        try: 
            q_trans = GoogleTranslator(source='auto', target='en').translate(custom_query.strip()).lower()
            is_safe = any(safe_word in q_trans for safe_word in SAFE_WHITELIST)
            
            if is_safe:
                q = f"{q_trans} landscape scenery atmospheric no people"
            else:
                print(f"🚫 تم رفض كلمة البحث ({q_trans}) لأنها خارج القائمة البيضاء.")
                q = f"{random.choice(safe_topics)} no people"
        except: 
            q = f"{random.choice(safe_topics)} no people"
    else:
        q = f"{random.choice(safe_topics)} no people"

    # 4. محاولة الجلب من Pexels API
    if active_key:
        try:
            check_stop(job_id)
            random_page = random.randint(1, 10)
            url = f"https://api.pexels.com/videos/search?query={q}&per_page={count+5}&page={random_page}&orientation=portrait"
            
            r = requests.get(url, headers={'Authorization': active_key}, timeout=10)
            
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
                        if not os.path.exists(path):
                            smart_download(f['link'], path, job_id)
                        pool.append(path)
            else:
                print(f"⚠️ Pexels API Error: {r.status_code}")
        except Exception as e:
            print(f"⚠️ Fetch Error: {e}")

    # 5. نظام الطوارئ (Local Fallback)
    if not pool:
        print("🔄 Switching to Local Fallback...")
        try:
            local_files = [os.path.join(LOCAL_BGS_DIR, f) for f in os.listdir(LOCAL_BGS_DIR) if f.lower().endswith(('.mp4', '.mov', '.mkv'))]
            if local_files:
                pool = random.choices(local_files, k=count)
        except Exception as e:
            print(f"❌ Local Fallback Error: {e}")
            
    return pool
# ==========================================
# ⚡ Optimized Video Builder (Segmented)
# ==========================================
def build_video_task(job_id, user_pexels_key, reciter_id, surah, start, end, quality, bg_query, fps, dynamic_bg, use_glow, use_vignette, style):
    job = get_job(job_id)
    workspace = job['workspace']
    target_w, target_h = (1080, 1920) if quality == '1080' else (720, 1280)
    scale = 1.0 if quality == '1080' else 0.67
    last = min(end if end else start+9, VERSE_COUNTS.get(surah, 286))
    total_ayahs = (last - start) + 1
    
    try:
        # 1. Fetch Backgrounds immediately
        vpool = fetch_video_pool(user_pexels_key, bg_query, count=total_ayahs if dynamic_bg else 1, job_id=job_id)
        
        # 2. Prepare Base Background (Load once)
        if not vpool:
            base_bg_clip = ColorClip((target_w, target_h), color=(15, 20, 35)).set_duration(1)
        else:
            base_bg_clip = VideoFileClip(vpool[0]).resize(height=target_h).crop(width=target_w, height=target_h, x_center=target_w/2, y_center=target_h/2)

        # 3. Prepare Static Overlays (Create once)
        overlays_static = [ColorClip((target_w, target_h), color=(0,0,0)).set_opacity(0.3)]
        if use_vignette:
            overlays_static.append(create_vignette_mask(target_w, target_h))

        segments = []
        current_bg_time = 0.0
        
        # 4. Sequential Processing (Ayah by Ayah)
        for i, ayah in enumerate(range(start, last+1)):
            check_stop(job_id)
            update_job_status(job_id, int((i / total_ayahs) * 80), f'Processing Ayah {ayah}...')

            # A. Audio
            ap = download_audio(reciter_id, surah, ayah, i, workspace, job_id)
            audioclip = AudioFileClip(ap)
            duration = audioclip.duration

            # B. Text (Updated to use Style)
            ar_text = f"{get_text(surah, ayah)} ({ayah})"
            en_text = get_en_text(surah, ayah)
            
            # 🚨 تمرير الـ style هنا هو السر!
            ac = create_text_clip(ar_text, duration, target_w, scale, use_glow, style=style)
            ec = create_english_clip(en_text, duration, target_w, scale, use_glow, style=style)

            # Positioning (Dynamic based on size)
            # نقوم بحساب المكان بناءً على حجم الخط المختار لضمان التناسق
            ar_size_mult = float(style.get('arSize', '1.0'))
            
            # نرفع النص العربي قليلاً إذا كان الخط كبيراً جداً
            base_y = 0.32
            if ar_size_mult > 1.2: base_y = 0.28 
            
            ar_y_pos = target_h * base_y
            en_y_pos = ar_y_pos + ac.h + (10 * scale)
            
            ac = ac.set_position(('center', ar_y_pos))
            ec = ec.set_position(('center', en_y_pos))

            # C. Background Slice
            if dynamic_bg and i < len(vpool):
                # 🔄 حالة الخلفية المتغيرة: نستخدم فيديو جديد ونعمله Fade
                bg_clip = VideoFileClip(vpool[i]).resize(height=target_h).crop(width=target_w, height=target_h, x_center=target_w/2, y_center=target_h/2)
                
                if bg_clip.duration < duration:
                    bg_clip = bg_clip.loop(duration=duration)
                else:
                    max_start = max(0, bg_clip.duration - duration)
                    start_t = random.uniform(0, max_start)
                    bg_clip = bg_clip.subclip(start_t, start_t + duration)
                
                # الـ Fade يطبق هنا فقط لأنها خلفية متغيرة
                bg_clip = bg_clip.set_duration(duration).fadein(0.5).fadeout(0.5)
                
            else:
                # 🚀 حالة الخلفية الثابتة: استمرار الفيديو كقطعة واحدة بدون أي Fade أو تقطيع عشوائي
                bg_clip = base_bg_clip.loop().subclip(current_bg_time, current_bg_time + duration)
                current_bg_time += duration  # نزود الوقت عشان الآية الجاية تكمل من مكان ما دي وقفت
                bg_clip = bg_clip.set_duration(duration)
                # ❌ لا يوجد fadein أو fadeout هنا إطلاقاً!
            
            # Apply overlays to this segment
            segment_overlays = [o.set_duration(duration) for o in overlays_static]
            
            # D. Compose Segment
            # 🚀 تم إزالة الـ fadeout الخارجي لضمان تواصل التلاوة (النَفَس) بدون سكون بين الآيات
            segment = CompositeVideoClip([bg_clip] + segment_overlays + [ac, ec]).set_audio(audioclip)
            segments.append(segment)

        # 5. Concatenate
        update_job_status(job_id, 85, "Merging Clips...")
        final_video = concatenate_videoclips(segments, method="compose")
        
        out_p = os.path.join(workspace, f"out_{job_id}.mp4")
        
        # ==========================================
        # 6. The "Studio Dry" Workflow (Clean & Crisp)
        # ==========================================

        # فلتر "استوديو خام" - نقي جداً وبدون صدى
        # Highpass: إزالة التشويش | Compressor: توحيد الصوت | EQ: تحسين الخامة
        # تمت إزالة (aecho) نهائياً ❌
        STUDIO_DRY_FILTER = (
            "highpass=f=60, "                                 # تنظيف الضوضاء المنخفضة
            "equalizer=f=200:width_type=h:width=200:g=3, "    # إضافة فخامة (Warmth)
            "equalizer=f=8000:width_type=h:width=1000:g=2, "  # إضافة وضوح (Clarity)
            "acompressor=threshold=-21dB:ratio=4:attack=200:release=1000, " # توحيد ارتفاع الصوت
            "extrastereo=m=1.3, "                             # توزيع الصوت يمين ويسار قليلاً
            "loudnorm=I=-16:TP=-1.5:LRA=11"                   # ضبط المعايير العالمية (Loudness)
        )
        
        # --- A. Render Clean Video (Mix) ---
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

        # --- B. Apply Dry Mastering ---
        update_job_status(job_id, 95, "Mastering Audio (Dry Studio)...")
        
        cmd = (
            f'ffmpeg -y -i "{temp_mix_path}" '
            f'-af "{STUDIO_DRY_FILTER}" '
            f'-c:v copy '
            f'-c:a aac -b:a 192k '
            f'"{out_p}"'
        )
        
        if os.system(cmd) != 0: raise Exception("FFmpeg Mastering Failed")

        if os.path.exists(temp_mix_path): os.remove(temp_mix_path)

        with JOBS_LOCK: 
            JOBS[job_id].update({'output_path': out_p, 'is_complete': True, 'is_running': False, 'percent': 100, 'status': "Done!"})

        # --- B. Apply The Golden Mastering ---
        update_job_status(job_id, 95, "Mastering Audio (Golden Preset)...")
        
        # تطبيق الفلتر باستخدام FFmpeg مباشرة للسرعة والجودة
        cmd = (
            f'ffmpeg -y -i "{temp_mix_path}" '
            f'-af "{MODERATE_AUDIO_FILTER}" '
            f'-c:v copy '
            f'-c:a aac -b:a 192k '
            f'"{out_p}"'
        )
        
        if os.system(cmd) != 0: raise Exception("FFmpeg Mastering Failed")

        # تنظيف الملف المؤقت
        if os.path.exists(temp_mix_path): os.remove(temp_mix_path)

        with JOBS_LOCK: 
            JOBS[job_id].update({'output_path': out_p, 'is_complete': True, 'is_running': False, 'percent': 100, 'status': "Done!"})

        # --- C. Apply Dynamic Mastering ---
        update_job_status(job_id, 95, f"Mastering Audio (Warmth:{warmth_val}% Clarity:{clarity_val}%)...")
        
        cmd = (
            f'ffmpeg -y -i "{temp_mix_path}" '
            f'-af "{CUSTOM_AUDIO_FILTER}" '
            f'-c:v copy '
            f'-c:a aac -b:a 192k '
            f'"{out_p}"'
        )
        
        if os.system(cmd) != 0: raise Exception("FFmpeg Mastering Failed")

        if os.path.exists(temp_mix_path): os.remove(temp_mix_path)

        with JOBS_LOCK: 
            JOBS[job_id].update({'output_path': out_p, 'is_complete': True, 'is_running': False, 'percent': 100, 'status': "Done!"})    
    
    except Exception as e:
        msg = str(e)
        traceback.print_exc()
        status = "Cancelled" if msg == "Stopped" else "Error"
        with JOBS_LOCK: JOBS[job_id].update({'error': msg, 'status': status, 'is_running': False})
    
    finally:
        try:
            if 'final_video' in locals(): final_video.close()
            if 'base_bg_clip' in locals(): base_bg_clip.close()
            for s in segments: s.close()
        except: pass
        gc.collect()

@app.route('/')
def ui(): return send_file(UI_PATH) if os.path.exists(UI_PATH) else "API Running"

@app.route('/api/generate', methods=['POST'])
def gen():
    d = request.json
    job_id = create_job()
    
    # 1. Extract the style object (contains audio settings)
    style_settings = d.get('style', {}) 
    
    # 2. Pass it to the thread (Add it as the LAST argument)
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
            style_settings  # <--- CRITICAL: This must be here!
        ), 
        daemon=True
    ).start()
    
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
    app.run(host='0.0.0.0', port=8000, threaded=True)












