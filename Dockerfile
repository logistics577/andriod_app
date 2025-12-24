# -----------------------------
# Base image
# -----------------------------
FROM python:3.10-slim

# -----------------------------
# System dependencies for aiortc
# -----------------------------
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libavcodec-dev \
    libavformat-dev \
    libavdevice-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    libopus-dev \
    libvpx-dev \
    pkg-config \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------
# Working directory
# -----------------------------
WORKDIR /app

# -----------------------------
# Install Python dependencies
# -----------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# -----------------------------
# Copy application code
# -----------------------------
COPY . .

# -----------------------------
# Expose port (Render / Railway compatible)
# -----------------------------
EXPOSE 8000

# -----------------------------
# Run the app
# -----------------------------
CMD ["python3", "main.py"]
