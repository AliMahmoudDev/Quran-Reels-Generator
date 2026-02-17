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
import json
import requests
import subprocess
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

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

NEW_RECITERS_CONFIG = {
     'ادريس أبكر': (12, "https://server6.mp3quran.net/abkr/"),
    'منصور السالمي': (245, "https://server14.mp3quran.net/mansor/"),
    'رعد الكردي': (221, "https://server6.mp3quran.net/kurdi/"),
}

OLD_RECITERS_MAP = {
    'أبو بكر الشاطري':'Abu_Bakr_Ash-Shaatree_128kbps',
    'ياسر الدوسري':'Yasser_Ad-Dussary_128kbps', 
    'الشيخ عبدالرحمن السديس': 'Abdurrahmaan_As-Sudais_64kbps', 
    'الشيخ ماهر المعيقلي': 'Maher_AlMuaiqly_64kbps', 
    'الشيخ سعود الشريم': 'Saood_ash-Shuraym_64kbps', 
    'الشيخ مشاري العفاسي': 'Alafasy_64kbps',
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
# 🛠️ Helper Functions
# ==========================================

session = requests.Session()

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def smart_download(url, dest_path, job_id, headers=None):
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0: return
    check_stop(job_id)
    with session.get(url, stream=True, timeout=30, headers=headers) as r:
        r.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk: f.write(chunk)
    check_stop(job_id)

def get_text(surah, ayah):
    try:
        t = session.get(f'https://api.alquran.cloud/v1/ayah/{surah}:{ayah}/quran-simple', timeout=10).json()['data']['text']
        if surah not in [1, 9] and ayah == 1:
            t = re.sub(r'^بِسْمِ [^ ]+ [^ ]+ [^ ]+', '', t).strip()
            t = t.replace("بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ", "").strip()
        return t
    except: return "Text Error"

def get_en_text(surah, ayah):
    try: return session.get(f'http://api.alquran.cloud/v1/ayah/{surah}:{ayah}/en.sahih', timeout=10).json()['data']['text']
    except: return ""

def wrap_text(text, per_line):
    words = text.split()
    return '\n'.join([' '.join(words[i:i+per_line]) for i in range(0, len(words), per_line)])

# ==========================================
# ⚡ PARALLEL VIDEO BUILDER ENGINE
# ==========================================
def build_video_task(job_id, user_pexels_key, reciter_id, surah, start, end, quality, bg_query, fps, dynamic_bg, use_glow, use_vignette, style_cfg):
    try:
        update_job_status(job_id, 1, "Loading Engine...")
        
        # --- LAZY IMPORTS ---
        import re
        import numpy as np
        from PIL import Image, ImageDraw, ImageFont
        import PIL.Image
        if not hasattr(PIL.Image, 'ANTIALIAS'): PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

        from moviepy.editor import (
            ImageClip, VideoFileClip, AudioFileClip, 
            CompositeVideoClip, ColorClip, concatenate_videoclips
        )
        from moviepy.config import change_settings
        from pydub import AudioSegment
        from deep_translator import GoogleTranslator

        try: change_settings({"IMAGEMAGICK_BINARY": os.getenv("IMAGEMAGICK_BINARY", "convert")})
        except: pass
        AudioSegment.converter = FFMPEG_EXE
        AudioSegment.ffmpeg = FFMPEG_EXE

        @lru_cache(maxsize=32)
        def get_cached_font(font_path, size):
            try: return ImageFont.truetype(font_path, size)
            except: return ImageFont.load_default()

        def detect_silence(sound, thresh):
            t = 0
            while t < len(sound) and sound[t:t+10].dBFS < thresh: t += 10
            return t

        def fetch_video_pool_optimized(count):
            pool = []
            if bg_query and len(bg_query) > 2:
                try: q_base = GoogleTranslator(source='auto', target='en').translate(bg_query.strip())
                except: q_base = "nature landscape"
            else:
                q_base = random.choice(['nature landscape', 'mosque architecture', 'sky clouds', 'galaxy stars', 'forest trees'])
            q = f"{q_base} no people"
            
            try:
                r = session.get(f"https://api.pexels.com/videos/search?query={q}&per_page={count+3}&orientation=portrait", headers={'Authorization': user_pexels_key}, timeout=15)
                if r.status_code == 200:
                    vids = r.json().get('videos', [])
                    random.shuffle(vids)
                    selected_vids = []
                    for vid in vids:
                        f = next((vf for vf in vid['video_files'] if vf['width'] <= 1080 and vf['height'] > vf['width']), None)
                        if not f and vid['video_files']: f = vid['video_files'][0]
                        if f: selected_vids.append((vid['id'], f['link']))
                        if len(selected_vids) >= count: break
                    
                    def dl_video(v_data):
                        vid_id, link = v_data
                        path = os.path.join(VISION_DIR, f"bg_{vid_id}.mp4")
                        if not os.path.exists(path): smart_download(link, path, job_id)
                        return path

                    with ThreadPoolExecutor(max_workers=5) as executor:
                        pool = list(executor.map(dl_video, selected_vids))
            except Exception as e: print(f"Fetch Error: {e}")
            return pool

        def create_optimized_overlay(surah, ayah, duration, target_w, target_h, scale_factor):
            # Init Canvas
            img = Image.new('RGBA', (target_w, target_h), (0,0,0,0))
            draw = ImageDraw.Draw(img)

            # Vectorized Vignette
            if use_vignette:
                if not hasattr(create_optimized_overlay, "vignette_cache"): create_optimized_overlay.vignette_cache = {}
                v_key = (target_w, target_h)
                if v_key not in create_optimized_overlay.vignette_cache:
                    Y, X = np.ogrid[:target_h, :target_w]
                    mask = np.clip((np.sqrt((X - target_w/2)**2 + (Y - target_h*0.7)**2) / np.sqrt((target_w/2)**2 + (target_h/2)**2)), 0, 1)
                    mask = (mask ** 2.5) * 200
                    v_img = Image.new('RGBA', (target_w, target_h), (0,0,0,0))
                    v_arr = np.array(v_img)
                    v_arr[:, :, 3] = mask.astype(np.uint8)
                    create_optimized_overlay.vignette_cache[v_key] = Image.fromarray(v_arr)
                img.alpha_composite(create_optimized_overlay.vignette_cache[v_key])

            # Configs
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

            # Arabic Text
            ar_text = f"{get_text(surah, ayah)} ({ayah})"
            wc = len(ar_text.split())
            if wc > 60: base_fs, pl = 30, 12
            elif wc > 40: base_fs, pl = 35, 10
            elif wc > 25: base_fs, pl = 41, 9
            elif wc > 15: base_fs, pl = 46, 8
            else: base_fs, pl = 48, 7
            
            ar_font = get_cached_font(FONT_PATH_ARABIC, int(base_fs * scale_factor * ar_scale))
            wrapped_ar = wrap_text(ar_text, pl)
            
            current_y = target_h * 0.35 
            GAP = 10 * scale_factor * ar_scale

            for line in wrapped_ar.split('\n'):
                bbox = draw.textbbox((0, 0), line, font=ar_font, stroke_width=ar_stroke_w)
                w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                x = (target_w - w) // 2
                
                if ar_shadow_on:
                    draw.text((x + int(4*scale_factor), current_y + int(4*scale_factor)), line, font=ar_font, fill=ar_shadow_c)
                if use_glow:
                    try: glow_rgb = hex_to_rgb(ar_color) + (50,)
                    except: glow_rgb = (255,255,255,50)
                    draw.text((x, current_y), line, font=ar_font, fill=glow_rgb, stroke_width=ar_stroke_w+5, stroke_fill=glow_rgb)
                draw.text((x, current_y), line, font=ar_font, fill=ar_color, stroke_width=ar_stroke_w, stroke_fill=ar_stroke_c)
                current_y += h + GAP

            # English Text
            en_text = get_en_text(surah, ayah)
            if en_text:
                current_y += (20 * scale_factor)
                en_font = get_cached_font(FONT_PATH_ENGLISH, int(30 * scale_factor * en_scale))
                wrapped_en = wrap_text(en_text, 10)
                if en_shadow_on:
                    draw.multiline_text(((target_w/2) + int(3*scale_factor), current_y + int(3*scale_factor)), wrapped_en, font=en_font, fill=en_shadow_c, align='center', anchor="ma")
                draw.multiline_text((target_w/2, current_y), wrapped_en, font=en_font, fill=en_color, align='center', anchor="ma", stroke_width=en_stroke_w, stroke_fill=en_stroke_c)

            return ImageClip(np.array(img)).set_duration(duration).fadein(0.2).fadeout(0.2)

        # --- ISOLATED WORKER FOR PARALLEL PROCESSING ---
        def process_ayah_segment(idx, ayah, bg_path, workspace):
            check_stop(job_id)
            out_audio = os.path.join(workspace, f'audio_{idx}.mp3')
            out_video = os.path.join(workspace, f'segment_{idx}.mp4')
            
            # 1. Prepare Audio
            if reciter_id in NEW_RECITERS_CONFIG:
                rid, server_url = NEW_RECITERS_CONFIG[reciter_id]
                cache_dir = os.path.join(EXEC_DIR, "cache_mp3quran", str(rid))
                os.makedirs(cache_dir, exist_ok=True)
                full_mp3 = os.path.join(cache_dir, f"{surah:03d}.mp3")
                timings_p = os.path.join(cache_dir, f"{surah:03d}.json")
                
                # Fetch Audio Logic
                if not os.path.exists(full_mp3) or not os.path.exists(timings_p):
                    time.sleep(random.uniform(0.1, 0.5))
                    if not os.path.exists(full_mp3):
                        smart_download(f"{server_url}{surah:03d}.mp3", full_mp3, job_id)
                        t_data = session.get(f"https://mp3quran.net/api/v3/ayat_timing?surah={surah}&read={rid}").json()
                        with open(timings_p, 'w') as f: json.dump({item['ayah']: {'start': item['start_time'], 'end': item['end_time']} for item in t_data}, f)
                
                with open(timings_p, 'r') as f: t = json.load(f)[str(ayah)]
                seg = AudioSegment.from_file(full_mp3)[t['start']:t['end']]
                seg.fade_in(50).fade_out(50).export(out_audio, format="mp3")
            else:
                url = f'https://everyayah.com/data/{reciter_id}/{surah:03d}{ayah:03d}.mp3'
                smart_download(url, out_audio, job_id)
                snd = AudioSegment.from_file(out_audio)
                start_s, end_s = detect_silence(snd, snd.dBFS-20), detect_silence(snd.reverse(), snd.dBFS-20)
                (AudioSegment.silent(duration=50) + snd[max(0, start_s-30):len(snd)-max(0, end_s-30)].fade_in(20).fade_out(20)).export(out_audio, format='mp3')

            # 2. Build Video Segment
            audioclip = AudioFileClip(out_audio)
            duration = audioclip.duration
            
            bg_clip = VideoFileClip(bg_path).resize(height=target_h).crop(width=target_w, height=target_h, x_center=target_w/2, y_center=target_h/2)
            if bg_clip.duration < duration: bg_clip = bg_clip.loop(duration=duration)
            else:
                max_start = max(0, bg_clip.duration - duration)
                start_t = random.uniform(0, max_start)
                bg_clip = bg_clip.subclip(start_t, start_t + duration)

            bg_clip = bg_clip.set_duration(duration).fadein(0.5).fadeout(0.5)
            overlay = create_optimized_overlay(surah, ayah, duration, target_w, target_h, scale)
            darken = ColorClip((target_w, target_h), color=(0,0,0)).set_opacity(0.45).set_duration(duration)
            
            # COMPOSITE & WRITE
            final = CompositeVideoClip([bg_clip, darken, overlay]).set_audio(audioclip)
            final.write_videofile(out_video, fps=fps, codec='libx264', audio_codec='aac', preset='ultrafast', threads=1, verbose=False, logger=None)
            
            final.close()
            bg_clip.close()
            audioclip.close()
            return out_video

        # --- MAIN EXECUTION ---
        job = get_job(job_id)
        workspace = job['workspace']
        target_w, target_h = (1080, 1920) if quality == '1080' else (720, 1280)
        scale = 1.0 if quality == '1080' else 0.67
        last = min(end if end else start+9, VERSE_COUNTS.get(surah, 286))
        total_ayahs = (last - start) + 1

        update_job_status(job_id, 5, "Fetching Assets...")
        vpool = fetch_video_pool_optimized(total_ayahs if dynamic_bg else 1)
        if not vpool: vpool = [os.path.join(VISION_DIR, "default.mp4")]
        if len(vpool) < total_ayahs and not dynamic_bg: vpool = [vpool[0]] * total_ayahs
        elif len(vpool) < total_ayahs: vpool = (vpool * (total_ayahs // len(vpool) + 1))[:total_ayahs]

        # PARALLEL PROCESSING START
        # Using a map to keep track of indices to ensure final concatenation order is correct
        future_to_index = {}
        seg_files = [None] * total_ayahs
        
        start_time = time.time()
        completed_count = 0

        with ThreadPoolExecutor(max_workers=min(os.cpu_count(), 4)) as executor:
            for i, ayah in enumerate(range(start, last+1)):
                bg_file = vpool[i] if dynamic_bg else vpool[0]
                future = executor.submit(process_ayah_segment, i, ayah, bg_file, workspace)
                future_to_index[future] = i

            # as_completed yields futures as they finish (Real-time updates!)
            for future in as_completed(future_to_index):
                check_stop(job_id)
                idx = future_to_index[future]
                try:
                    seg_files[idx] = future.result()
                    
                    # Update Progress and ETA
                    completed_count += 1
                    elapsed = time.time() - start_time
                    avg_time_per_ayah = elapsed / completed_count
                    remaining_ayahs = total_ayahs - completed_count
                    
                    eta_seconds = int(avg_time_per_ayah * remaining_ayahs)
                    eta_str = str(datetime.timedelta(seconds=eta_seconds))
                    if eta_seconds < 3600: eta_str = eta_str[2:] # Trim HH: if less than hour
                    
                    percent = 10 + int((completed_count / total_ayahs) * 85)
                    update_job_status(job_id, percent, f"Rendering ({completed_count}/{total_ayahs})", eta=eta_str)
                    
                except Exception as exc:
                    print(f"Verse processing generated an exception: {exc}")
                    raise exc

        # FAST CONCATENATION (Stream Copy)
        update_job_status(job_id, 98, "Final Stitching...", eta="00:00")
        list_path = os.path.join(workspace, "list.txt")
        with open(list_path, "w") as f:
            for path in seg_files:
                if path: f.write(f"file '{path}'\n")

        out_p = os.path.join(workspace, f"out_{job_id}.mp4")
        
        cmd = [FFMPEG_EXE, "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", "-y", out_p]
        subprocess.run(cmd, check=True)

        with JOBS_LOCK: JOBS[job_id].update({'output_path': out_p, 'is_complete': True, 'is_running': False, 'percent': 100, 'status': "Done!"})

    except Exception as e:
        msg = str(e)
        traceback.print_exc()
        with JOBS_LOCK: JOBS[job_id].update({'error': msg, 'status': "Cancelled" if msg == "Stopped" else "Error", 'is_running': False})
    finally:
        gc.collect()

@app.route('/')
def ui(): return send_file(UI_PATH) if os.path.exists(UI_PATH) else "API Running"

@app.route('/api/generate', methods=['POST'])
def gen():
    d = request.json
    job_id = create_job()
    threading.Thread(target=build_video_task, args=(
        job_id, d['pexelsKey'], d['reciter'], int(d['surah']), 
        int(d['startAyah']), int(d.get('endAyah',0)), 
        d.get('quality','720'), d.get('bgQuery',''), 
        int(d.get('fps',20)), d.get('dynamicBg',False), 
        d.get('useGlow',False), d.get('useVignette',False),
        d.get('style', {})
    ), daemon=True).start()
    return jsonify({'ok': True, 'jobId': job_id})

@app.route('/api/progress')
def prog(): return jsonify(get_job(request.args.get('jobId')))

@app.route('/api/download')
def download_result(): 
    job = get_job(request.args.get('jobId'))
    if job and job.get('output_path'): return send_file(job['output_path'], as_attachment=True)
    return "Not Found", 404

@app.route('/api/cancel', methods=['POST'])
def cancel_process():
    job_id = request.json.get('jobId')
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
            to_delete = [jid for jid, job in JOBS.items() if current_time - job['created_at'] > 3600]
            for jid in to_delete: del JOBS[jid]
        try:
            if os.path.exists(BASE_TEMP_DIR):
                for folder in os.listdir(BASE_TEMP_DIR):
                    if current_time - os.path.getctime(os.path.join(BASE_TEMP_DIR, folder)) > 3600:
                        shutil.rmtree(os.path.join(BASE_TEMP_DIR, folder), ignore_errors=True)
        except: pass

threading.Thread(target=background_cleanup, daemon=True).start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, threaded=True)
