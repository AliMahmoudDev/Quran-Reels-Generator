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
import subprocess  # [NEW] Needed for checking FFmpeg encoders
from functools import lru_cache
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

# Media Processing Imports
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import PIL.Image

# Patch for older PIL versions
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

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def app_dir():
    if getattr(sys, "frozen", False): return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

EXEC_DIR = app_dir()
BUNDLE_DIR = EXEC_DIR 

FFMPEG_EXE = "ffmpeg"
os.environ["FFMPEG_BINARY"] = FFMPEG_EXE

# ... (Keep existing Asset Paths and Data Constants: VERSE_COUNTS, SURAH_NAMES, RECITERS config) ...
# [PASTE YOUR EXISTING CONSTANTS HERE IF NOT INCLUDED BELOW FOR BREVITY]
# For the sake of the solution, assuming SURAH_NAMES, VERSE_COUNTS, RECITERS_MAP are defined here as in your original code.
# ...

# [Keep your existing Asset Paths]
FONT_DIR = os.path.join(EXEC_DIR, "fonts")
FONT_PATH_ARABIC = os.path.join(FONT_DIR, "Arabic.ttf") 
FONT_PATH_ENGLISH = os.path.join(FONT_DIR, "English.otf")
VISION_DIR = os.path.join(BUNDLE_DIR, "vision")
UI_PATH = os.path.join(BUNDLE_DIR, "UI.html")
BASE_TEMP_DIR = os.path.join(EXEC_DIR, "temp_workspaces")
os.makedirs(BASE_TEMP_DIR, exist_ok=True)
os.makedirs(VISION_DIR, exist_ok=True)

app = Flask(__name__, static_folder=EXEC_DIR)
CORS(app)

# ==========================================
# 🚀 NEW: Hardware Acceleration Helpers
# ==========================================

@lru_cache(maxsize=1)
def check_available_encoders():
    """
    Checks FFmpeg for available hardware encoders.
    Returns the best available codec and its specific optimization flags.
    """
    try:
        # Run ffmpeg -encoders to see what is supported
        cmd = [FFMPEG_EXE, "-encoders"]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output = result.stdout

        # Priority 1: NVIDIA NVENC
        if "h264_nvenc" in output:
            print("🚀 NVIDIA GPU Detected: Using h264_nvenc")
            return "h264_nvenc", [
                "-preset", "p1",       # p1 is fastest, p7 is best quality. p1-p3 is good for speed.
                "-cq", "20",           # Constant Quality (lower is better, 18-23 is sweet spot)
                "-rc", "vbr",          # Variable bitrate
                "-pix_fmt", "yuv420p"  # Ensure compatibility
            ]
        
        # Priority 2: Intel QSV (Quick Sync Video)
        elif "h264_qsv" in output:
            print("🚀 Intel QSV Detected: Using h264_qsv")
            return "h264_qsv", [
                "-global_quality", "20",
                "-preset", "veryfast",
                "-look_ahead", "0"
            ]
            
        # Priority 3: AMD AMF
        elif "h264_amf" in output:
            print("🚀 AMD GPU Detected: Using h264_amf")
            return "h264_amf", [
                "-usage", "transcoding",
                "-quality", "speed"
            ]

    except Exception as e:
        print(f"Encoder check failed: {e}. Falling back to CPU.")

    # Fallback: Optimized CPU
    print("⚠️ No GPU Detected: Using Optimized CPU (libx264)")
    return "libx264", [
        "-preset", "ultrafast",  # The fastest CPU preset
        "-crf", "23",            # Visually lossless balance
        "-tune", "zerolatency",  # Optimizes for fast encoding start
        "-movflags", "+faststart", # Web optimization
        "-pix_fmt", "yuv420p"
    ]

# ==========================================
# 🧠 Job Management (Unchanged)
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
# 📊 Scoped Logger (Unchanged)
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
# 🛠️ Helper Functions (Unchanged)
# ==========================================
# ... (Include get_cached_font, hex_to_rgb, detect_silence, smart_download, 
#      process_mp3quran_audio, download_audio, get_text, get_en_text, wrap_text) ...
# For brevity, assuming these exist as in your original code.

# [PASTE YOUR HELPER FUNCTIONS HERE]
@lru_cache(maxsize=10)
def get_cached_font(font_path, size):
    try: return ImageFont.truetype(font_path, size)
    except: return ImageFont.load_default()

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

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
                    if counter % 100 == 0: check_stop(job_id)

def process_mp3quran_audio(reciter_name, surah, ayah, idx, workspace_dir, job_id):
    # (Implementation from your code)
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

