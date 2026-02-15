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
import re
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

# Media Processing Imports
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

from moviepy.editor import ImageClip, VideoFileClip, AudioFileClip, CompositeVideoClip, ColorClip
import moviepy.video.fx.all as vfx
from moviepy.config import change_settings
from proglog import ProgressBarLogger
from pydub import AudioSegment
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

FONT_DIR = os.path.join(EXEC_DIR, "fonts")
FONT_PATH_ARABIC = os.path.join(FONT_DIR, "Arabic.ttf") 
FONT_PATH_ENGLISH = os.path.join(FONT_DIR, "English.otf")
VISION_DIR = os.path.join(BUNDLE_DIR, "vision")
UI_PATH = os.path.join(BUNDLE_DIR, "UI.html")
BASE_TEMP_DIR = os.path.join(EXEC_DIR, "temp_workspaces")

for d in [BASE_TEMP_DIR, VISION_DIR, FONT_DIR]:
    os.makedirs(d, exist_ok=True)

# Data Constants
VERSE_COUNTS = {1: 7, 2: 286, 3: 200, 4: 176, 5: 120, 6: 165, 7: 206, 8: 75, 9: 129, 10: 109, 11: 123, 12: 111, 13: 43, 14: 52, 15: 99, 16: 128, 17: 111, 18: 110, 19: 98, 20: 135, 21: 112, 22: 78, 23: 118, 24: 64, 25: 77, 26: 227, 27: 93, 28: 88, 29: 69, 30: 60, 31: 34, 32: 30, 33: 73, 34: 54, 35: 45, 36: 83, 37: 182, 38: 88, 39: 75, 40: 85, 41: 54, 42: 53, 43: 89, 44: 59, 45: 37, 46: 35, 47: 38, 48: 29, 49: 18, 50: 45, 51: 60, 52: 49, 53: 62, 54: 55, 55: 78, 56: 96, 57: 29, 58: 22, 59: 24, 60: 13, 61: 14, 62: 11, 63: 11, 64: 18, 65: 12, 66: 12, 67: 30, 68: 52, 69: 52, 70: 44, 71: 28, 72: 28, 73: 20, 74: 56, 75: 40, 76: 31, 77: 50, 78: 40, 79: 46, 80: 42, 81: 29, 82: 19, 83: 36, 84: 25, 85: 22, 86: 17, 87: 19, 88: 26, 89: 30, 90: 20, 91: 15, 92: 21, 93: 11, 94: 8, 95: 8, 96: 19, 97: 5, 98: 8, 99: 8, 100: 11, 101: 11, 102: 8, 103: 3, 104: 9, 105: 5, 106: 4, 107: 7, 108: 3, 109: 6, 110: 3, 111: 5, 112: 4, 113: 5, 114: 6}
SURAH_NAMES = ['الفاتحة', 'البقرة', 'آل عمران', 'النساء', 'المائدة', 'الأنعام', 'الأعراف', 'الأنفال', 'التوبة', 'يونس', 'هود', 'يوسف', 'الرعد', 'إبراهيم', 'الحجر', 'النحل', 'الإسراء', 'الكهف', 'مريم', 'طه', 'الأنبياء', 'الحج', 'المؤمنون', 'النور', 'الفرقان', 'الشعراء', 'النمل', 'القصص', 'العنكبوت', 'الروم', 'لقمان', 'السجدة', 'الأحزاب', 'سبأ', 'فاطر', 'يس', 'الصافات', 'ص', 'الزمر', 'غافر', 'فصلت', 'الشورى', 'الزخرف', 'الدخان', 'الجاثية', 'الأحقاف', 'محمد', 'الفتح', 'الحجرات', 'ق', 'الذاريات', 'الطور', 'النجم', 'القمر', 'الرحمن', 'الواقعة', 'الحديد', 'المجادلة', 'الحشر', 'الممتحنة', 'الصف', 'الجمعة', 'المنافقون', 'التغابن', 'الطلاق', 'التحريم', 'الملك', 'القلم', 'الحاقة', 'المعارج', 'نوح', 'الجن', 'المزمل', 'المدثر', 'القيامة', 'الإنسان', 'المرسلات', 'النبأ', 'النازعات', 'عبس', 'التكوير', 'الانفطار', 'المطففين', 'الانشقاق', 'البروج', 'الطارق', 'الأعلى', 'الغاشية', 'الفجر', 'البلد', 'الشمس', 'الليل', 'الضحى', 'الشرح', 'التين', 'العلق', 'القدر', 'البينة', 'الزلزلة', 'العاديات', 'القارعة', 'التكاثر', 'العصر', 'الهمزة', 'الفيل', 'قريش', 'الماعون', 'الكوثر', 'الكافرون', 'النصر', 'المسد', 'الإخلاص', 'الفلق', 'الناس']
RECITERS_MAP = {'ياسر الدوسري':'Yasser_Ad-Dussary_128kbps', 'الشيخ عبدالرحمن السديس': 'Abdurrahmaan_As-Sudais_64kbps', 'الشيخ ماهر المعيقلي': 'Maher_AlMuaiqly_64kbps', 'محمد صديق المنشاوي': 'Minshawy_Mujawwad_64kbps', 'مشاري العفاسي': 'Alafasy_64kbps'}

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
            JOBS[job_id].update({'percent': percent, 'status': status})
            if eta: JOBS[job_id]['eta'] = eta

