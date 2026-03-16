# Python 3.9 slim image
FROM python:3.9-slim

# 1. تثبيت المتطلبات الأساسية
RUN apt-get update && apt-get install -y \
    ffmpeg \
    imagemagick \
    libfribidi-dev \
    libharfbuzz-dev \
    libraqm-dev \
    fonts-noto-core \
    fonts-noto-extra \
    && rm -rf /var/lib/apt/lists/*

# 2. إعداد ImageMagick policy لـ moviepy
RUN sed -i 's/rights="none" pattern="PDF"/rights="read|write" pattern="PDF"/g' /etc/ImageMagick-6/policy.xml 2>/dev/null || true

# 3. مجلد العمل
WORKDIR /app

# 4. نسخ الخطوط
COPY fonts /app/fonts

# 5. نسخ المتطلبات وتثبيتها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. نسخ باقي الكود
COPY . .

# 7. إنشاء المجلدات المطلوبة مع صلاحيات كاملة
# HF Spaces يحب أن تكون الملفات المؤقتة في /tmp أو /data
RUN mkdir -p /app/temp_workspaces \
             /app/outputs \
             /app/vision \
             /app/cache_mp3quran \
    && chmod -R 777 /app

# 8. متغيرات البيئة
ENV PYTHONIOENCODING=utf-8
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONUNBUFFERED=1

# 9. المنفذ المطلوب لـ Hugging Face
EXPOSE 7860

# 10. التشغيل
CMD ["python", "main.py"]
