# Quran Reels Generator - Final Fixed Version (App Only)
import sys
import io
import os

# 1. إجبار النظام على استخدام UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, VideoFileClip, AudioFileClip, CompositeVideoClip, ColorClip
import moviepy.video.fx.all as vfx
from moviepy.config import change_settings
import arabic_reshaper
from bidi.algorithm import get_display

import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

import time
from deep_translator import GoogleTranslator
from pydub import AudioSegment
import requests
import shutil
import random
import threading
import datetime
import logging
import traceback
import gc
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from proglog import ProgressBarLogger

# ==========================================
# 📂 إعدادات المسارات
# ==========================================
def app_dir():
    if getattr(sys, "frozen", False): return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def bundled_dir():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"): return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

EXEC_DIR = app_dir()
BUNDLE_DIR = bundled_dir()

# FFMPEG & ImageMagick
FFMPEG_EXE = "ffmpeg"
os.environ["FFMPEG_BINARY"] = FFMPEG_EXE
IM_MAGICK_EXE = "/usr/bin/convert"
change_settings({"IMAGEMAGICK_BINARY": IM_MAGICK_EXE})

# Folders
TEMP_DIR = os.path.join(EXEC_DIR, "temp_videos")
VISION_DIR = os.path.join(BUNDLE_DIR, "vision")
UI_PATH = os.path.join(BUNDLE_DIR, "UI.html")
INTERNAL_AUDIO_DIR = os.path.join(EXEC_DIR, "temp_audio")
FONT_DIR = os.path.join(EXEC_DIR, "fonts")
FONT_PATH_ARABIC = os.path.join(FONT_DIR, "Arabic.ttf") 
FONT_PATH_ENGLISH = os.path.join(FONT_DIR, "English.otf")
FINAL_AUDIO_PATH = os.path.join(INTERNAL_AUDIO_DIR, "combined_final.mp3")

for d in [TEMP_DIR, INTERNAL_AUDIO_DIR, FONT_DIR, VISION_DIR]:
    os.makedirs(d, exist_ok=True)

AudioSegment.converter = FFMPEG_EXE
AudioSegment.ffmpeg = FFMPEG_EXE
AudioSegment.ffprobe = "ffprobe"

# ==========================================
# 📝 إدارة الحالة
# ==========================================
current_progress = {'percent': 0, 'status': 'واقف', 'log': [], 'is_running': False, 'is_complete': False, 'output_path': None, 'should_stop': False}

app = Flask(__name__, static_folder=EXEC_DIR)
CORS(app)

def reset_progress():
    global current_progress
    current_progress = {'percent': 0, 'status': 'جاري التحضير...', 'log': [], 'is_running': False, 'is_complete': False, 'output_path': None, 'error': None, 'should_stop': False}

def add_log(message):
    current_progress['log'].append(message)
    current_progress['status'] = message

def update_progress(percent, status):
    current_progress['percent'] = percent
    current_progress['status'] = status

def clear_outputs():
    if os.path.isdir(INTERNAL_AUDIO_DIR): shutil.rmtree(INTERNAL_AUDIO_DIR)
    os.makedirs(INTERNAL_AUDIO_DIR, exist_ok=True)
    if os.path.isdir(TEMP_DIR):
        for f in os.listdir(TEMP_DIR): 
            try: os.remove(os.path.join(TEMP_DIR, f))
            except: pass
    else:
        os.makedirs(TEMP_DIR, exist_ok=True)

# === ⏱️ كلاس العداد (تم استرجاع التايمر) ===
class QuranLogger(ProgressBarLogger):
    def __init__(self):
        super().__init__()
        self.start_time = None

    def bars_callback(self, bar, attr, value, old_value=None):
        if current_progress.get('should_stop'):
            raise Exception("Stopped by user")

        if bar == 't':
            total = self.bars[bar]['total']
            if total > 0:
                percent = int((value / total) * 100)
                if self.start_time is None: self.start_time = time.time()
                elapsed = time.time() - self.start_time
                
                # حساب الوقت المتبقي
                rem_str = "00:00"
                if elapsed > 0 and value > 0:
                    rate = value / elapsed 
                    remaining = (total - value) / rate
                    rem_str = str(datetime.timedelta(seconds=int(remaining)))[2:] if remaining > 0 else "00:00"
                
                current_progress['percent'] = percent
                # الرسالة دي اللي هتروح للمتصفح وفيها التايمر
                current_progress['status'] = f"جاري التصدير... {percent}% (متبقي {rem_str})"

