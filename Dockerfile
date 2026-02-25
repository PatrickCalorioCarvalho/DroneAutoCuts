# base usada para suportar GPU quando estiver disponível
# na máquina de teste CPU esta imagem funciona normalmente, embora maior.
# caso queira voltar a imagem slim sem CUDA com o tempo, troque por python:3.11-slim
FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

# instalar Python3 e pip porque a imagem base não inclui
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# apontar "python" e "pip" para versões corretas
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 1 \
 && update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# pré-busca do peso YOLO para evitar demora no primeiro run
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

CMD ["python", "main.py"]