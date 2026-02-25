# DroneAutoCuts

Gerador automático de highlights para filmagens de drone.

## Configuração

1. Coloque os vídeos na pasta `input`.
2. Execute `python main.py` ou use o Docker Compose.

### Aceleração por hardware

- Os scripts podem usar aceleração por GPU para inferência YOLO e codificação do ffmpeg.
- Defina a variável de ambiente `USE_GPU=1` antes de rodar.
  - No Docker Compose, altere a seção `environment` correspondente.
- O `ffmpeg` adicionará automaticamente `-hwaccel cuda` e trocará o codec para `h264_nvenc`.
- O `Dockerfile` é baseado em `nvidia/cuda:12.1.1-cudnn8-runtime`, portanto já traz as bibliotecas CUDA.

> **Nota:** o ambiente atual pode ser só CPU; ativar `USE_GPU` não quebrará nada, o código simplesmente cairá de volta para CPU. Você pode testar as flags agora e depois mover o container para uma máquina com GPU.

### Docker com GPU

1. Instale o [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).
2. Em `docker-compose.yml` descomente `runtime: nvidia` ou a seção `deploy.resources`.
3. Defina `USE_GPU=1` no bloco de `environment`.
4. Inicie com `docker compose up --build`.

### Dicas de desempenho

- Em máquinas sem GPU, use `FFMPEG_CODEC` como `libx264` e `-preset fast` se quiser mais rapidez.
- Ajuste a constante `SKIP_FRAMES` em `core/intelligent_analysis.py` para amostrar menos quadros.
- Use opções `-preset` e `-crf` do ffmpeg para trocar qualidade por velocidade.

---

### Fluxo do projeto

```mermaid
flowchart LR
    A[Vídeos de entrada] --> B[NORMALIZE (1920x1080,30fps)]
    B --> C[MERGE]
    C --> D[DETECT SCENES]
    D --> E[ANALYZE SCENES (YOLO, nitidez, brilho, câmera)]
    E --> F[seleção top 20%]
    F --> G[BUILD HIGHLIGHT (cortes, LUT, aceleração)]
    G --> H[EXPORT VERTICAL]
    H --> I[Saída final]
```

Sinta-se à vontade para ajustar configurações e migrar para um host com GPU quando quiser!