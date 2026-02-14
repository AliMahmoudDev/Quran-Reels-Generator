# استخدام بايثون 3.9
FROM python:3.9

# 1. تثبيت الحزم الأساسية
# أضفت 'fontconfig' لضمان التعامل مع الخطوط بشكل صحيح
RUN apt-get update && \
    apt-get install -y ffmpeg imagemagick ghostscript fontconfig && \
    rm -rf /var/lib/apt/lists/*

# 2. تعديل سياسة ImageMagick (الطريقة الصحيحة)
# بدلاً من حذف الملف، نقوم بتعديل السطر الذي يمنع الكتابة فقط
# هذا يضمن بقاء باقي الإعدادات سليمة
RUN sed -i 's/none/read,write/g' /etc/ImageMagick-6/policy.xml

# 3. إعداد مجلد العمل
WORKDIR /app

# 4. نسخ مجلد الخطوط أولاً (مهم جداً)
COPY fonts /app/fonts

# === خطوة سحرية ===
# تحديث كاش الخطوط في لينكس ليتأكد النظام من وجود الخط العربي
RUN chmod -R 755 /app/fonts && fc-cache -f -v

# 5. نسخ وتثبيت المكتبات
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. نسخ باقي الملفات
COPY . .

# 7. إعطاء صلاحيات المجلدات (لضمان عمل Hugging Face بدون مشاكل permissions)
RUN mkdir -p temp_videos temp_audio vision && \
    chmod -R 777 temp_videos temp_audio vision /app

# متغير بيئة لمساعدة MoviePy في العثور على ImageMagick
ENV IMAGEMAGICK_BINARY=/usr/bin/convert

# 8. المنفذ
EXPOSE 7860

# 9. التشغيل
CMD ["gunicorn", "main:app", "--workers", "1", "--threads", "2", "--timeout", "120", "--bind", "0.0.0.0:7860"]