def get_job(job_id):
    with JOBS_LOCK: return JOBS.get(job_id)

# ==========================================
# 📊 Scoped Logger
# ==========================================
class ScopedQuranLogger(ProgressBarLogger):
    def __init__(self, job_id):
        super().__init__()
        self.job_id = job_id
        self.start_time = None

    def bars_callback(self, bar, attr, value, old_value=None):
        job = get_job(self.job_id)
        if not job or job['should_stop']: raise Exception("Stopped")
        if bar == 't':
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
# 🛠️ Helper Functions
# ==========================================
def get_text(surah, ayah):
    try:
        r = requests.get(f'https://api.alquran.cloud/v1/ayah/{surah}:{ayah}/quran-simple')
        t = r.json()['data']['text']
        # ✅ مسح البسملة (Regex) لضمان الدقة
        if surah != 1 and surah != 9 and ayah == 1:
            basmala_pattern = r'^بِسْمِ [^ ]+ [^ ]+ [^ ]+' 
            t = re.sub(basmala_pattern, '', t).strip()
            t = t.replace("بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ", "").strip()
        return t
    except: return "Text Error"

def get_en_text(surah, ayah):
    try:
        r = requests.get(f'http://api.alquran.cloud/v1/ayah/{surah}:{ayah}/en.sahih')
        return r.json()['data']['text']
    except: return ""

def download_audio(reciter_id, surah, ayah, idx, workspace_dir):
    url = f'https://everyayah.com/data/{reciter_id}/{surah:03d}{ayah:03d}.mp3'
    out = os.path.join(workspace_dir, f'part{idx}.mp3')
    r = requests.get(url, stream=True, timeout=20)
    with open(out, 'wb') as f:
        for chunk in r.iter_content(8192): f.write(chunk)
    return out

def wrap_text(text, per_line):
    words = text.split()
    return '\n'.join([' '.join(words[i:i+per_line]) for i in range(0, len(words), per_line)])