# ==========================================
# 🛠️ الدوال المساعدة
# ==========================================
VERSE_COUNTS = {1: 7, 2: 286, 3: 200, 4: 176, 5: 120, 6: 165, 7: 206, 8: 75, 9: 129, 10: 109, 11: 123, 12: 111, 13: 43, 14: 52, 15: 99, 16: 128, 17: 111, 18: 110, 19: 98, 20: 135, 21: 112, 22: 78, 23: 118, 24: 64, 25: 77, 26: 227, 27: 93, 28: 88, 29: 69, 30: 60, 31: 34, 32: 30, 33: 73, 34: 54, 35: 45, 36: 83, 37: 182, 38: 88, 39: 75, 40: 85, 41: 54, 42: 53, 43: 89, 44: 59, 45: 37, 46: 35, 47: 38, 48: 29, 49: 18, 50: 45, 51: 60, 52: 49, 53: 62, 54: 55, 55: 78, 56: 96, 57: 29, 58: 22, 59: 24, 60: 13, 61: 14, 62: 11, 63: 11, 64: 18, 65: 12, 66: 12, 67: 30, 68: 52, 69: 52, 70: 44, 71: 28, 72: 28, 73: 20, 74: 56, 75: 40, 76: 31, 77: 50, 78: 40, 79: 46, 80: 42, 81: 29, 82: 19, 83: 36, 84: 25, 85: 22, 86: 17, 87: 19, 88: 26, 89: 30, 90: 20, 91: 15, 92: 21, 93: 11, 94: 8, 95: 8, 96: 19, 97: 5, 98: 8, 99: 8, 100: 11, 101: 11, 102: 8, 103: 3, 104: 9, 105: 5, 106: 4, 107: 7, 108: 3, 109: 6, 110: 3, 111: 5, 112: 4, 113: 5, 114: 6}
SURAH_NAMES = ['الفاتحة', 'البقرة', 'آل عمران', 'النساء', 'المائدة', 'الأنعام', 'الأعراف', 'الأنفال', 'التوبة', 'يونس', 'هود', 'يوسف', 'الرعد', 'إبراهيم', 'الحجر', 'النحل', 'الإسراء', 'الكهف', 'مريم', 'طه', 'الأنبياء', 'الحج', 'المؤمنون', 'النور', 'الفرقان', 'الشعراء', 'النمل', 'القصص', 'العنكبوت', 'الروم', 'لقمان', 'السجدة', 'الأحزاب', 'سبأ', 'فاطر', 'يس', 'الصافات', 'ص', 'الزمر', 'غافر', 'فصلت', 'الشورى', 'الزخرف', 'الدخان', 'الجاثية', 'الأحقاف', 'محمد', 'الفتح', 'الحجرات', 'ق', 'الذاريات', 'الطور', 'النجم', 'القمر', 'الرحمن', 'الواقعة', 'الحديد', 'المجادلة', 'الحشر', 'الممتحنة', 'الصف', 'الجمعة', 'المنافقون', 'التغابن', 'الطلاق', 'التحريم', 'الملك', 'القلم', 'الحاقة', 'المعارج', 'نوح', 'الجن', 'المزمل', 'المدثر', 'القيامة', 'الإنسان', 'المرسلات', 'النبأ', 'النازعات', 'عبس', 'التكوير', 'الانفطار', 'المطففين', 'الانشقاق', 'البروج', 'الطارق', 'الأعلى', 'الغاشية', 'الفجر', 'البلد', 'الشمس', 'الليل', 'الضحى', 'الشرح', 'التين', 'العلق', 'القدر', 'البينة', 'الزلزلة', 'العاديات', 'القارعة', 'التكاثر', 'العصر', 'الهمزة', 'الفيل', 'قريش', 'الماعون', 'الكوثر', 'الكافرون', 'النصر', 'المسد', 'الإخلاص', 'الفلق', 'الناس']
RECITERS_MAP = {'ياسر الدوسري':'Yasser_Ad-Dussary_128kbps', 'الشيخ عبدالرحمن السديس': 'Abdurrahmaan_As-Sudais_64kbps', 'الشيخ ماهر المعيقلي': 'Maher_AlMuaiqly_64kbps', 'الشيخ محمد صديق المنشاوي (مجود)': 'Minshawy_Mujawwad_64kbps', 'الشيخ سعود الشريم': 'Saood_ash-Shuraym_64kbps', 'الشيخ مشاري العفاسي': 'Alafasy_64kbps', 'الشيخ محمود خليل الحصري': 'Husary_64kbps', 'الشيخ أبو بكر الشاطري': 'Abu_Bakr_Ash-Shaatree_128kbps', 'ناصر القطامي':'Nasser_Alqatami_128kbps', 'هاني الرافعي':'Hani_Rifai_192kbps', 'علي جابر' :'Ali_Jaber_64kbps'}

