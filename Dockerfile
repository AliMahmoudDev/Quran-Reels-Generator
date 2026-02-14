# 1. استخدام صورة بايثون خفيفة
FROM python:3.9-slim

# 2. تحديث النظام وتثبيت البرامج الضرورية (FFmpeg + ImageMagick + Ghostscript + الخطوط)
# Ghostscript مهم جداً لعمل النصوص
RUN apt-get update && \
    apt-get install -y ffmpeg imagemagick libmagick++-dev ghostscript fonts-dejavu coreutils && \
    apt-get clean

# ========================================================
# 🔥🔥🔥 الحل السحري لمشكلة MoviePy Error 🔥🔥🔥
# هذا السطر يقوم بتعديل ملف سياسة ImageMagick للسماح بقراءة النصوص
# ========================================================
RUN sed -i '/<policy domain="path" rights="none" pattern="@\*"/d' /etc/ImageMagick-6/policy.xml

# 3. إعداد مجلد العمل
WORKDIR /app

# 4. نسخ ملف المكتبات وتثبيتها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. نسخ باقي ملفات المشروع
COPY . .

# 6. إنشاء المجلدات الضرورية (لتجنب أخطاء التصريح)
RUN mkdir -p temp_videos temp_audio vision fonts

# 7. تحديد المنفذ
EXPOSE 8000

# 8. أمر التشغيل (Threads=1 لحماية الرامات)
CMD ["gunicorn", "main:app", "--workers", "1", "--threads", "1", "--timeout", "120", "--bind", "0.0.0.0:8000"]
