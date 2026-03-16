# استخدام بايثون 3.9
FROM python:3.9

# 1. تحديث النظام وتثبيت المكتبات الضرورية
RUN apt-get update && \
    apt-get install -y \
    ffmpeg \
    git \
    libfribidi-dev \
    libharfbuzz-dev \
    libraqm-dev \
    fonts-liberation \
    fonts-kacst \
    && rm -rf /var/lib/apt/lists/*

# 2. إعداد مجلد العمل
WORKDIR /app

# 3. نسخ جميع الملفات من الـ repo (HuggingFace بيقللها تلقائياً)
COPY . .

# 4. تثبيت المتطلبات
RUN pip install --no-cache-dir -r requirements.txt

# 5. صلاحيات المجلدات (مهم لـ Hugging Face)
RUN mkdir -p temp_workspaces vision cache_mp3quran local_bgs && \
    chmod -R 777 /app

ENV PYTHONIOENCODING=utf-8
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# 6. المنفذ
EXPOSE 7860

# 7. التشغيل
CMD ["gunicorn", "main:app", "--workers", "1", "--threads", "4", "--timeout", "300", "--preload", "--bind", "0.0.0.0:7860"]