def detect_silence(sound, thresh):
    t = 0
    while t < len(sound) and sound[t:t+10].dBFS < thresh: t += 10
    return t

def download_audio(reciter_id, surah, ayah, idx):
    os.makedirs(INTERNAL_AUDIO_DIR, exist_ok=True)
    url = f'https://everyayah.com/data/{reciter_id}/{surah:03d}{ayah:03d}.mp3'
    out = os.path.join(INTERNAL_AUDIO_DIR, f'part{idx}.mp3')
    try:
        r = requests.get(url, stream=True, timeout=30)
        with open(out, 'wb') as f:
            for chunk in r.iter_content(8192): f.write(chunk)
        
        snd = AudioSegment.from_file(out)
        
        # كود القص القديم (Trim Silence)
        start = detect_silence(snd, snd.dBFS-20) 
        end = detect_silence(snd.reverse(), snd.dBFS-20)
        
        trimmed = snd
        if start + end < len(snd):
            trimmed = snd[max(0, start-30):len(snd)-max(0, end-30)]
            
        # --- التعديل هنا: إضافة سكتة صغيرة في البداية (Delay) ---
        # 200 مللي ثانية تأخير عشان الصوت ميبدأش قبل الصورة
        padding = AudioSegment.silent(duration=50) 
        final_snd = padding + trimmed.fade_in(20).fade_out(20)
        # -------------------------------------------------------
        
        final_snd.export(out, format='mp3')
        
    except Exception as e: raise ValueError(f"فشل تحميل الآية {ayah}")
    return out
    
def get_text(surah, ayah):
    try:
        r = requests.get(f'https://api.alquran.cloud/v1/ayah/{surah}:{ayah}/quran-simple')
        t = r.json()['data']['text']
        
        # لو الآية رقم 1 والسورة مش الفاتحة (رقم 1) ولا التوبة (رقم 9)
        if surah != 1 and ayah == 1:
            # قائمة باحتمالات البسملة المختلفة في الرسم الإملائي والعثماني
            basmalah_variations = [
                "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ", # الرسم العثماني الشائع
                "بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِيمِ",   # الرسم الإملائي
                "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ"  # تنويع آخر في التشكيل
            ]
            
            # محاولة مسح البسملة لو موجودة في بداية النص
            for b in basmalah_variations:
                if t.startswith(b):
                    t = t.replace(b, "").strip()
                    break
            
            # حل أخير: لو لسه متمسحتش، امسح أول 39 حرف (طول البسملة تقريباً)
            # لأن أحياناً المسافات بتكون مختلفة
            if len(t) > 40 and t.startswith("بِسْمِ"): 
                 # نتأكد إننا مابنمسحش الآية نفسها، بنشوف أول مسافة بعد البسملة
                 split_text = t.split()
                 if len(split_text) > 4: # البسملة 4 كلمات
                     # نجمع الكلمات ما عدا أول 4
                     t = " ".join(split_text[4:])
                     
        return t
    except: return "خطأ"

def get_en_text(surah, ayah):
    try:
        r = requests.get(f'http://api.alquran.cloud/v1/ayah/{surah}:{ayah}/en.sahih')
        return r.json()['data']['text']
    except: return ""

def wrap_text(text, per_line):
    words = text.split()
    return '\n'.join([' '.join(words[i:i+per_line]) for i in range(0, len(words), per_line)])