def create_text_clip(arabic, duration, target_w, scale_factor=1.0):
    fs = int(46 * scale_factor)
    try: font = ImageFont.truetype(FONT_PATH_ARABIC, fs)
    except: font = ImageFont.load_default()
    wrapped = wrap_text(arabic, 8)
    lines = wrapped.split('\n')
    dummy = Image.new('RGBA', (target_w, 500))
    draw = ImageDraw.Draw(dummy)
    h_total = sum([draw.textbbox((0,0), l, font=font)[3] + 20 for l in lines])
    img = Image.new('RGBA', (target_w, h_total + 40), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    curr_y = 20
    for line in lines:
        w = draw.textbbox((0,0), line, font=font)[2]
        draw.text(((target_w-w)//2, curr_y), line, font=font, fill='white', stroke_width=1, stroke_fill='black')
        curr_y += draw.textbbox((0,0), line, font=font)[3] + 20
    return ImageClip(np.array(img)).set_duration(duration).fadein(0.3).fadeout(0.3)

def create_english_clip(text, duration, target_w, scale_factor=1.0):
    fs = int(26 * scale_factor)
    try: font = ImageFont.truetype(FONT_PATH_ENGLISH, fs)
    except: font = ImageFont.load_default()
    wrapped = wrap_text(text, 10)
    img = Image.new('RGBA', (target_w, 200), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    w, h = draw.textbbox((0,0), wrapped, font=font)[2:]
    draw.text(((target_w-w)//2, 10), wrapped, font=font, fill='#FFD700', align='center')
    return ImageClip(np.array(img)).set_duration(duration).fadein(0.3).fadeout(0.3)

def pick_bg(user_key, query=None):
    try:
        q = query if query else random.choice(['nature', 'clouds', 'ocean', 'stars'])
        headers = {'Authorization': user_key}
        r = requests.get(f"https://api.pexels.com/videos/search?query={q}&per_page=5&orientation=portrait", headers=headers, timeout=10)
        vids = r.json().get('videos', [])
        if not vids: return None
        vid = random.choice(vids)
        link = vid['video_files'][0]['link']
        path = os.path.join(VISION_DIR, f"bg_{vid['id']}.mp4")
        if not os.path.exists(path):
            with requests.get(link, stream=True) as rv:
                with open(path, 'wb') as f: shutil.copyfileobj(rv.raw, f)
        return path
    except: return None

# ==========================================
# 🎬 Scene Processor (The New Logic)
# ==========================================
def build_video_task(job_id, user_pexels_key, reciter_id, surah, start, end, quality, bg_query, fps, dynamic_bg):
    job = get_job(job_id)
    if not job: return
    workspace = job['workspace']
    final = None
    
    try:
        update_job_status(job_id, 5, 'Downloading Assets...')
        target_w, target_h = (1080, 1920) if quality == '1080' else (720, 1280)
        scale_factor = 1.0 if quality == '1080' else 0.67
        max_ayah = VERSE_COUNTS.get(surah, 286)
        last = min(end if end else start+4, max_ayah)
        
        ayahs_data = []
        full_audio_seg = AudioSegment.empty()
        
        # تحميل متوازي للخلفيات والصوت
        with ThreadPoolExecutor(max_workers=4) as executor:
            bg_futures = []
            for i, ayah in enumerate(range(start, last+1), 1):
                ap = download_audio(reciter_id, surah, ayah, i, workspace)
                seg = AudioSegment.from_file(ap)
                full_audio_seg = full_audio_seg.append(seg, crossfade=100) if len(full_audio_seg) > 0 else seg
                
                bg_fut = executor.submit(pick_bg, user_pexels_key, bg_query) if dynamic_bg else None
                ayahs_data.append({'ar': get_text(surah, ayah), 'en': get_en_text(surah, ayah), 'dur': seg.duration_seconds, 'bg_fut': bg_fut})

        final_audio_path = os.path.join(workspace, "final.mp3")
        full_audio_seg.export(final_audio_path, format="mp3")
        
        # بناء المشاهد
        update_job_status(job_id, 40, 'Assembling Scenes...')
        scenes = []
        curr_t = 0.0
        main_bg = pick_bg(user_pexels_key, bg_query) if not dynamic_bg else None

        for data in ayahs_data:
            bg_path = data['bg_fut'].result() if dynamic_bg else main_bg
            if bg_path and os.path.exists(bg_path):
                v = VideoFileClip(bg_path).resize(height=target_h)
                v = v.crop(width=target_w, height=target_h, x_center=v.w/2, y_center=v.h/2)
                v = v.fx(vfx.loop, duration=data['dur']).subclip(0, data['dur'])
            else:
                v = ColorClip((target_w, target_h), color=(15, 20, 35), duration=data['dur'])
            
            if scenes: v = v.crossfadein(0.5)
            
            ac = create_text_clip(data['ar'], data['dur'], target_w, scale_factor).set_position(('center', target_h*0.4))
            ec = create_english_clip(data['en'], data['dur'], target_w, scale_factor).set_position(('center', target_h*0.4 + ac.h + 20))
            
            scene = CompositeVideoClip([v, ColorClip(v.size, color=(0,0,0), duration=data['dur']).set_opacity(0.5), ac, ec])
            scenes.append(scene.set_start(curr_t).set_duration(data['dur']))
            curr_t += data['dur']

        final = CompositeVideoClip(scenes).set_audio(AudioFileClip(final_audio_path)).fadeout(0.2)
        out_p = os.path.join(workspace, f"Quran_{job_id[:8]}.mp4")
        
        update_job_status(job_id, 50, 'Rendering...')
        final.write_videofile(out_p, fps=fps, codec='libx264', audio_codec='aac', preset='ultrafast', threads=os.cpu_count() or 2, logger=ScopedQuranLogger(job_id))
        
        with JOBS_LOCK:
            JOBS[job_id].update({'output_path': out_p, 'is_complete': True, 'is_running': False})

    except Exception as e:
        update_job_status(job_id, 0, f'Error: {str(e)}')
    finally: gc.collect()

# ==========================================
# 🌐 API Routes
# ==========================================
@app.route('/api/generate', methods=['POST'])
def gen():
    d = request.json
    jid = create_job()
    threading.Thread(target=build_video_task, args=(jid, d['pexelsKey'], d['reciter'], int(d['surah']), int(d['startAyah']), int(d['endAyah']), d['quality'], d.get('bgQuery'), int(d.get('fps', 20)), d.get('dynamicBg', False)), daemon=True).start()
    return jsonify({'ok': True, 'jobId': jid})

@app.route('/api/progress')
def prog():
    j = get_job(request.args.get('jobId'))
    return jsonify(j) if j else (jsonify({'error': 'Not found'}), 404)

@app.route('/api/download')
def dl():
    j = get_job(request.args.get('jobId'))
    return send_file(j['output_path'], as_attachment=True) if j and j['output_path'] else (jsonify({'error': 'Not ready'}), 404)

@app.route('/api/config')
def conf(): return jsonify({'surahs': SURAH_NAMES, 'verseCounts': VERSE_COUNTS, 'reciters': RECITERS_MAP})

@app.route('/')
def ui(): return send_file(UI_PATH)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=7860, threaded=True)
