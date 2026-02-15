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
from flask import Flask, request, jsonify, send_file, after_this_request
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

# Standardize Encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Paths
def app_dir():
    if getattr(sys, "frozen", False): return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

EXEC_DIR = app_dir()
BUNDLE_DIR = EXEC_DIR 

# FFMPEG Setup
FFMPEG_EXE = "ffmpeg" # Ensure this is in your PATH or specify full path
os.environ["FFMPEG_BINARY"] = FFMPEG_EXE
IM_MAGICK_EXE = "/usr/bin/convert" # Ensure this is correct for your server
change_settings({"IMAGEMAGICK_BINARY": IM_MAGICK_EXE})
AudioSegment.converter = FFMPEG_EXE
AudioSegment.ffmpeg = FFMPEG_EXE

# Asset Paths
FONT_DIR = os.path.join(EXEC_DIR, "fonts")
FONT_PATH_ARABIC = os.path.join(FONT_DIR, "Arabic.ttf") 
FONT_PATH_ENGLISH = os.path.join(FONT_DIR, "English.otf")
VISION_DIR = os.path.join(BUNDLE_DIR, "vision")
UI_PATH = os.path.join(BUNDLE_DIR, "UI.html")

# Master Temp Directory (We will create sub-folders inside this)
BASE_TEMP_DIR = os.path.join(EXEC_DIR, "temp_workspaces")
os.makedirs(BASE_TEMP_DIR, exist_ok=True)
os.makedirs(VISION_DIR, exist_ok=True)

# Data Constants
VERSE_COUNTS = {1: 7, 2: 286, 3: 200, 108: 3, 112: 4, 113: 5, 114: 6} # (Truncated for brevity, keep your full list)
SURAH_NAMES = ['الفاتحة', 'البقرة', 'آل عمران', 'الكوثر', 'الإخلاص', 'الفلق', 'الناس'] # (Truncated, keep full list)
RECITERS_MAP = {'ياسر الدوسري':'Yasser_Ad-Dussary_128kbps', 'الشيخ مشاري العفاسي': 'Alafasy_64kbps'} # (Truncated)

app = Flask(__name__, static_folder=EXEC_DIR)
CORS(app)

# ==========================================
# 🧠 Job Management (The Solution to Concurrency)
# ==========================================

# Global Dictionary to hold state for concurrent users
# Structure: { 'uuid_string': { 'percent': 0, 'status': '...', 'path': '...', ... } }
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
            'is_running': True,
            'is_complete': False,
            'output_path': None,
            'error': None,
            'should_stop': False,
            'created_at': time.time(),
            'workspace': job_dir  # Every user gets their own folder
        }
    return job_id

def update_job_status(job_id, percent, status):
    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id]['percent'] = percent
            JOBS[job_id]['status'] = status

def get_job(job_id):
    with JOBS_LOCK:
        return JOBS.get(job_id)

def cleanup_job(job_id):
    """Deletes temporary files and removes job from memory"""
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
    """
    Updates a SPECIFIC job_id in the global JOBS dict.
    Thread-safe because it writes to a specific key.
    """
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
                
                # Calculate ETA
                elapsed = time.time() - self.start_time
                rem_str = "00:00"
                if elapsed > 0 and value > 0:
                    rate = value / elapsed
                    remaining = (total - value) / rate
                    rem_str = str(datetime.timedelta(seconds=int(remaining)))[2:] if remaining > 0 else "00:00"
                
                update_job_status(self.job_id, percent, f"جاري التصدير... {percent}% (متبقي {rem_str})")

# ==========================================
# 🛠️ Helper Functions ( Stateless )
# ==========================================

def detect_silence(sound, thresh):
    t = 0
    while t < len(sound) and sound[t:t+10].dBFS < thresh: t += 10
    return t

def download_audio(reciter_id, surah, ayah, idx, workspace_dir):
    """Downloads audio to the specific job workspace"""
    url = f'https://everyayah.com/data/{reciter_id}/{surah:03d}{ayah:03d}.mp3'
    # Unique path inside the job's folder
    out = os.path.join(workspace_dir, f'part{idx}.mp3')
    
    try:
        r = requests.get(url, stream=True, timeout=30)
        with open(out, 'wb') as f:
            for chunk in r.iter_content(8192): f.write(chunk)
            
        snd = AudioSegment.from_file(out)
        # Silence removal logic...
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
    # (Same as your original code)
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

