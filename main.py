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
RECITERS_MAP = {'ياسر الدوسري':'Yasser_Ad-Dussary_128kbps', 'الشيخ عبدالرحمن السديس': 'Abdurrahmaan_As-Sudais_64kbps', 'الشيخ ماهر المعيقلي': 'Maher_AlMuaiqly_64kbps', 'الشيخ محمد صديق المنشاوي (مجود)': 'Minshawy_Mujawwad_64kbps', 'الشيخ سعود الشريم': 'Saood_ash-Shuraym_64kbps', 'الشيخ مشاري العفاسي': 'Alafasy_64kbps', 'الشيخ محمود خليل الحصري': 'Husary_64kbps', 'الشيخ أبو بكر الشاطري': 'Abu_Bakr_Ash-Shaatree_128kbps', 'ناصر القطامي':'Nasser_Alqatami_128kbps', 'هاني الرافعي':'Hani_Rifai_192kbps', 'علي جابر' :'Ali_Jaber_64kbps'}

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

def cleanup_job(job_id):
    with JOBS_LOCK:
        job = JOBS.pop(job_id, None)
    if job and os.path.exists(job['workspace']):
        try: shutil.rmtree(job['workspace'])
        except: pass

class ScopedQuranLogger(ProgressBarLogger):
    def __init__(self, job_id): super().__init__(); self.job_id = job_id; self.start_time = None
    def bars_callback(self, bar, attr, value, old_value=None):
        job = get_job(self.job_id)
        if not job or job['should_stop']: raise Exception("Stopped by user")
        if bar == 't':
            total = self.bars[bar]['total']
            if total > 0:
                percent = int((value / total) * 100)
                if self.start_time is None: self.start_time = time.time()
                elapsed = time.time() - self.start_time
                rem_str = "00:00"
                if elapsed > 0 and value > 0:
                    remaining = (total - value) / (value / elapsed)
                    rem_str = str(datetime.timedelta(seconds=int(remaining)))[2:] if remaining > 0 else "00:00"
                update_job_status(self.job_id, percent, f"جاري التصدير... {percent}%", eta=rem_str)

# ==========================================
# 🛠️ Helper Functions
# ==========================================
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def detect_silence(sound, thresh):
    try:
        if len(sound) == 0: return 0
        t = 0
        while t < len(sound) and sound[t:t+10].dBFS < thresh: t += 10
        return t
    except: return 0

def download_audio(reciter_id, surah, ayah, idx, workspace_dir):
    url = f'https://everyayah.com/data/{reciter_id}/{surah:03d}{ayah:03d}.mp3'
    out = os.path.join(workspace_dir, f'part{idx}.mp3')
    try:
        r = requests.get(url, stream=True, timeout=30)
        with open(out, 'wb') as f:
            for chunk in r.iter_content(8192): f.write(chunk)
        snd = AudioSegment.from_file(out)
        if len(snd) < 100: final_snd = snd
        else:
            start = detect_silence(snd, snd.dBFS-20) 
            end = detect_silence(snd.reverse(), snd.dBFS-20)
            if start + end < len(snd):
                trimmed = snd[max(0, start-30):len(snd)-max(0, end-30)]
            else: trimmed = snd 
            padding = AudioSegment.silent(duration=50) 
            final_snd = padding + trimmed.fade_in(20).fade_out(20)
        final_snd.export(out, format='mp3')
    except Exception as e: 
        print(f"Audio DL Error: {e}")
        AudioSegment.silent(duration=1000).export(out, format='mp3')
    return out

def get_text(surah, ayah):
    try:
        r = requests.get(f'https://api.alquran.cloud/v1/ayah/{surah}:{ayah}/quran-simple')
        t = r.json()['data']['text']
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

def wrap_text(text, per_line):
    words = text.split()
    return '\n'.join([' '.join(words[i:i+per_line]) for i in range(0, len(words), per_line)])