# === 🎨 دالة إنشاء النصوص (إصلاح العربي + عدم القلب) ===
# === دالة الكتابة الخام (بدون معالجة عربي) ===
def create_text_clip(arabic, duration, target_w, scale_factor=1.0):
    # مسار الخط
    font_path = FONT_PATH_ARABIC
    
    words = arabic.split()
    wc = len(words)
    # تظبيط حجم الخط
    if wc > 60: base_fs, pl = 27, 10
    elif wc > 40: base_fs, pl = 32, 9
    elif wc > 25: base_fs, pl = 38, 8
    elif wc > 15: base_fs, pl = 43, 7
    else: base_fs, pl = 45, 6
    
    final_fs = int(base_fs * scale_factor)
    box_w = int(target_w * 0.9)

    # تحميل الخط
    try:
        font = ImageFont.truetype(font_path, final_fs)
    except:
        font = ImageFont.load_default()

    # ====================================================
    # 🚫 تم إلغاء المعالجة (Raw Text)
    # ====================================================
    # بنعمل Wrap بس عشان الكلام ميوصلش لآخر الشارع
    try:
        wrapped_text = wrap_text(arabic, pl)
        # بناخد النص زي ما هو بالظبط بدون تشبيك ولا قلب
        lines = wrapped_text.split('\n')
    except:
        lines = [arabic]
    # ====================================================

    # حساب الأبعاد
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

    img_w = max(box_w, int(max_line_w + 40))
    img_h = int(total_h + 40)
    
    final_image = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
    draw_final = ImageDraw.Draw(final_image)

    # الرسم
    current_y = 20
    for i, line in enumerate(lines):
        bbox = draw_final.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        start_x = (img_w - line_w) // 2
        
        # رسم النص كما هو
        draw_final.text((start_x+2, current_y+2), line, font=font, fill=(0,0,0,150))
        draw_final.text((start_x, current_y), line, font=font, fill='white')
        
        current_y += line_heights[i]

    np_img = np.array(final_image)
    return ImageClip(np_img).set_duration(duration).fadein(0.25).fadeout(0.25)

def create_english_clip(text, duration, target_w, scale_factor=1.0):
    final_fs = int(28 * scale_factor)
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
    draw.text((img_w/2, img_h/2), wrapped_text, font=font, fill='#FFD700', align='center', anchor="mm")
    
    np_img = np.array(img)
    return ImageClip(np_img).set_duration(duration).fadein(0.25).fadeout(0.25)

# === 🎥 الخلفيات ===
def pick_bg(user_key, custom_query=None):
    if not user_key: return None
    try:
        rand_page = random.randint(1, 10)
        safe_filter = " no people"
        if custom_query:
            trans_q = GoogleTranslator(source='auto', target='en').translate(custom_query.strip())
            q = trans_q + safe_filter
            add_log(f'Search: {q}')
        else:
            safe_topics = ['nature landscape', 'mosque architecture', 'sky clouds', 'galaxy stars', 'flowers garden', 'ocean waves']
            q = random.choice(safe_topics) + safe_filter
            add_log(f'Random BG: {q}')

        headers = {'Authorization': user_key}
        r = requests.get(f"https://api.pexels.com/videos/search?query={q}&per_page=15&page={rand_page}&orientation=portrait", headers=headers, timeout=15)
        
        if r.status_code == 401: return None
        vids = r.json().get('videos', [])
        if not vids: return None
        
        vid = random.choice(vids)
        f = next((vf for vf in vid['video_files'] if vf['width'] <= 1080 and vf['height'] > vf['width']), vid['video_files'][0])
        path = os.path.join(VISION_DIR, f"bg_{vid['id']}.mp4")
        if not os.path.exists(path):
            with requests.get(f['link'], stream=True) as rv:
                with open(path, 'wb') as f: shutil.copyfileobj(rv.raw, f)
        return path
    except: return None

