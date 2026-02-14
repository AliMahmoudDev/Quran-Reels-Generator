# استخدام بايثون 3.9
FROM python:3.9

# 1. تثبيت ffmpeg و imagemagick
RUN apt-get update && \
    apt-get install -y ffmpeg imagemagick ghostscript && \
    apt-get clean

# 2. الحل الجذري والنهائي لمشكلة السياسة (ImageMagick Policy)
# بنمسح الملف القديم ونكتب واحد جديد يسمح بكل حاجة (Text + PDF)
RUN echo '<policymap><policy domain="path" rights="read|write" pattern="@*" /></policymap>' > /etc/ImageMagick-6/policy.xml

# 3. إعداد مجلد العمل
WORKDIR /app

# 4. نسخ وتثبيت المكتبات
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. نسخ باقي الملفات
COPY . .

# 6. إعطاء صلاحيات كاملة لمجلدات العمل (مهم جداً لـ Hugging Face)
RUN mkdir -p temp_videos temp_audio vision fonts && \
    chmod -R 777 temp_videos temp_audio vision fonts /app

# 7. البورت الرسمي لـ Hugging Face هو 7860
EXPOSE 7860

# تأكد من نسخ الخطوط ومنحها صلاحيات القراءة
COPY fonts /app/fonts
RUN chmod -R 755 /app/fonts

# 8. أمر التشغيل
CMD ["gunicorn", "main:app", "--workers", "1", "--threads", "1", "--timeout", "120", "--bind", "0.0.0.0:7860"]
