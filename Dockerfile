FROM python:3.9-bullseye

# 1. تثبيت الحزم المطلوبة (بما فيها الخطوط العربية)
RUN apt-get update && \
    apt-get install -y \
    ffmpeg \
    imagemagick \
    ghostscript \
    fonts-liberation \
    fonts-kacst \
    fonts-noto-color-emoji && \
    rm -rf /var/lib/apt/lists/*

# تثبيت ImageMagick
RUN apt-get update && apt-get install -y imagemagick

# تعديل سياسة الأمان للسماح لـ ImageMagick بقراءة وكتابة الملفات (مهم جداً لـ MoviePy)
RUN sed -i 's/domain="coder" rights="none" pattern="PDF"/domain="coder" rights="read|write" pattern="PDF"/' /etc/ImageMagick-6/policy.xml || true
RUN sed -i 's/domain="path" rights="none" pattern="@\*"/domain="path" rights="read|write" pattern="@\*"/' /etc/ImageMagick-6/policy.xml || true
# 3. إعداد مجلدات العمل
WORKDIR /app

# 4. نسخ ملفات المشروع وتثبيت المكتبات
COPY . .
RUN pip install --no-cache-dir -r requirements.txt

# 5. إنشاء مجلد مؤقت وإعطاؤه صلاحيات كاملة (عشان MoviePy يكتب فيه براحته)
RUN mkdir -p /app/my_temp && chmod 777 /app/my_temp

# 6. تعريف المتغيرات المهمة
ENV IMAGEMAGICK_BINARY=/usr/bin/convert
ENV TMPDIR=/app/my_temp

# 7. تشغيل التطبيق (تأكد إن اسم ملفك main.py)
CMD ["python", "main.py"]
