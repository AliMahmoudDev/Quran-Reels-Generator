FROM python:3.9-slim

# 1. تثبيت الحزم المطلوبة
RUN apt-get update && \
    apt-get install -y ffmpeg imagemagick libmagick++-dev ghostscript fonts-dejavu coreutils findutils && \
    apt-get clean

# ========================================================
# 🔥 تنفيذ الحل اللي في الفيديو (طريقة الحذف) 🔥
# الأمر ده هيدور على أي ملف policy.xml في النظام
# ويقوم بحذف السطر اللي بيعمل Block للـ Text والـ PDF نهائياً
# ========================================================
RUN find /etc -name "policy.xml" -exec sed -i '/pattern="@\*"/d' {} +

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# التأكد من المجلدات
RUN mkdir -p temp_videos temp_audio vision fonts

EXPOSE 8000

# تشغيل التطبيق (Thread واحد للأمان)
CMD ["gunicorn", "main:app", "--workers", "1", "--threads", "1", "--timeout", "120", "--bind", "0.0.0.0:8000"]
