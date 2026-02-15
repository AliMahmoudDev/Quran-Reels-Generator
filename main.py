import sys
import io
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, VideoFileClip, AudioFileClip, CompositeVideoClip, ColorClip
import moviepy.video.fx.all as vfx
from moviepy.config import change_settings
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

# إعدادات المسارات
def app_dir():
    if getattr(sys, "frozen", False): return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

EXEC_DIR = app_dir()
BUNDLE_DIR = EXEC_DIR 

FFMPEG_EXE = "ffmpeg"
os.environ["FFMPEG_BINARY"] = FFMPEG_EXE
IM_MAGICK_EXE = "/usr/bin/convert"
change_settings({"IMAGEMAGICK_BINARY": IM_MAGICK_EXE})

FONT_DIR = os.path.join(EXEC_DIR, "fonts")
FONT_PATH_ARABIC = os.path.join(FONT_DIR, "Arabic.ttf") 
FONT_PATH_ENGLISH = os.path.join(FONT_DIR, "English.otf")
VISION_DIR = os.path.join(BUNDLE_DIR, "vision")
UI_PATH = os.path.join(BUNDLE_DIR, "UI.html")
INTERNAL_AUDIO_DIR = os.path.join(EXEC_DIR, "temp_audio")
TEMP_DIR = os.path.join(EXEC_DIR, "temp_videos")
FINAL_AUDIO_PATH = os.path.join(INTERNAL_AUDIO_DIR, "combined_final.mp3")

for d in [TEMP_DIR, INTERNAL_AUDIO_DIR, FONT_DIR, VISION_DIR]:
    os.makedirs(d, exist_ok=True)

# إدارة الجلسة (Global - تسبب تداخل المستخدمين)
current_progress = {'percent': 0, 'status': 'واقف', 'log': [], 'is_running': False, 'is_complete': False, 'output_path': None, 'should_stop': False, 'error': None}

app = Flask(__name__, static_folder=EXEC_DIR)
CORS(app)

def reset_progress():
    global current_progress
    current_progress = {'percent': 0, 'status': 'جاري التحضير...', 'log': [], 'is_running': False, 'is_complete': False, 'output_path': None, 'error': None, 'should_stop': False}

class QuranLogger(ProgressBarLogger):
    def bars_callback(self, bar, attr, value, old_value=None):
        if bar == 't':
            total = self.bars[bar]['total']
            if total > 0:
                percent = int((value / total) * 100)
                current_progress['percent'] = percent
                current_progress['status'] = f"جاري التصدير... {percent}%"

# (باقي الدوال المساعدة مثل download_audio و get_text كانت موجودة هنا)

def build_video(user_pexels_key, reciter_id, surah, start, end=None, quality='720', bg_query=None):
    global current_progress
    try:
        current_progress['is_running'] = True
        # مسح المجلدات الثابتة (يؤدي لمسح ملفات المستخدمين الآخرين)
        if os.path.isdir(INTERNAL_AUDIO_DIR): shutil.rmtree(INTERNAL_AUDIO_DIR)
        os.makedirs(INTERNAL_AUDIO_DIR, exist_ok=True)
        
        # منطق بناء الفيديو (نسخة بسيطة بخلفية واحدة)
        # ...
        
        current_progress['is_complete'] = True
        current_progress['is_running'] = False
    except Exception as e:
        current_progress['error'] = str(e)
        current_progress['is_running'] = False

@app.route('/api/generate', methods=['POST'])
def gen():
    if current_progress['is_running']: return jsonify({'error': 'Busy'}), 400
    reset_progress()
    d = request.json
    threading.Thread(target=build_video, args=(d['pexelsKey'], d['reciter'], int(d['surah']), int(d['startAyah'])), daemon=True).start()
    return jsonify({'ok': True})

@app.route('/api/progress')
def prog(): return jsonify(current_progress)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000)