def create_vignette_mask(w, h):
    Y, X = np.ogrid[:h, :w]
    center_y, center_x = h / 2, w / 2
    dist_from_center = np.sqrt((X - center_x)**2 + (Y - center_y)**2)
    max_dist = np.sqrt((w/2)**2 + (h/2)**2)
    mask = dist_from_center / max_dist
    mask = np.clip(mask * 1.5, 0, 1) ** 3 
    mask_img = np.zeros((h, w, 4), dtype=np.uint8)
    mask_img[:, :, 3] = (mask * 255).astype(np.uint8)
    return ImageClip(mask_img, ismask=False)

# ==========================================
# 🎨 دالة رسم النص العربي (محدثة لاستقبال اللون)
# ==========================================
def create_text_clip(arabic, duration, target_w, scale_factor=1.0, glow=False, color='white'):
    font_path = FONT_PATH_ARABIC
    words = arabic.split()
    wc = len(words)
    if wc > 60: base_fs, pl = 30, 12
    elif wc > 40: base_fs, pl = 35, 10
    elif wc > 25: base_fs, pl = 41, 9
    elif wc > 15: base_fs, pl = 46, 8
    else: base_fs, pl = 48, 7
    final_fs = int(base_fs * scale_factor)
    try: font = ImageFont.truetype(font_path, final_fs)
    except: font = ImageFont.load_default()

    wrapped_text = wrap_text(arabic, pl)
    lines = wrapped_text.split('\n')
    dummy_img = Image.new('RGBA', (target_w, 1000))
    draw = ImageDraw.Draw(dummy_img)
    max_line_w = 0
    total_h = 0
    line_heights = []
    
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        line_h = bbox[3] - bbox[1]
        max_line_w = max(max_line_w, line_w)
        line_heights.append(line_h + 20)
        total_h += line_h + 20

    box_w = int(target_w * 0.9)
    img_w = max(box_w, int(max_line_w + 40))
    img_h = int(total_h + 40)
    final_image = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
    draw_final = ImageDraw.Draw(final_image)
    current_y = 20
    
    shadow_opacity = 180 
    stroke_w = 1 
    
    # تحويل كود اللون الـ Hex إلى RGB لحساب لون التوهج
    try:
        if color.startswith('#'):
            rgb_color = hex_to_rgb(color)
        else:
            rgb_color = (255, 255, 255) # Fallback to white
    except:
        rgb_color = (255, 255, 255)

    for i, line in enumerate(lines):
        bbox = draw_final.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        start_x = (img_w - line_w) // 2
        
        # ✅ توهج بنفس لون الخط (شفافية متدرجة)
        if glow:
            faint_color = rgb_color + (40,) 
            strong_color = rgb_color + (80,) 
            draw_final.text((start_x, current_y), line, font=font, fill=faint_color, stroke_width=5, stroke_fill=faint_color)
            draw_final.text((start_x, current_y), line, font=font, fill=strong_color, stroke_width=3, stroke_fill=strong_color)

        draw_final.text((start_x + 1, current_y + 1), line, font=font, fill=(0,0,0, shadow_opacity))
        draw_final.text((start_x, current_y), line, font=font, fill=color, stroke_width=stroke_w, stroke_fill='black')
        current_y += line_heights[i]
        
    return ImageClip(np.array(final_image)).set_duration(duration).fadein(0.25).fadeout(0.25)

