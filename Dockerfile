# 1. بنستخدم نسخة Bullseye (الأكثر استقراراً وتوافقاً)
FROM python:3.9-bullseye

WORKDIR /app

# 2. تثبيت الحزمة الكاملة:
# - ffmpeg: للفيديو
# - imagemagick + ghostscript: للكتابة على الفيديو
# - fonts-kacst: خطوط عربية عشان الكلام ميظهرش مربعات
# - git: عشان نسحب الكود
RUN apt-get update && \
    apt-get install -y \
    git \
    ffmpeg \
    imagemagick \
    ghostscript \
    fonts-liberation \
    fonts-kacst && \
    rm -rf /var/lib/apt/lists/*

# 3. "الحل النووي": نسف ملف السياسات القديم وكتابة واحد جديد
# بيسمح بقراءة الملفات المؤقتة (@) والنصوص (TXT) والكتابة (read|write)
RUN echo '<policymap> \
    <policy domain="path" rights="read|write" pattern="@*" /> \
    <policy domain="coder" rights="read|write" pattern="TXT" /> \
    <policy domain="coder" rights="read|write" pattern="LABEL" /> \
</policymap>' > /etc/ImageMagick-6/policy.xml

# 4. إنشاء مستخدم (مهم لبعض المنصات زي HuggingFace)
RUN useradd -m -u 1000 user

# 5. سحب الكود (أول خطوة في الملفات عشان الفولدر يكون فاضي)
RUN git clone https://github.com/AliMahmoudDev/Quran-Reels-Generator.git .

# 6. تثبيت مكتبات بايثون
RUN pip install --no-cache-dir -r requirements.txt

# 7. إنشاء المجلدات وإعطاء صلاحيات "للجميع" (777)
# عملنا مجلد my_temp عشان نبعد عن مجلدات النظام المحمية
RUN mkdir -p /app/my_temp /app/temp_videos /app/vision /app/temp_audio && \
    chown -R user:user /app && \
    chmod -R 777 /app

# 8. توجيه متغيرات البيئة للفولدر المفتوح
ENV TMPDIR=/app/my_temp
ENV TEMP=/app/my_temp
ENV TMP=/app/my_temp
ENV IMAGEMAGICK_BINARY=/usr/bin/convert

# 9. التشغيل
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# هنا بنشغل التطبيق (تأكد إن main.py هو اسم ملفك الرئيسي)
CMD ["python", "main.py"]
