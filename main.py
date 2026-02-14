# Quran Reels Generator - Fast & Memory Efficient
# ==========================================
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS
# ==========================================
import time
from deep_translator import GoogleTranslator
import moviepy.video.fx.all as vfx
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, ColorClip
from moviepy.config import change_settings
from pydub import AudioSegment
import requests
import os
import sys
import shutil
import random
import threading
import datetime
import logging
import traceback
import gc
import arabic_reshaper
from bidi.algorithm import get_display
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from proglog import ProgressBarLogger

# ==========================================
# 🔧 إعدادات النظام
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXEC_DIR = BASE_DIR
BUNDLE_DIR = BASE_DIR

FFMPEG_EXE = "ffmpeg"
os.environ["FFMPEG_BINARY"] = FFMPEG_EXE

# ImageMagick Fast Path
IM_MAGICK_EXE = "/usr/bin/convert"
change_settings({"IMAGEMAGICK_BINARY": IM_MAGICK_EXE})

AudioSegment.converter = FFMPEG_EXE
AudioSegment.ffmpeg = FFMPEG_EXE
AudioSegment.ffprobe = "ffprobe"

# ==========================================
# 📂 المجلدات
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

# Logging
log_path = os.path.join(EXEC_DIR, "runlog.txt")
logging.basicConfig(filename=log_path, level=logging.INFO, format='%(asctime)s - %(message)s', force=True)

# ==========================================
# البيانات (تم اختصارها للعرض، استخدم بياناتك الكاملة)
VERSE_COUNTS = {1: 7, 2: 286, 3: 200, 112: 4, 113: 5, 114: 6} # أضف القائمة الكاملة هنا
SURAH_NAMES = ['الفاتحة', 'البقرة', 'آل عمران', 'الإخلاص', 'الفلق', 'الناس'] # أضف القائمة الكاملة
RECITERS_MAP = {'ياسر الدوسري':'Yasser_Ad-Dussary_128kbps'} # أضف القائمة الكاملة

current_progress = {'percent': 0, 'status': 'واقف', 'log': [], 'is_running': False, 'is_complete': False, 'output_path': None, 'should_stop': False}
app = Flask(__name__, static_folder=EXEC_DIR)
CORS(app)

# ... (نفس كلاس Logger ودوال المساعدة السابقة: reset_progress, add_log, update_progress, clear_outputs, clear_vision_cache, detect_silence) ...
# لعدم تكرار الكود الطويل، استخدم الدوال المساعدة من الكود السابق هنا

class QuranLogger(ProgressBarLogger):
    def __init__(self):
        super().__init__()
        self.start_time = None
    def bars_callback(self, bar, attr, value, old_value=None):
        if current_progress.get('should_stop'): raise Exception("تم الإلغاء")
        if bar == 't':
            total = self.bars[bar]['total']
            if total > 0:
                percent = int((value / total) * 100)
                current_progress['percent'] = percent
                current_progress['status'] = f"جاري التصدير... {percent}%"

def reset_progress():
    global current_progress
    current_progress = {'percent': 0, 'status': 'جاري التحضير...', 'log': [], 'is_running': False, 'is_complete': False, 'output_path': None, 'error': None, 'should_stop': False}

def add_log(message):
    current_progress['log'].append(message)
    current_progress['status'] = message
    print(f'>>> {message}', flush=True)

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

def clear_vision_cache():
    try:
        files = [f for f in os.listdir(VISION_DIR) if f.lower().endswith('.mp4')]
        for f in files: os.remove(os.path.join(VISION_DIR, f))
    except: pass

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
        start = detect_silence(snd, snd.dBFS-20) 
        end = detect_silence(snd.reverse(), snd.dBFS-20)
        trimmed = snd
        if start + end < len(snd): trimmed = snd[max(0, start-50):len(snd)-max(0, end-50)]
        final_snd = trimmed.fade_in(20).fade_out(20)
        final_snd.export(out, format='mp3')
    except Exception as e: raise ValueError(f"فشل تحميل الآية {ayah}")
    return out

def get_text(surah, ayah):
    try:
        # نستخدم النص البسيط لتفادي مشاكل الرسم العثماني المعقد
        r = requests.get(f'https://api.alquran.cloud/v1/ayah/{surah}:{ayah}/quran-simple')
        t = r.json()['data']['text']
        if surah!=1 and ayah==1: t = t.replace("بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ", "").strip()
        return t
    except: return "خطأ في النص"

def get_en_text(surah, ayah):
    try:
        r = requests.get(f'http://api.alquran.cloud/v1/ayah/{surah}:{ayah}/en.sahih')
        return r.json()['data']['text']
    except: return ""

