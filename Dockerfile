FROM python:3.12-slim

# System dependency for OCR — this is the actual reason we need Docker at
# all; a plain "connect GitHub" Render deploy only installs Python packages,
# not OS-level binaries like tesseract.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render sets $PORT at runtime — don't hardcode 8000 here.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]