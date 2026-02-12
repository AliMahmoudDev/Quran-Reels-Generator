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

# 2. 🚨 الخطوة الحاسمة (كسر الحماية):
# الأمر ده بيدخل جوه ملف الإعدادات ويحول أي كلمة "none" (ممنوع) لـ "read|write" (مسموح)
# ده هيحل مشكلة TXT ومشكلة @ ومشكلة PDF مرة واحدة
RUN sed -i 's/rights="none"/rights="read|write"/g' /etc/ImageMagick-6/policy.xml

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