def wrap_text(text, per_line):
    words = text.split()
    return '\n'.join([' '.join(words[i:i+per_line]) for i in range(0, len(words), per_line)])

# === 🧩 أهم دالة: إنشاء النص بسرعة وكفاءة ===
def create_text_clip(arabic, duration, target_w, scale_factor=1.0):
    words = arabic.split()
    wc = len(words)
    if wc > 60: base_fs, pl = 27, 10
    elif wc > 40: base_fs, pl = 32, 9
    elif wc > 25: base_fs, pl = 38, 8
    elif wc > 15: base_fs, pl = 43, 7
    else: base_fs, pl = 45, 6
    
    final_fs = int(base_fs * scale_factor)
    box_w = int(target_w * 0.9)
    
    # 1. معالجة العربي (التشكيل والعكس)
    wrapped_text = wrap_text(arabic, pl)
    reshaped_text = arabic_reshaper.reshape(wrapped_text)
    bidi_text = get_display(reshaped_text)
    
    # 2. استخدام TextClip (الأسرع مع ImageMagick)
    # ملاحظة: نستخدم method='caption' لأنه أفضل في التفاف النص أوتوماتيكياً
    # تأكد أن الخط يدعم العربي (Amiri مثلاً)
    txt_clip = TextClip(
        bidi_text, 
        font=FONT_PATH_ARABIC, 
        fontsize=final_fs, 
        color='white', 
        size=(box_w, None), 
        method='caption',
        align='center'
    ).set_duration(duration)
    
    return txt_clip.fadein(0.25).fadeout(0.25)

def create_english_clip(text, duration, target_w, scale_factor=1.0):
    final_fs = int(28 * scale_factor)
    box_w = int(target_w * 0.85)
    en_clip = TextClip(
        wrap_text(text, 10), 
        font=FONT_PATH_ENGLISH, 
        fontsize=final_fs, 
        color='#FFD700', 
        size=(box_w, None), 
        method='caption', 
        align='center'
    ).set_duration(duration)
    return en_clip.fadein(0.25).fadeout(0.25)

# ... (دالة pick_bg نفسها كما في الكود السابق) ...
LAST_BG = None
def pick_bg(user_key, custom_query=None):
    global LAST_BG
    if not user_key: return None
    try:
        rand_page = random.randint(1, 10)
        safe_filter = " no people"
        if custom_query and custom_query.strip():
            trans_q = GoogleTranslator(source='auto', target='en').translate(custom_query.strip())
            q = trans_q + safe_filter
        else:
            safe_topics = ['nature landscape', 'mosque architecture', 'sky clouds timelapse']
            q = random.choice(safe_topics) + safe_filter
        
        headers = {'Authorization': user_key}
        r = requests.get(f"https://api.pexels.com/videos/search?query={q}&per_page=15&page={rand_page}&orientation=portrait", headers=headers, timeout=10)
        if r.status_code == 401: return None
        vids = r.json().get('videos', [])
        if not vids: return None
        vid = random.choice(vids)
        f = next((vf for vf in vid['video_files'] if vf['width'] <= 1080 and vf['height'] > vf['width']), vid['video_files'][0])
        path = os.path.join(VISION_DIR, f"bg_{vid['id']}.mp4")
        if not os.path.exists(path):
            with requests.get(f['link'], stream=True) as rv:
                with open(path, 'wb') as f: shutil.copyfileobj(rv.raw, f)
        LAST_BG = path
        return path
    except: return LAST_BG

