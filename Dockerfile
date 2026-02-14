FROM python:3.9-slim

# 1. تثبيت البرامج الأساسية
RUN apt-get update && \
    apt-get install -y ffmpeg imagemagick libmagick++-dev ghostscript fonts-dejavu coreutils && \
    apt-get clean

WORKDIR /app

# 2. نسخ ملف المكتبات وتثبيتها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ========================================================
# 🔥 الحل النهائي (الاستبدال الكامل) 🔥
# هنا بننسخ ملف السياسة المفتوح بتاعنا مكان ملف السيرفر المقفول
# ========================================================
COPY policy.xml /etc/ImageMagick-6/policy.xml

# 3. نسخ باقي ملفات المشروع
COPY . .

# التأكد من المجلدات
RUN mkdir -p temp_videos temp_audio vision fonts

EXPOSE 8000

# تشغيل التطبيق (Thread واحد فقط)
CMD ["gunicorn", "main:app", "--workers", "1", "--threads", "1", "--timeout", "120", "--bind", "0.0.0.0:8000"]