# ==========================================
# 🎨 دالة رسم النص الإنجليزي (محدثة لاستقبال اللون)
# ==========================================
def create_english_clip(text, duration, target_w, scale_factor=1.0, glow=False, color='#FFD700'):
    final_fs = int(30 * scale_factor)
    box_w = int(target_w * 0.85)
    wrapped_text = wrap_text(text, 10)
    try: font = ImageFont.truetype(FONT_PATH_ENGLISH, final_fs)
    except: font = ImageFont.load_default()
    dummy_img = Image.new('RGB', (1, 1))
    draw = ImageDraw.Draw(dummy_img)
    bbox = draw.textbbox((0, 0), wrapped_text, font=font, align='center')
    img_w = max(box_w, int((bbox[2]-bbox[0]) + 20))
    img_h = int((bbox[3]-bbox[1]) + 20)
    img = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    stroke_w = 1 
    
    # تحويل اللون لحساب التوهج
    try:
        if color.startswith('#'):
            rgb_color = hex_to_rgb(color)
        else:
            rgb_color = (255, 215, 0) # Fallback to gold
    except:
        rgb_color = (255, 215, 0)

    if glow:
         glow_rgba = rgb_color + (50,)
         draw.text((img_w/2, img_h/2), wrapped_text, font=font, fill=glow_rgba, align='center', anchor="mm", stroke_width=2, stroke_fill=glow_rgba)

    draw.text((img_w/2, img_h/2), wrapped_text, font=font, fill=color, align='center', anchor="mm", stroke_width=stroke_w, stroke_fill='black')
    return ImageClip(np.array(img)).set_duration(duration).fadein(0.25).fadeout(0.25)

# ... (fetch_video_pool remains same) ...
def fetch_video_pool(user_key, custom_query, count=1):
    pool = []
    if not user_key or len(user_key) < 10: return pool
    try:
        safe_filter = " no people"
        if custom_query and len(custom_query) > 2:
            try: trans_q = GoogleTranslator(source='auto', target='en').translate(custom_query.strip()) + safe_filter
            except: trans_q = "nature landscape" + safe_filter
            q = trans_q
        else:
            q = random.choice(['nature landscape', 'mosque architecture', 'sky clouds', 'galaxy stars', 'ocean waves']) + safe_filter
        headers = {'Authorization': user_key}
        r = requests.get(f"https://api.pexels.com/videos/search?query={q}&per_page={count+2}&orientation=portrait", headers=headers, timeout=15)
        if r.status_code == 200:
            vids = r.json().get('videos', [])
            random.shuffle(vids)
            for vid in vids:
                if len(pool) >= count: break 
                f = next((vf for vf in vid['video_files'] if vf['width'] <= 1080 and vf['height'] > vf['width']), None)
                if not f and vid['video_files']: f = vid['video_files'][0]
                if f:
                    path = os.path.join(VISION_DIR, f"bg_{vid['id']}.mp4")
                    if not os.path.exists(path):
                        with requests.get(f['link'], stream=True, timeout=20) as rv:
                            with open(path, 'wb') as f_out: shutil.copyfileobj(rv.raw, f_out)
                    pool.append(path)
    except Exception as e: print(f"Pool Fetch Error: {e}")
    return pool