# ==========================================
# 🎬 بناء الفيديو
# ==========================================
def build_video(user_pexels_key, reciter_id, surah, start, end=None, quality='720', bg_query=None):
    global current_progress
    final = None
    final_audio_clip = None
    bg = None
    success = False
    try:
        current_progress['is_running'] = True
        add_log('🚀 Starting Process...')
        clear_outputs()
        
        target_w, target_h = (1080, 1920) if quality == '1080' else (720, 1280)
        scale_factor = 1.0 if quality == '1080' else 0.67
        max_ayah = VERSE_COUNTS[surah]
        last = min(end if end else start+9, max_ayah)
        
        items = []
        full_audio_seg = AudioSegment.empty()
        
        for i, ayah in enumerate(range(start, last+1), 1):
            # 🛑 تحقق من الإيقاف في كل لفة
            if current_progress.get('should_stop'): raise Exception("Stopped by user")
            add_log(f'Processing Ayah {ayah}...')
            
            ap = download_audio(reciter_id, surah, ayah, i)
            ar_txt = f"{get_text(surah, ayah)} ({ayah})"
            en_txt = get_en_text(surah, ayah)
            
            seg = AudioSegment.from_file(ap)
            full_audio_seg = full_audio_seg.append(seg, crossfade=100) if len(full_audio_seg) > 0 else seg
            clip_dur = seg.duration_seconds 
            
            if len(ar_txt.split()) > 30:
                mid = len(ar_txt.split()) // 2
                items.append(( " ".join(ar_txt.split()[:mid]), " ".join(en_txt.split()[:len(en_txt.split())//2])+"...", clip_dur/2 ))
                items.append(( " ".join(ar_txt.split()[mid:]), "..."+" ".join(en_txt.split()[len(en_txt.split())//2:]), clip_dur/2 ))
            else:
                items.append((ar_txt, en_txt, clip_dur))
        
        full_audio_seg.export(FINAL_AUDIO_PATH, format="mp3")
        final_audio_clip = AudioFileClip(FINAL_AUDIO_PATH)
        full_dur = final_audio_clip.duration

        add_log('Merging Background...')
        bg_path = pick_bg(user_pexels_key, bg_query)
        if not bg_path: raise ValueError("No background found")
        
        bg = VideoFileClip(bg_path)
        bg_ratio = bg.w / bg.h
        target_ratio = target_w / target_h

        if bg_ratio > target_ratio:
            bg = bg.resize(height=target_h)
        else:
            bg = bg.resize(width=target_w)
            
        bg = bg.crop(width=target_w, height=target_h, x_center=bg.w/2, y_center=bg.h/2)
        bg = bg.fx(vfx.loop, duration=full_dur).subclip(0, full_dur)
        
        layers = [bg, ColorClip(bg.size, color=(0,0,0), duration=full_dur).set_opacity(0.6)]
        
        curr_t = 0.0
        y_pos = target_h * 0.40 
        
        for ar, en, dur in items:
            # 🛑 تحقق من الإيقاف قبل معالجة النصوص
            if current_progress.get('should_stop'): raise Exception("Stopped by user")
            
            ac = create_text_clip(ar, dur, target_w, scale_factor).set_start(curr_t).set_position(('center', y_pos))
            gap = 30 * scale_factor 
            ec = create_english_clip(en, dur, target_w, scale_factor).set_start(curr_t).set_position(('center', y_pos + ac.h + gap))
            layers.extend([ac, ec])
            curr_t += dur

        final = CompositeVideoClip(layers).set_audio(final_audio_clip)
        
        fname = f"Quran_{surah}_{start}-{last}_{quality}p.mp4"
        out = os.path.join(TEMP_DIR, fname) 
        
        add_log('Rendering Final Video...')
        my_logger = QuranLogger()
        final.write_videofile(
            out, fps=15, codec='libx264', audio_bitrate='96k', preset='ultrafast', 
            threads=4, verbose=False, logger=my_logger, 
            ffmpeg_params=['-movflags', '+faststart', '-pix_fmt', 'yuv420p', '-crf', '28']
        )
        
        update_progress(100, 'Done!')
        current_progress['is_complete'] = True 
        current_progress['output_path'] = out
        success = True
        
    except Exception as e:
        logging.error(traceback.format_exc())
        current_progress['error'] = str(e)
        add_log(f"Error: {str(e)}")
    finally:
        if success: add_log("Cleaning Memory...")
        
        # ⚠️ هنا التعديل المهم: بنقول للمتصفح إن العملية وقفت رسمياً
        current_progress['is_running'] = False
        
        try:
            if final: final.close()
            if final_audio_clip: final_audio_clip.close()
            if bg: bg.close()
            del final, final_audio_clip, bg
        except: pass
        gc.collect()

@app.route('/')
def ui(): return send_file(UI_PATH) if os.path.exists(UI_PATH) else "UI Missing"

@app.route('/api/generate', methods=['POST'])
def gen():
    d = request.json
    if current_progress['is_running']: return jsonify({'error': 'Busy'}), 400
    
    user_key = d.get('pexelsKey')
    if not user_key: return jsonify({'error': 'Pexels API Key Missing'}), 400

    reset_progress()
    threading.Thread(target=build_video, args=(
        user_key,
        d.get('reciter'), int(d.get('surah')), int(d.get('startAyah')), 
        int(d.get('endAyah')) if d.get('endAyah') else None, 
        d.get('quality', '720'), d.get('bgQuery')
    ), daemon=True).start()
    return jsonify({'ok': True})

@app.route('/api/cancel')
def cancel_process():
    if current_progress['is_running']:
        current_progress['should_stop'] = True
        current_progress['status'] = "Stopping..."
        add_log("🛑 Stopping...")
    return jsonify({'ok': True})

@app.route('/api/progress')
def prog(): return jsonify(current_progress)

@app.route('/api/config')
def conf(): return jsonify({'surahs': SURAH_NAMES, 'verseCounts': VERSE_COUNTS, 'reciters': RECITERS_MAP})

@app.route('/outputs/<path:f>')
def out(f): return send_from_directory(TEMP_DIR, f)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port, debug=False)





