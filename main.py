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
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

# Media Processing Imports
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

from moviepy.editor import ImageClip, VideoFileClip, AudioFileClip, CompositeVideoClip, ColorClip, concatenate_videoclips
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

# 🚀 إعدادات القراء
NEW_RECITERS_CONFIG = {
    'رعد الكردي': (221, "https://server6.mp3quran.net/kurdi/"),
}

OLD_RECITERS_MAP = {
    'ياسر الدوسري':'Yasser_Ad-Dussary_128kbps', 
    'الشيخ عبدالرحمن السديس': 'Abdurrahmaan_As-Sudais_64kbps', 
    'الشيخ ماهر المعيقلي': 'Maher_AlMuaiqly_64kbps', 
    'الشيخ سعود الشريم': 'Saood_ash-Shuraym_64kbps', 
    'الشيخ مشاري العفاسي': 'Alafasy_64kbps', 
    'الشيخ أبو بكر الشاطري': 'Abu_Bakr_Ash-Shaatree_128kbps', 
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
# 📊 Scoped Logger (Fixed for immediate stop)
# ==========================================
class ScopedQuranLogger(ProgressBarLogger):
    def __init__(self, job_id):
        super().__init__()
        self.job_id = job_id
        self.start_time = None
    
    def callback(self, **changes):
        # ✅ فحص الإيقاف مع كل تحديث للوغ
        check_stop(self.job_id)
        super().callback(**changes)

    def bars_callback(self, bar, attr, value, old_value=None):
        check_stop(self.job_id) # ✅ فحص إضافي
        
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
def detect_silence(sound, thresh):
    t = 0
    while t < len(sound) and sound[t:t+10].dBFS < thresh: t += 10
    return t

# ✅ دالة تحميل ذكية تقبل المقاطعة
def smart_download(url, dest_path, job_id):
    check_stop(job_id)
    with requests.get(url, stream=True, timeout=30) as r:
        r.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                check_stop(job_id) # 🛑 يفحص التوقف كل 8 كيلو بايت
                if chunk: f.write(chunk)

def process_mp3quran_audio(reciter_name, surah, ayah, idx, workspace_dir, job_id):
    reciter_id, server_url = NEW_RECITERS_CONFIG[reciter_name]
    cache_dir = os.path.join(EXEC_DIR, "cache_mp3quran", str(reciter_id))
    os.makedirs(cache_dir, exist_ok=True)
    full_audio_path = os.path.join(cache_dir, f"{surah:03d}.mp3")
    timings_path = os.path.join(cache_dir, f"{surah:03d}.json")

    # تحميل الملفات لو مش موجودة
    if not os.path.exists(full_audio_path) or not os.path.exists(timings_path):
        smart_download(f"{server_url}{surah:03d}.mp3", full_audio_path, job_id)
        
        # جلب التوقيتات
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
    font = ImageFont.truetype(FONT_PATH_ARABIC, int(48 * scale_factor))
    lines = wrap_text(arabic, 7).split('\n')
    
    dummy = Image.new('RGBA', (target_w, 100))
    d = ImageDraw.Draw(dummy)
    
    line_metrics = []
    total_h = 0
    GAP = 10 
    
    for l in lines:
        bbox = d.textbbox((0, 0), l, font=font)
        h = bbox[3] - bbox[1]
        line_metrics.append(h)
        total_h += h + GAP
        
    total_h += 40 
    
    img = Image.new('RGBA', (target_w, total_h), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    curr_y = 20
    
    for i, line in enumerate(lines):
        w = draw.textbbox((0, 0), line, font=font)[2]
        x = (target_w - w) // 2
        
        if glow: 
            draw.text((x, curr_y), line, font=font, fill=(255,255,255,40), stroke_width=5, stroke_fill=(255,255,255,40))
        
        draw.text((x+1, curr_y+1), line, font=font, fill=(0,0,0,180))
        draw.text((x, curr_y), line, font=font, fill='white', stroke_width=2, stroke_fill='black')
        
        curr_y += line_metrics[i] + GAP
        
    return ImageClip(np.array(img)).set_duration(duration).fadein(0.25).fadeout(0.25)

def create_english_clip(text, duration, target_w, scale_factor=1.0, glow=False):
    font = ImageFont.truetype(FONT_PATH_ENGLISH, int(30 * scale_factor))
    img = Image.new('RGBA', (target_w, 200), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    draw.text((target_w/2, 20), wrap_text(text, 10), font=font, fill='#FFD700', align='center', anchor="ma", stroke_width=1, stroke_fill='black')
    return ImageClip(np.array(img)).set_duration(duration).fadein(0.25).fadeout(0.25)

# ✅ تم تعديل دالة fetch_video_pool فقط لإضافة العشوائية
def fetch_video_pool(user_key, custom_query, count=1, job_id=None):
    pool = []
    
    if custom_query and len(custom_query) > 2:
        try:
             q_base = GoogleTranslator(source='auto', target='en').translate(custom_query.strip())
        except:
             q_base = "nature landscape"
    else:
        # قائمة كلمات بحث متنوعة (عشوائية)
        topics = ['nature landscape', 'mosque architecture', 'sky clouds', 'galaxy stars', 'ocean waves', 'forest trees', 'mountains', 'waterfall']
        q_base = random.choice(topics)

    q = f"{q_base} no people" # فلتر الأمان

    try:
        check_stop(job_id)
        # صفحة عشوائية
        random_page = random.randint(1, 10)
        
        # إضافة &page={random_page}
        vids = requests.get(f"https://api.pexels.com/videos/search?query={q}&per_page={count+2}&orientation=portrait&page={random_page}", headers={'Authorization': user_key}, timeout=10).json().get('videos', [])
        
        # خلط النتائج
        random.shuffle(vids)
        
        for vid in vids[:count]:
            check_stop(job_id)
            path = os.path.join(VISION_DIR, f"bg_{vid['id']}.mp4")
            if not os.path.exists(path):
                # ✅ التحميل باستخدام smart_download للمقاطعة الفورية
                smart_download(vid['video_files'][0]['link'], path, job_id)
            pool.append(path)
    except: pass
    return pool

def build_video_task(job_id, user_pexels_key, reciter_id, surah, start, end, quality, bg_query, fps, dynamic_bg, use_glow, use_vignette):
    job = get_job(job_id)
    workspace = job['workspace']
    target_w, target_h = (1080, 1920) if quality == '1080' else (720, 1280)
    scale = 1.0 if quality == '1080' else 0.67
    last = min(end if end else start+9, VERSE_COUNTS.get(surah, 286))
    
    try:
        ayah_data, full_audio = [], AudioSegment.empty()
        for i, ayah in enumerate(range(start, last+1), 1):
            check_stop(job_id)
            update_job_status(job_id, 10 + i, f'Processing Ayah {ayah}...')
            
            # ✅ تمرير job_id
            ap = download_audio(reciter_id, surah, ayah, i, workspace, job_id)
            seg = AudioSegment.from_file(ap)
            full_audio += seg
            
            ar_text_with_num = f"{get_text(surah, ayah)} ({ayah})"
            ayah_data.append({'ar': ar_text_with_num, 'en': get_en_text(surah, ayah), 'dur': seg.duration_seconds})

        a_path = os.path.join(workspace, "combined.mp3")
        full_audio.export(a_path, format="mp3")
        aclip = AudioFileClip(a_path)
        
        # ✅ تمرير job_id لجلب الخلفيات
        vpool = fetch_video_pool(user_pexels_key, bg_query, count=len(ayah_data) if dynamic_bg else 1, job_id=job_id)
        bg_clips = []
        
        check_stop(job_id)
        
        if not vpool: 
             bg = ColorClip((target_w, target_h), color=(15, 20, 35), duration=aclip.duration)
        else:
            if dynamic_bg:
                for i, data in enumerate(ayah_data):
                    check_stop(job_id)
                    vid_path = vpool[i % len(vpool)]
                    dur = data['dur']
                    clip = VideoFileClip(vid_path).resize(height=target_h).crop(width=target_w, height=target_h, x_center=target_w/2, y_center=target_h/2)
                    if clip.duration < dur: clip = clip.loop(duration=dur)
                    else:
                        start_t = random.uniform(0, max(0, clip.duration - dur))
                        clip = clip.subclip(start_t, start_t + dur)
                    bg_clips.append(clip.fadein(0.5).fadeout(0.5))
                bg = concatenate_videoclips(bg_clips, method="compose")
            else:
                bg = VideoFileClip(vpool[0]).resize(height=target_h).crop(width=target_w, height=target_h, x_center=target_w/2, y_center=target_h/2).loop(duration=aclip.duration)
        
        overlays = [ColorClip((target_w, target_h), color=(0,0,0), duration=aclip.duration).set_opacity(0.3)]
        if use_vignette: overlays.append(create_vignette_mask(target_w, target_h).set_duration(aclip.duration))
        
        texts, curr = [], 0
        for d in ayah_data:
            check_stop(job_id)
            ac = create_text_clip(d['ar'], d['dur'], target_w, scale, use_glow)
            ec = create_english_clip(d['en'], d['dur'], target_w, scale, use_glow)
            
            ar_y_pos = target_h * 0.32
            en_y_pos = ar_y_pos + ac.h + (20 * scale) 
            
            ac = ac.set_start(curr).set_position(('center', ar_y_pos))
            ec = ec.set_start(curr).set_position(('center', en_y_pos))
            
            texts.extend([ac, ec])
            curr += d['dur']
        
        out_p = os.path.join(workspace, f"out_{job_id}.mp4")
        check_stop(job_id)
        
        # ✅ الريندر مع اللوجر المحسن
        CompositeVideoClip([bg] + overlays + texts).set_audio(aclip).write_videofile(out_p, fps=fps, codec='libx264', logger=ScopedQuranLogger(job_id))
        
        with JOBS_LOCK: JOBS[job_id].update({'output_path': out_p, 'is_complete': True, 'is_running': False, 'percent': 100, 'status': "Done!"})
    
    except Exception as e:
         msg = str(e)
         status = "Cancelled" if msg == "Stopped" else "Error"
         with JOBS_LOCK: JOBS[job_id].update({'error': msg, 'status': status, 'is_running': False})
    
    finally:
        try:
            if 'aclip' in locals(): aclip.close()
            if 'bg' in locals(): bg.close()
        except: pass
        gc.collect()

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
