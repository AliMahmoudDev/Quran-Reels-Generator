FROM python:3.9-bullseye

# 1. إعداد مسار العمل
WORKDIR /app

# 2. تثبيت الحزمة الكاملة (ffmpeg, imagemagick, ghostscript, fonts)
RUN apt-get update && \
    apt-get install -y \
    git \
    ffmpeg \
    imagemagick \
    ghostscript \
    fonts-liberation \
    fonts-kacst \
    fonts-noto-color-emoji && \
    rm -rf /var/lib/apt/lists/*

# 3. الحل الجذري لمشكلة Policy Error
# بدلاً من استبدال الملف، بنستخدم أمر sed لتعديل الصلاحيات داخل الملف الأصلي
# ده بيحول أي قيد (none) لسماح كامل (read|write)
RUN sed -i 's/rights="none"/rights="read|write"/g' /etc/ImageMagick-6/policy.xml

# 4. إنشاء مستخدم
RUN useradd -m -u 1000 user

# 5. نسخ الملفات وتثبيت المكتبات
COPY . .
RUN pip install --no-cache-dir -r requirements.txt

# 6. صلاحيات الملفات والمجلدات المؤقتة
# إنشاء مجلدات العمل وإعطاء صلاحيات كاملة 777
RUN mkdir -p /app/my_temp /app/temp_videos /app/temp_audio && \
    chmod -R 777 /app && \
    chown -R user:user /app

# 7. ضبط متغيرات البيئة (مهم جداً عشان MoviePy يشوف Imagemagick)
ENV IMAGEMAGICK_BINARY=/usr/bin/convert
ENV TMPDIR=/app/my_temp

# 8. التشغيل
USER user
CMD ["python", "main.py"]