# ==========================================
# 🎨 Optimized Text Rendering (Unchanged)
# ==========================================
# (Keep create_combined_overlay exactly as is to preserve visual style)
def create_combined_overlay(surah, ayah, duration, target_w, target_h, scale_factor, use_glow, use_vignette, style_cfg):
    # ... [PASTE YOUR create_combined_overlay FUNCTION HERE] ...
    # Assuming the implementation provided in your prompt
    img = Image.new('RGBA', (target_w, target_h), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    if use_vignette:
        overlay = Image.new('RGBA', (target_w, target_h), (0,0,0,0))
        v_draw = ImageDraw.Draw(overlay)
        for i in range(int(target_h * 0.6), target_h, 2):
            alpha = int(180 * ((i - target_h * 0.6) / (target_h * 0.4)))
            v_draw.line([(0, i), (target_w, i)], fill=(0, 0, 0, alpha), width=2)
        img.alpha_composite(overlay)
    ar_color = style_cfg.get('arColor', '#ffffff')
    ar_scale = float(style_cfg.get('arSize', 1.0))
    ar_stroke_c = style_cfg.get('arOutC', '#000000')
    ar_stroke_w = int(float(style_cfg.get('arOutW', 4)) * scale_factor)
    ar_shadow_on = style_cfg.get('arShadow', False)
    ar_shadow_c = style_cfg.get('arShadowC', '#000000')
    en_color = style_cfg.get('enColor', '#FFD700')
    en_scale = float(style_cfg.get('enSize', 1.0))
    en_stroke_c = style_cfg.get('enOutC', '#000000')
    en_stroke_w = int(float(style_cfg.get('enOutW', 3)) * scale_factor)
    en_shadow_on = style_cfg.get('enShadow', False)
    en_shadow_c = style_cfg.get('enShadowC', '#000000')
    ar_text = f"{get_text(surah, ayah)} ({ayah})"
    words = ar_text.split()
    wc = len(words)
    if wc > 60: base_fs, pl = 30, 12
    elif wc > 40: base_fs, pl = 35, 10
    elif wc > 25: base_fs, pl = 41, 9
    elif wc > 15: base_fs, pl = 46, 8
    else: base_fs, pl = 48, 7
    final_ar_fs = int(base_fs * scale_factor * ar_scale)
    ar_font = get_cached_font(FONT_PATH_ARABIC, final_ar_fs)
    wrapped_ar = wrap_text(ar_text, pl)
    ar_lines = wrapped_ar.split('\n')
    line_metrics = []
    total_ar_h = 0
    GAP = 10 * scale_factor * ar_scale
    for l in ar_lines:
        bbox = draw.textbbox((0, 0), l, font=ar_font, stroke_width=ar_stroke_w)
        h = bbox[3] - bbox[1]
        line_metrics.append(h)
        total_ar_h += h + GAP
    en_text = get_en_text(surah, ayah)
    final_en_fs = int(30 * scale_factor * en_scale)
    en_font = get_cached_font(FONT_PATH_ENGLISH, final_en_fs)
    wrapped_en = wrap_text(en_text, 10)
    current_y = target_h * 0.35 
    for i, line in enumerate(ar_lines):
        bbox = draw.textbbox((0, 0), line, font=ar_font, stroke_width=ar_stroke_w)
        w = bbox[2] - bbox[0]
        x = (target_w - w) // 2
        if ar_shadow_on:
            offset = int(4 * scale_factor)
            draw.text((x + offset, current_y + offset), line, font=ar_font, fill=ar_shadow_c)
        if use_glow:
            try: glow_rgb = hex_to_rgb(ar_color)
            except: glow_rgb = (255,255,255)
            glow_rgba = glow_rgb + (50,)
            draw.text((x, current_y), line, font=ar_font, fill=glow_rgba, stroke_width=ar_stroke_w+5, stroke_fill=glow_rgba)
        draw.text((x, current_y), line, font=ar_font, fill=ar_color, stroke_width=ar_stroke_w, stroke_fill=ar_stroke_c)
        current_y += line_metrics[i] + GAP
    current_y += (20 * scale_factor)
    if en_shadow_on:
        offset = int(3 * scale_factor)
        draw.multiline_text(((target_w/2) + offset, current_y + offset), wrapped_en, font=en_font, fill=en_shadow_c, align='center', anchor="ma")
    draw.multiline_text((target_w/2, current_y), wrapped_en, font=en_font, fill=en_color, align='center', anchor="ma", stroke_width=en_stroke_w, stroke_fill=en_stroke_c)
    return ImageClip(np.array(img)).set_duration(duration).fadein(0.2).fadeout(0.2)

def fetch_video_pool(user_key, custom_query, count=1, job_id=None):
    # (Same as your original code)
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
                f = next((vf for vf in vid['video_files'] if vf['width'] <= 1080 and vf['height'] > vf['width']), None)
                if not f: 
                     if vid['video_files']: f = vid['video_files'][0]
                if f:
                    path = os.path.join(VISION_DIR, f"bg_{vid['id']}.mp4")
                    if not os.path.exists(path):
                        smart_download(f['link'], path, job_id)
                    pool.append(path)
    except Exception as e: print(f"Fetch Error: {e}")
    return pool

# ==========================================
# ⚡ Optimized Video Builder (Segmented)
# ==========================================
def build_video_task(job_id, user_pexels_key, reciter_id, surah, start, end, quality, bg_query, fps, dynamic_bg, use_glow, use_vignette, style_cfg):
    job = get_job(job_id)
    workspace = job['workspace']
    target_w, target_h = (1080, 1920) if quality == '1080' else (720, 1280)
    scale = 1.0 if quality == '1080' else 0.67
    last = min(end if end else start+9, VERSE_COUNTS.get(surah, 286))
    total_ayahs = (last - start) + 1
    
    try:
        # [Optimization] Fetch assets first
        vpool = fetch_video_pool(user_pexels_key, bg_query, count=total_ayahs if dynamic_bg else 1, job_id=job_id)
        
        if not vpool:
            base_bg_clip = ColorClip((target_w, target_h), color=(15, 20, 35))
        else:
            base_bg_clip = VideoFileClip(vpool[0]).resize(height=target_h).crop(width=target_w, height=target_h, x_center=target_w/2, y_center=target_h/2)

        dark_layer = ColorClip((target_w, target_h), color=(0,0,0)).set_opacity(0.45) 

        segments = []
        
        for i, ayah in enumerate(range(start, last+1)):
            check_stop(job_id)
            update_job_status(job_id, int((i / total_ayahs) * 80), f'Processing Ayah {ayah}...')

            ap = download_audio(reciter_id, surah, ayah, i, workspace, job_id)
            audioclip = AudioFileClip(ap)
            duration = audioclip.duration

            if dynamic_bg and i < len(vpool):
                bg_clip = VideoFileClip(vpool[i]).resize(height=target_h).crop(width=target_w, height=target_h, x_center=target_w/2, y_center=target_h/2)
            else:
                bg_clip = base_bg_clip
            
            if bg_clip.duration < duration:
                bg_clip = bg_clip.loop(duration=duration)
            else:
                max_start = max(0, bg_clip.duration - duration)
                start_t = random.uniform(0, max_start)
                bg_clip = bg_clip.subclip(start_t, start_t + duration)

            bg_clip = bg_clip.set_duration(duration).fadein(0.5).fadeout(0.5)

            overlay_clip = create_combined_overlay(surah, ayah, duration, target_w, target_h, scale, use_glow, use_vignette, style_cfg)
            
            # Combine
            segment = CompositeVideoClip([bg_clip, dark_layer.set_duration(duration), overlay_clip]).set_audio(audioclip)
            segments.append(segment)

        update_job_status(job_id, 85, "Merging & Rendering (Rocket Speed)...")
        final_video = concatenate_videoclips(segments, method="compose")
        
        out_p = os.path.join(workspace, f"out_{job_id}.mp4")
        
        # ==========================================
        # 🚀 OPTIMIZATION: Hardware Encode Check
        # ==========================================
        video_codec, ffmpeg_flags = check_available_encoders()
        
        # Calculate threads: Even with GPU, we need threads for MoviePy's Frame Compositing (Numpy)
        # Using all CPUs for composition, while GPU handles the compression.
        cpu_threads = os.cpu_count() or 4

        final_video.write_videofile(
            out_p, 
            fps=fps, 
            codec=video_codec,           # Use nvenc/qsv/libx264
            audio_codec='aac', 
            audio_bitrate='192k',        # Optimized audio bitrate
            threads=cpu_threads,         # Maximize CPU usage for frame generation
            ffmpeg_params=ffmpeg_flags,  # Inject GPU-specific flags
            logger=ScopedQuranLogger(job_id)
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
            if 'base_bg_clip' in locals(): base_bg_clip.close()
            for s in segments: s.close()
        except: pass
        gc.collect()

# (The rest of the Flask App Routes and background cleanup remain exactly the same)
@app.route('/')
def ui(): return send_file(UI_PATH) if os.path.exists(UI_PATH) else "API Running"

@app.route('/api/generate', methods=['POST'])
def gen():
    d = request.json
    job_id = create_job()
    style_cfg = d.get('style', {})
    threading.Thread(target=build_video_task, args=(
        job_id, d['pexelsKey'], d['reciter'], int(d['surah']), 
        int(d['startAyah']), int(d.get('endAyah',0)), 
        d.get('quality','720'), d.get('bgQuery',''), 
        int(d.get('fps',20)), d.get('dynamicBg',False), 
        d.get('useGlow',False), d.get('useVignette',False),
        style_cfg
    ), daemon=True).start()
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
