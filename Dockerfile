# استخدام بايثون 3.9
FROM python:3.9

# 1. تحديث النظام وتثبيت مكتبات الرسم الضرورية للنصوص العربية
# libfribidi-dev و libharfbuzz-dev هما السر لظهور العربي بشكل صحيح في Pillow
RUN apt-get update && \
    apt-get install -y \
    ffmpeg \
    libfribidi-dev \
    libharfbuzz-dev \
    libraqm-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. إعداد مجلد العمل
WORKDIR /app

# 3. نسخ مجلد الخطوط (تأكد أن اسمه fonts بنفس الحالة)
COPY fonts /app/fonts

# 4. نسخ المتطلبات وتثبيتها
COPY requirements.txt .
# ملاحظة: أحياناً نحتاج لإعادة تثبيت Pillow ليتعرف على المكتبات الجديدة
RUN pip install --no-cache-dir -r requirements.txt

# 5. نسخ باقي كود التطبيق
COPY . .

# 6. صلاحيات المجلدات (مهم لـ Hugging Face)
RUN mkdir -p temp_videos temp_audio vision && \
    chmod -R 777 temp_videos temp_audio vision /app

# 7. المنفذ
EXPOSE 7860

# 8. التشغيل
CMD ["gunicorn", "main:app", "--workers", "1", "--threads", "2", "--timeout", "120", "--bind", "0.0.0.0:7860"]
