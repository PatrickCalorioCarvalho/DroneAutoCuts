# base usada para suportar GPU quando estiver disponível
# na máquina de teste CPU esta imagem funciona normalmente, embora maior.
# caso queira voltar a imagem slim sem CUDA com o tempo, troque por python:3.11-slim
FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# pré-busca do peso YOLO para evitar demora no primeiro run
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

CMD ["python", "main.py"]