# (Keep create_text_clip and create_english_clip exactly as they were, 
#  just ensure they don't use global variables. They looked fine in your original code.)

def pick_bg(user_key, custom_query=None):
    # (Same as original, but ensure we don't log to global variable)
    if not user_key: return None
    try:
        rand_page = random.randint(1, 10)
        safe_filter = " no people"
        q = (custom_query + safe_filter) if custom_query else (random.choice(['nature', 'clouds', 'mosque']) + safe_filter)
        
        headers = {'Authorization': user_key}
        r = requests.get(f"https://api.pexels.com/videos/search?query={q}&per_page=15&page={rand_page}&orientation=portrait", headers=headers, timeout=15)
        if r.status_code == 401: return None
        vids = r.json().get('videos', [])
        if not vids: return None
        vid = random.choice(vids)
        f = next((vf for vf in vid['video_files'] if vf['width'] <= 1080 and vf['height'] > vf['width']), vid['video_files'][0])
        
        # We download the background to the COMMON Vision dir (caching is fine here)
        # OR download to workspace if you want total isolation. Let's keep common cache for speed.
        path = os.path.join(VISION_DIR, f"bg_{vid['id']}.mp4")
        if not os.path.exists(path):
            with requests.get(f['link'], stream=True) as rv:
                with open(path, 'wb') as f: shutil.copyfileobj(rv.raw, f)
        return path
    except: return None

# ==========================================
# 🎬 Main Processor
# ==========================================

def build_video_task(job_id, user_pexels_key, reciter_id, surah, start, end, quality, bg_query):
    """
    Main worker function. Everything is scoped to job_id and job['workspace'].
    """
    job = get_job(job_id)
    if not job: return

    workspace = job['workspace']
    final = None
    final_audio_clip = None
    bg = None
    
    try:
        update_job_status(job_id, 5, 'Downloading Audio & Text...')
        
        target_w, target_h = (1080, 1920) if quality == '1080' else (720, 1280)
        scale_factor = 1.0 if quality == '1080' else 0.67
        
        # Determine Ayah Range
        max_ayah = VERSE_COUNTS.get(surah, 286) # Default to max if unknown
        last = min(end if end else start+9, max_ayah)
        
        items = []
        full_audio_seg = AudioSegment.empty()
        
        # 1. Prepare Content
        for i, ayah in enumerate(range(start, last+1), 1):
            if get_job(job_id)['should_stop']: raise Exception("Stopped")
            
            update_job_status(job_id, 10 + int((i / (last-start+1)) * 20), f'Processing Ayah {ayah}...')
            
            # Download to specific workspace
            ap = download_audio(reciter_id, surah, ayah, i, workspace)
            
            ar_txt = f"{get_text(surah, ayah)} ({ayah})"
            en_txt = get_en_text(surah, ayah)
            
            seg = AudioSegment.from_file(ap)
            full_audio_seg = full_audio_seg.append(seg, crossfade=100) if len(full_audio_seg) > 0 else seg
            
            clip_dur = seg.duration_seconds
            
            # Text Splitting Logic (Simplified)
            items.append((ar_txt, en_txt, clip_dur))

        # 2. Audio Processing
        final_audio_path = os.path.join(workspace, "combined.mp3")
        full_audio_seg.export(final_audio_path, format="mp3")
        final_audio_clip = AudioFileClip(final_audio_path)
        full_dur = final_audio_clip.duration

        # 3. Background
        update_job_status(job_id, 40, 'Preparing Background...')
        bg_path = pick_bg(user_pexels_key, bg_query)
        if not bg_path: raise ValueError("Could not fetch background")
        
        bg = VideoFileClip(bg_path)
        # Resize Logic
        if bg.w/bg.h > target_w/target_h: bg = bg.resize(height=target_h)
        else: bg = bg.resize(width=target_w)
        bg = bg.crop(width=target_w, height=target_h, x_center=bg.w/2, y_center=bg.h/2)
        bg = bg.fx(vfx.loop, duration=full_dur).subclip(0, full_dur)
        
        layers = [bg, ColorClip(bg.size, color=(0,0,0), duration=full_dur).set_opacity(0.6)]
        
        # 4. Text Overlay
        curr_t = 0.0
        y_pos = target_h * 0.40 
        
        # Import local functions to avoid scope issues if they weren't defined above
        # (Assuming create_text_clip/create_english_clip are available globally in script)

        for ar, en, dur in items:
            if get_job(job_id)['should_stop']: raise Exception("Stopped")
            
            # Note: Ensure create_text_clip is thread-safe (it is, as long as it doesn't write to globals)
            ac = create_text_clip(ar, dur, target_w, scale_factor).set_start(curr_t).set_position(('center', y_pos))
            gap = 30 * scale_factor 
            ec = create_english_clip(en, dur, target_w, scale_factor).set_start(curr_t).set_position(('center', y_pos + ac.h + gap))
            
            layers.extend([ac, ec])
            curr_t += dur

        # 5. Rendering
        final = CompositeVideoClip(layers).set_audio(final_audio_clip)
        
        # Unique Filename
        output_filename = f"Quran_{surah}_{start}-{last}_{job_id[:8]}.mp4"
        output_full_path = os.path.join(workspace, output_filename)
        
        update_job_status(job_id, 50, 'Rendering Video...')
        
        # Use Scoped Logger
        my_logger = ScopedQuranLogger(job_id)
        
        final.write_videofile(
            output_full_path, 
            fps=24, 
            codec='libx264', 
            audio_bitrate='96k', 
            preset='ultrafast', 
            threads=4, 
            logger=my_logger, 
            ffmpeg_params=['-movflags', '+faststart', '-pix_fmt', 'yuv420p']
        )
        
        with JOBS_LOCK:
            JOBS[job_id]['output_path'] = output_full_path
            JOBS[job_id]['is_complete'] = True
            JOBS[job_id]['is_running'] = False
            JOBS[job_id]['percent'] = 100
            JOBS[job_id]['status'] = "Done! Ready for download."

    except Exception as e:
        err_msg = str(e)
        logging.error(f"Job {job_id} Error: {traceback.format_exc()}")
        with JOBS_LOCK:
            JOBS[job_id]['error'] = err_msg
            JOBS[job_id]['is_running'] = False
            JOBS[job_id]['status'] = "Error Occurred"
    finally:
        # Resource Cleanup
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
def ui(): return send_file(UI_PATH) if os.path.exists(UI_PATH) else "UI Missing"