def build_video_task(job_id, user_pexels_key, reciter_id, surah, start, end, quality, bg_query, fps, dynamic_bg, use_glow, use_vignette, ar_color, en_color):
    job = get_job(job_id)
    if not job: return
    workspace = job['workspace']
    final = None; final_audio_clip = None; bg_clip = None
    
    try:
        update_job_status(job_id, 5, 'Downloading Assets...')
        target_w, target_h = (1080, 1920) if quality == '1080' else (720, 1280)
        scale_factor = 1.0 if quality == '1080' else 0.67
        max_ayah = VERSE_COUNTS.get(surah, 286)
        last = min(end if end else start+9, max_ayah)
        if start > last: raise ValueError("Invalid ayah range")

        ayah_data = []; full_audio_seg = AudioSegment.empty()
        
        for i, ayah in enumerate(range(start, last+1), 1):
            if get_job(job_id)['should_stop']: raise Exception("Stopped")
            update_job_status(job_id, 5 + int((i / (last-start+1)) * 20), f'Processing Ayah {ayah}...')
            ap = download_audio(reciter_id, surah, ayah, i, workspace)
            ar_txt = f"{get_text(surah, ayah)} ({ayah})"; en_txt = get_en_text(surah, ayah)
            seg = AudioSegment.from_file(ap)
            full_audio_seg = full_audio_seg.append(seg, crossfade=100) if len(full_audio_seg) > 0 else seg
            ayah_data.append({'ar': ar_txt, 'en': en_txt, 'dur': seg.duration_seconds})

        if len(full_audio_seg) < 100: full_audio_seg = full_audio_seg + AudioSegment.silent(duration=1000)
        final_audio_path = os.path.join(workspace, "combined.mp3")
        full_audio_seg.export(final_audio_path, format="mp3")
        final_audio_clip = AudioFileClip(final_audio_path)
        full_dur = max(1.0, final_audio_clip.duration)

        update_job_status(job_id, 30, 'Preparing Backgrounds...')
        pool_size = min(len(ayah_data), 5) if dynamic_bg else 1
        video_pool = fetch_video_pool(user_pexels_key, bg_query, count=pool_size)
        
        if not video_pool:
            bg_clip = ColorClip((target_w, target_h), color=(15, 20, 35), duration=full_dur)
        elif dynamic_bg:
            bg_clips_list = []
            for i, data in enumerate(ayah_data):
                required_dur = max(2.0, data['dur'])
                vid_path = video_pool[i % len(video_pool)]
                try:
                    raw_clip = VideoFileClip(vid_path)
                    sub = raw_clip.fx(vfx.loop, duration=required_dur) if raw_clip.duration < required_dur else raw_clip.subclip(0, required_dur)
                    sub = sub.resize(height=target_h).crop(width=target_w, height=target_h, x_center=sub.w/2, y_center=sub.h/2).fadein(0.2).fadeout(0.2)
                    bg_clips_list.append(sub)
                except Exception as e:
                    bg_clips_list.append(ColorClip((target_w, target_h), color=(20, 20, 20), duration=required_dur))
            if bg_clips_list:
                bg_clip = concatenate_videoclips(bg_clips_list, method="compose")
            else:
                bg_clip = ColorClip((target_w, target_h), color=(15, 20, 35), duration=full_dur)
        else:
            try:
                bg = VideoFileClip(video_pool[0]).resize(height=target_h).crop(width=target_w, height=target_h, x_center=video_pool[0].w/2, y_center=video_pool[0].h/2)
                bg_clip = bg.fx(vfx.loop, duration=full_dur).subclip(0, full_dur)
            except: bg_clip = ColorClip((target_w, target_h), color=(15, 20, 35), duration=full_dur)

        bg_clip = bg_clip.set_duration(full_dur)
        
        if use_vignette:
            mask_clip = create_vignette_mask(target_w, target_h).set_duration(full_dur)
            base_dark = ColorClip((target_w, target_h), color=(0,0,0), duration=full_dur).set_opacity(0.2)
            overlay_layers = [base_dark, mask_clip]
        else:
            overlay_layers = [ColorClip((target_w, target_h), color=(0,0,0), duration=full_dur).set_opacity(0.6)]
        
        text_layers = []; curr_t = 0.0; y_pos = target_h * 0.40 
        for data in ayah_data:
            ar, en, dur = data['ar'], data['en'], data['dur']
            if get_job(job_id)['should_stop']: raise Exception("Stopped")
            
            # ✅ تمرير الألوان المختارة لدوال الرسم
            ac = create_text_clip(ar, dur, target_w, scale_factor, glow=use_glow, color=ar_color).set_start(curr_t).set_position(('center', y_pos))
            gap = 10 * scale_factor 
            ec = create_english_clip(en, dur, target_w, scale_factor, glow=use_glow, color=en_color).set_start(curr_t).set_position(('center', y_pos + ac.h + gap))
            text_layers.extend([ac, ec])
            curr_t += dur

        final = CompositeVideoClip([bg_clip] + overlay_layers + text_layers).set_audio(final_audio_clip).fadeout(0.5).audio_fadeout(0.5)
        output_filename = f"Quran_{surah}_{start}-{last}_{job_id[:8]}.mp4"
        output_full_path = os.path.join(workspace, output_filename)
        update_job_status(job_id, 50, f'Rendering ({fps} FPS)...')
        
        final.write_videofile(output_full_path, fps=fps, codec='libx264', audio_codec='aac', audio_bitrate='128k', preset='ultrafast', threads=os.cpu_count() or 2, logger=ScopedQuranLogger(job_id), ffmpeg_params=['-movflags', '+faststart', '-pix_fmt', 'yuv420p', '-crf', '28'])
        
        with JOBS_LOCK:
            JOBS[job_id].update({'output_path': output_full_path, 'is_complete': True, 'is_running': False, 'percent': 100, 'eta': "00:00", 'status': "Done! Ready for download."})

    except Exception as e:
        logging.error(f"Job {job_id} Error: {traceback.format_exc()}")
        with JOBS_LOCK: JOBS[job_id].update({'error': str(e), 'is_running': False, 'status': "Error Occurred"})
    finally:
        try:
            if final: final.close()
            if final_audio_clip: final_audio_clip.close()
            if bg_clip: bg_clip.close()
        except: pass
        gc.collect()

