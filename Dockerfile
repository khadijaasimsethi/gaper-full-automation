FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Chromium + all its OS-level dependencies already come pre-installed in this base image

COPY . .

# Cloud Run sets PORT at runtime — make sure run.py reads this, not a hardcoded 8000
ENV PORT=8080
EXPOSE 8080

CMD ["python", "run.py", "--dashboard"]