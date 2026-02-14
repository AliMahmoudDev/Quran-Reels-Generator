FROM python:3.9-slim

# 1. تحديث النظام وتثبيت البرامج (بما فيها أدوات البحث)
RUN apt-get update && \
    apt-get install -y ffmpeg imagemagick libmagick++-dev ghostscript fonts-dejavu coreutils findutils && \
    apt-get clean

# ========================================================
# 🔥 الحل النووي (Brute Force Fix) 🔥
# هذا الأمر يبحث عن ملف policy.xml في أي مكان داخل /etc
# ويقوم باستبدال "none" بـ "read|write" للسماح بالكتابة
# ========================================================
RUN find /etc -name "policy.xml" -exec sed -i 's/rights="none" pattern="@\*"/rights="read|write" pattern="@*"/g' {} +

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# التأكد من المجلدات
RUN mkdir -p temp_videos temp_audio vision fonts

EXPOSE 8000

# تشغيل التطبيق بـ Thread واحد فقط
CMD ["gunicorn", "main:app", "--workers", "1", "--threads", "1", "--timeout", "120", "--bind", "0.0.0.0:8000"]
