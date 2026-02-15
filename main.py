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
        JOBS[job_id] = {
            'id': job_id,
            'percent': 0,
            'status': 'جاري التحضير...',
            'eta': '--:--',
            'is_running': True,
            'is_complete': False,
            'output_path': None,
            'error': None,
            'should_stop': False,
            'created_at': time.time(),
            'workspace': job_dir
        }
    return job_id

def update_job_status(job_id, percent, status, eta=None):
    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id]['percent'] = percent
            JOBS[job_id]['status'] = status
            if eta: JOBS[job_id]['eta'] = eta

def get_job(job_id):
    with JOBS_LOCK:
        return JOBS.get(job_id)

def cleanup_job(job_id):
    with JOBS_LOCK:
        job = JOBS.pop(job_id, None)
    
    if job and os.path.exists(job['workspace']):
        try:
            shutil.rmtree(job['workspace'])
            print(f"cleaned up workspace: {job_id}")
        except Exception as e:
            print(f"Error cleaning up {job_id}: {e}")

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
        if not job or job['should_stop']:
            raise Exception("Stopped by user")

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

def download_audio(reciter_id, surah, ayah, idx, workspace_dir):
    url = f'https://everyayah.com/data/{reciter_id}/{surah:03d}{ayah:03d}.mp3'
    out = os.path.join(workspace_dir, f'part{idx}.mp3')
    try:
        r = requests.get(url, stream=True, timeout=30)
        with open(out, 'wb') as f:
            for chunk in r.iter_content(8192): f.write(chunk)
        snd = AudioSegment.from_file(out)
        start = detect_silence(snd, snd.dBFS-20) 
        end = detect_silence(snd.reverse(), snd.dBFS-20)
        trimmed = snd
        if start + end < len(snd):
            trimmed = snd[max(0, start-30):len(snd)-max(0, end-30)]
        padding = AudioSegment.silent(duration=50) 
        final_snd = padding + trimmed.fade_in(20).fade_out(20)
        final_snd.export(out, format='mp3')
    except Exception as e: 
        raise ValueError(f"Download Error Surah {surah} Ayah {ayah}: {e}")
    return out

def get_text(surah, ayah):
    try:
        r = requests.get(f'https://api.alquran.cloud/v1/ayah/{surah}:{ayah}/quran-simple')
        t = r.json()['data']['text']
        if surah != 1 and ayah == 1: 
            t = t.replace("بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ", "").strip()
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

def create_text_clip(arabic, duration, target_w, scale_factor=1.0):
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
    for i, line in enumerate(lines):
        bbox = draw_final.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        start_x = (img_w - line_w) // 2
        draw_final.text((start_x+2, current_y+2), line, font=font, fill=(0,0,0,120))
        draw_final.text((start_x, current_y), line, font=font, fill='white')
        current_y += line_heights[i]
    return ImageClip(np.array(final_image)).set_duration(duration).fadein(0.25).fadeout(0.25)

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
    return ImageClip(np.array(img)).set_duration(duration).fadein(0.25).fadeout(0.25)

def pick_bg(user_key, custom_query=None):
    if not user_key or len(user_key) < 10: 
        print("Invalid or missing Pexels Key")
        return None
    try:
        rand_page = random.randint(1, 10)
        safe_filter = " no people"
        if custom_query and len(custom_query) > 2:
            try:
                trans_q = GoogleTranslator(source='auto', target='en').translate(custom_query.strip())
                q = trans_q + safe_filter
            except:
                q = "nature landscape" + safe_filter
        else:
            safe_topics = ['nature landscape', 'mosque architecture', 'sky clouds', 'galaxy stars', 'ocean waves']
            q = random.choice(safe_topics) + safe_filter
            
        headers = {'Authorization': user_key}
        r = requests.get(f"https://api.pexels.com/videos/search?query={q}&per_page=5&page={rand_page}&orientation=portrait", headers=headers, timeout=10)
        if r.status_code != 200: return None
        vids = r.json().get('videos', [])
        if not vids: return None
        vid = random.choice(vids)
        f = next((vf for vf in vid['video_files'] if vf['width'] <= 1080 and vf['height'] > vf['width']), vid['video_files'][0])
        path = os.path.join(VISION_DIR, f"bg_{vid['id']}.mp4")
        if not os.path.exists(path):
            with requests.get(f['link'], stream=True, timeout=20) as rv:
                with open(path, 'wb') as f_out: shutil.copyfileobj(rv.raw, f_out)
        return path
    except Exception as e:
        print(f"Background Error: {e}")
        return None