# ==========================================
# 🎬 بناء الفيديو (مع تحسين الذاكرة)
def build_video(user_pexels_key, reciter_id, surah, start, end=None, quality='720', bg_query=None):
    global current_progress
    final = None
    final_audio_clip = None
    bg = None
    
    try:
        current_progress['is_running'] = True
        add_log('🚀 بدء المعالجة السريعة...')
        clear_outputs()
        
        target_w, target_h = (1080, 1920) if quality == '1080' else (720, 1280)
        scale_factor = 1.0 if quality == '1080' else 0.67
        
        # التأكد من صحة الآيات
        s_name = SURAH_NAMES[surah-1] if surah <= len(SURAH_NAMES) else "Surah"
        # يمكنك إضافة التحقق من VERSE_COUNTS هنا
        last = end if end else start+5 # تقليل الحد الأقصى للآيات افتراضياً لتخفيف الحمل

        items = []
        full_audio_seg = AudioSegment.empty()
        
        # حلقة المعالجة
        for i, ayah in enumerate(range(start, last+1), 1):
            if current_progress.get('should_stop'): raise Exception("Stop")
            add_log(f'⏳ معالجة {ayah}...')
            
            # 1. الصوت
            ap = download_audio(reciter_id, surah, ayah, i)
            seg = AudioSegment.from_file(ap)
            full_audio_seg = full_audio_seg.append(seg, crossfade=100) if len(full_audio_seg) > 0 else seg
            clip_dur = seg.duration_seconds
            
            # 2. النص
            ar_txt = f"{get_text(surah, ayah)} ({ayah})"
            en_txt = get_en_text(surah, ayah)
            
            # تقسيم النص الطويل
            if len(ar_txt.split()) > 30:
                mid = len(ar_txt.split()) // 2
                items.append(( " ".join(ar_txt.split()[:mid]), " ".join(en_txt.split()[:len(en_txt.split())//2])+"...", clip_dur/2 ))
                items.append(( " ".join(ar_txt.split()[mid:]), "..."+" ".join(en_txt.split()[len(en_txt.split())//2:]), clip_dur/2 ))
            else:
                items.append((ar_txt, en_txt, clip_dur))

        # تصدير الصوت النهائي
        full_audio_seg.export(FINAL_AUDIO_PATH, format="mp3")
        final_audio_clip = AudioFileClip(FINAL_AUDIO_PATH)
        full_dur = final_audio_clip.duration
        
        # الخلفية
        add_log('🎨 الخلفية...')
        bg_path = pick_bg(user_pexels_key, bg_query)
        if not bg_path: raise ValueError("No Background")
        
        bg = VideoFileClip(bg_path)
        if bg.h != target_h: bg = bg.resize(height=target_h)
        bg = bg.crop(x1=bg.w//2 - target_w//2, width=target_w, height=target_h)
        bg = bg.fx(vfx.loop, duration=full_dur).subclip(0, full_dur)
        
        # تجميع الطبقات
        layers = [bg, ColorClip(bg.size, color=(0,0,0), duration=full_dur).set_opacity(0.6)]
        
        curr_t = 0.0
        y_pos = target_h * 0.40 
        
        for ar, en, dur in items:
            ac = create_text_clip(ar, dur, target_w, scale_factor).set_start(curr_t).set_position(('center', y_pos))
            ec = create_english_clip(en, dur, target_w, scale_factor).set_start(curr_t).set_position(('center', y_pos + ac.h + (30*scale_factor)))
            layers.extend([ac, ec])
            curr_t += dur
            
        final = CompositeVideoClip(layers).set_audio(final_audio_clip)
        fname = f"Quran_{surah}_{start}_{quality}.mp4"
        out = os.path.join(TEMP_DIR, fname)
        
        add_log('🎬 تصدير (Render)...')
        my_logger = QuranLogger()
        
        # 🔥 إعدادات الأداء القصوى 🔥
        # fps=15: كافية جداً لنصوص ثابتة وتوفر نصف الذاكرة مقارنة بـ 30
        # threads=1: تمنع تعليق السيرفر
        # preset='ultrafast': أسرع خيار تصدير
        final.write_videofile(
            out, 
            fps=15, 
            codec='libx264', 
            audio_bitrate='64k', 
            preset='ultrafast', 
            threads=1, 
            logger=my_logger,
            verbose=False,
            ffmpeg_params=['-crf', '30'] # تقليل الجودة قليلاً لزيادة السرعة
        )
        
        update_progress(100, 'تم!')
        current_progress['is_complete'] = True
        current_progress['output_path'] = out

    except Exception as e:
        logging.error(traceback.format_exc())
        current_progress['error'] = str(e)
        add_log(f"❌ {str(e)}")
    finally:
        # تنظيف سريع
        current_progress['is_running'] = False
        try:
            if final: final.close()
            if final_audio_clip: final_audio_clip.close()
            if bg: bg.close()
        except: pass
        # لا نستخدم gc.collect() هنا لتجنب التعليق، نترك النظام يديرها

# ... (Routes نفس الكود السابق: ui, gen, cancel, prog, conf, out, main) ...
# تأكد من نسخ الـ Routes من الكود السابق لإكمال الملف

@app.route('/')
def ui(): return send_file(UI_PATH) if os.path.exists(UI_PATH) else "UI Missing"

@app.route('/api/generate', methods=['POST'])
def gen():
    d = request.json
    if current_progress['is_running']: return jsonify({'error': 'Busy'}), 400
    user_key = d.get('pexelsKey')
    if not user_key: return jsonify({'error': 'API Key Missing'}), 400
    reset_progress()
    threading.Thread(target=build_video, args=(
        user_key, d.get('reciter'), int(d.get('surah')), int(d.get('startAyah')), 
        int(d.get('endAyah')) if d.get('endAyah') else None, d.get('quality', '720'), d.get('bgQuery')
    ), daemon=True).start()
    return jsonify({'ok': True})

@app.route('/api/cancel')
def cancel_process():
    global current_progress
    current_progress['should_stop'] = True
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