@app.route('/api/generate', methods=['POST'])
def gen():
    d = request.json
    if not d.get('pexelsKey'): return jsonify({'error': 'Key Missing'}), 400

    # Create a unique job
    job_id = create_job()

    # Start thread with job_id
    threading.Thread(target=build_video_task, args=(
        job_id,
        d.get('pexelsKey'), 
        d.get('reciter'), 
        int(d.get('surah')), 
        int(d.get('startAyah')), 
        int(d.get('endAyah')) if d.get('endAyah') else None, 
        d.get('quality', '720'), 
        d.get('bgQuery')
    ), daemon=True).start()

    # Return the Job ID to the frontend
    return jsonify({'ok': True, 'jobId': job_id})

@app.route('/api/progress')
def prog():
    job_id = request.args.get('jobId')
    if not job_id: return jsonify({'error': 'No Job ID provided'}), 400
    
    job = get_job(job_id)
    if not job: return jsonify({'error': 'Job not found'}), 404
    
    # Return safe subset of data
    return jsonify({
        'percent': job['percent'],
        'status': job['status'],
        'is_complete': job['is_complete'],
        'error': job['error']
    })

@app.route('/api/download')
def download_result():
    job_id = request.args.get('jobId')
    job = get_job(job_id)
    
    if not job or not job['output_path'] or not os.path.exists(job['output_path']):
        return jsonify({'error': 'File not ready or expired'}), 404

    # Cleanup Trigger: When the request finishes sending the file, delete the temp folder
    @after_this_request
    def remove_file(response):
        try:
            # We delay slightly or just delete the folder
            cleanup_job(job_id)
        except Exception as e:
            print(f"Cleanup error: {e}")
        return response

    return send_file(job['output_path'], as_attachment=True)

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

if __name__ == "__main__":
    # Optional: Background thread to clean up very old stale jobs (e.g., > 1 hour)
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