# ==========================================
# 🎬 Main Processor
# ==========================================
def build_video_task(job_id, user_pexels_key, reciter_id, surah, start, end, quality, bg_query, fps):
    job = get_job(job_id)
    if not job: return

    workspace = job['workspace']
    final = None
    final_audio_clip = None
    bg = None
    
    try:
        update_job_status(job_id, 5, 'Downloading Assets...')
        target_w, target_h = (1080, 1920) if quality == '1080' else (720, 1280)
        scale_factor = 1.0 if quality == '1080' else 0.67
        max_ayah = VERSE_COUNTS.get(surah, 286)
        last = min(end if end else start+9, max_ayah)
        
        items = []
        full_audio_seg = AudioSegment.empty()
        
        for i, ayah in enumerate(range(start, last+1), 1):
            if get_job(job_id)['should_stop']: raise Exception("Stopped")
            update_job_status(job_id, 10 + int((i / (last-start+1)) * 20), f'Processing Ayah {ayah}...')
            
            ap = download_audio(reciter_id, surah, ayah, i, workspace)
            ar_txt = f"{get_text(surah, ayah)} ({ayah})"
            en_txt = get_en_text(surah, ayah)
            
            seg = AudioSegment.from_file(ap)
            full_audio_seg = full_audio_seg.append(seg, crossfade=100) if len(full_audio_seg) > 0 else seg
            items.append((ar_txt, en_txt, seg.duration_seconds))

        # 2. Audio Processing
        final_audio_path = os.path.join(workspace, "combined.mp3")
        full_audio_seg.export(final_audio_path, format="mp3")
        final_audio_clip = AudioFileClip(final_audio_path)
        full_dur = final_audio_clip.duration

        # 3. Background Setup
        update_job_status(job_id, 40, 'Preparing Background...')
        bg_path = pick_bg(user_pexels_key, bg_query)
        
        if bg_path and os.path.exists(bg_path):
            bg = VideoFileClip(bg_path)
            bg = bg.resize(height=target_h)
            bg = bg.crop(width=target_w, height=target_h, x_center=bg.w/2, y_center=bg.h/2)
            bg = bg.fx(vfx.loop, duration=full_dur).subclip(0, full_dur)
            layers = [bg, ColorClip(bg.size, color=(0,0,0), duration=full_dur).set_opacity(0.6)]
        else:
            print("Using Fallback Background")
            bg_color = ColorClip((target_w, target_h), color=(15, 20, 35), duration=full_dur)
            layers = [bg_color]

        # 4. Text Overlay
        curr_t = 0.0
        y_pos = target_h * 0.40 
        
        for ar, en, dur in items:
            if get_job(job_id)['should_stop']: raise Exception("Stopped")
            ac = create_text_clip(ar, dur, target_w, scale_factor).set_start(curr_t).set_position(('center', y_pos))
            gap = 30 * scale_factor 
            ec = create_english_clip(en, dur, target_w, scale_factor).set_start(curr_t).set_position(('center', y_pos + ac.h + gap))
            layers.extend([ac, ec])
            curr_t += dur

        # 5. Rendering
        final = CompositeVideoClip(layers).set_audio(final_audio_clip)
        
        # ✅ NEW: Add Fade Out (Video & Audio) - 0.2s
        final = final.fadeout(0.2).audio_fadeout(0.2)

        output_filename = f"Quran_{surah}_{start}-{last}_{job_id[:8]}.mp4"
        output_full_path = os.path.join(workspace, output_filename)
        
        update_job_status(job_id, 50, f'Rendering ({fps} FPS)...')
        my_logger = ScopedQuranLogger(job_id)
        
        available_threads = os.cpu_count() or 2
        
        final.write_videofile(
            output_full_path, 
            fps=fps,
            codec='libx264', 
            audio_codec='aac',    
            audio_bitrate='64k',  
            preset='ultrafast',   
            threads=available_threads,
            logger=my_logger, 
            ffmpeg_params=['-movflags', '+faststart', '-pix_fmt', 'yuv420p', '-crf', '30']
        )
        
        with JOBS_LOCK:
            JOBS[job_id]['output_path'] = output_full_path
            JOBS[job_id]['is_complete'] = True
            JOBS[job_id]['is_running'] = False
            JOBS[job_id]['percent'] = 100
            JOBS[job_id]['eta'] = "00:00"
            JOBS[job_id]['status'] = "Done! Ready for download."

    except Exception as e:
        err_msg = str(e)
        logging.error(f"Job {job_id} Error: {traceback.format_exc()}")
        with JOBS_LOCK:
            JOBS[job_id]['error'] = err_msg
            JOBS[job_id]['is_running'] = False
            JOBS[job_id]['status'] = "Error Occurred"
    finally:
        try:
            if final: final.close()
            if final_audio_clip: final_audio_clip.close()
            if bg: bg.close()
            del final, final_audio_clip, bg
        except: pass
        gc.collect()

