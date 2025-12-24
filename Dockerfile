FROM python:3.10-bullseye

# System deps (runtime only, not dev headers)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libopus0 \
    libvpx7 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["python3", "main.py"]