@app.route('/')
def ui(): return send_file(UI_PATH) if os.path.exists(UI_PATH) else "API Running."

@app.route('/api/generate', methods=['POST'])
def gen():
    d = request.json
    if not d.get('pexelsKey'): return jsonify({'error': 'Key Missing'}), 400
    try: user_fps = max(10, min(30, int(d.get('fps', 20))))
    except: user_fps = 20
    job_id = create_job()
    
    # ✅ استلام الألوان من الفرونت إند (مع قيم افتراضية)
    ar_color = d.get('arabicColor', '#FFFFFF')
    en_color = d.get('englishColor', '#FFD700')

    threading.Thread(target=build_video_task, args=(job_id, d.get('pexelsKey'), d.get('reciter'), int(d.get('surah')), int(d.get('startAyah')), int(d.get('endAyah')), d.get('quality', '720'), d.get('bgQuery'), user_fps, d.get('dynamicBg', False), d.get('useGlow', False), d.get('useVignette', False), ar_color, en_color), daemon=True).start()
    return jsonify({'ok': True, 'jobId': job_id})

@app.route('/api/progress')
def prog():
    job = get_job(request.args.get('jobId'))
    if not job: return jsonify({'error': 'Job not found'}), 404
    return jsonify(job)

@app.route('/api/download')
def download_result():
    job = get_job(request.args.get('jobId'))
    if not job or not job['output_path'] or not os.path.exists(job['output_path']): return jsonify({'error': 'Not ready'}), 404
    return send_file(job['output_path'], as_attachment=True, download_name=os.path.basename(job['output_path']), mimetype='video/mp4')

@app.route('/api/cancel', methods=['POST'])
def cancel_process():
    job_id = request.json.get('jobId')
    with JOBS_LOCK:
        if job_id in JOBS: JOBS[job_id]['should_stop'] = True
    return jsonify({'ok': True})

@app.route('/api/config')
def conf(): return jsonify({'surahs': SURAH_NAMES, 'verseCounts': VERSE_COUNTS, 'reciters': RECITERS_MAP})

def background_cleanup():
    while True:
        time.sleep(3600)
        with JOBS_LOCK:
            now = time.time()
            to_del = [jid for jid, j in JOBS.items() if now - j['created_at'] > 3600]
            for jid in to_del: del JOBS[jid]
        if os.path.exists(BASE_TEMP_DIR):
            for f in os.listdir(BASE_TEMP_DIR):
                fp = os.path.join(BASE_TEMP_DIR, f)
                if os.path.isdir(fp) and time.time() - os.path.getctime(fp) > 3600: shutil.rmtree(fp, ignore_errors=True)

threading.Thread(target=background_cleanup, daemon=True).start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8000)), debug=False, threaded=True)