# ==========================================
# 🌐 API Routes
# ==========================================
@app.route('/')
def ui(): 
    if not os.path.exists(UI_PATH): return "API Running."
    return send_file(UI_PATH)

@app.route('/api/generate', methods=['POST'])
def gen():
    d = request.json
    if not d.get('pexelsKey'): return jsonify({'error': 'Key Missing'}), 400
    try:
        user_fps = int(d.get('fps', 20))
        if user_fps > 30: user_fps = 30 
        if user_fps < 10: user_fps = 10
    except:
        user_fps = 20

    job_id = create_job()
    threading.Thread(target=build_video_task, args=(
        job_id, d.get('pexelsKey'), d.get('reciter'), int(d.get('surah')), 
        int(d.get('startAyah')), int(d.get('endAyah')) if d.get('endAyah') else None, 
        d.get('quality', '720'), d.get('bgQuery'), user_fps
    ), daemon=True).start()
    return jsonify({'ok': True, 'jobId': job_id})

@app.route('/api/progress')
def prog():
    job_id = request.args.get('jobId')
    if not job_id: return jsonify({'error': 'No Job ID provided'}), 400
    job = get_job(job_id)
    if not job: return jsonify({'error': 'Job not found'}), 404
    return jsonify({
        'percent': job['percent'], 
        'status': job['status'], 
        'eta': job.get('eta', '--:--'),
        'is_complete': job['is_complete'], 
        'is_running': job['is_running'], 
        'output_path': job['output_path'], 
        'error': job['error']
    })

@app.route('/api/download')
def download_result():
    job_id = request.args.get('jobId')
    job = get_job(job_id)
    if not job or not job['output_path'] or not os.path.exists(job['output_path']):
        return jsonify({'error': 'File not ready or expired'}), 404
    
    filename = os.path.basename(job['output_path'])
    return send_file(
        job['output_path'], 
        as_attachment=True, 
        download_name=filename,
        mimetype='video/mp4'
    )

@app.route('/api/cancel', methods=['POST'])
def cancel_process():
    d = request.json
    job_id = d.get('jobId')
    if job_id:
        with JOBS_LOCK:
            if job_id in JOBS:
                JOBS[job_id]['should_stop'] = True
                JOBS[job_id]['status'] = "Cancelling..."
    return jsonify({'ok': True})

@app.route('/api/config')
def conf(): return jsonify({'surahs': SURAH_NAMES, 'verseCounts': VERSE_COUNTS, 'reciters': RECITERS_MAP})

# ==========================================
# 🧹 Automatic Garbage Collector
# ==========================================
def background_cleanup():
    while True:
        time.sleep(3600)
        print("🧹 Running automatic cleanup...")
        current_time = time.time()
        
        with JOBS_LOCK:
            to_delete = []
            for jid, job in JOBS.items():
                if current_time - job['created_at'] > 3600:
                    to_delete.append(jid)
            for jid in to_delete:
                del JOBS[jid]

        try:
            if os.path.exists(BASE_TEMP_DIR):
                for folder in os.listdir(BASE_TEMP_DIR):
                    folder_path = os.path.join(BASE_TEMP_DIR, folder)
                    if os.path.isdir(folder_path):
                        if current_time - os.path.getctime(folder_path) > 3600:
                            shutil.rmtree(folder_path, ignore_errors=True)
                            print(f"🗑️ Auto-deleted old workspace: {folder}")
        except Exception as e:
            print(f"Cleanup Error: {e}")

threading.Thread(target=background_cleanup, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
