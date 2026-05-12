FROM pytorch/pytorch:2.4.0-cuda12.1-cudnn9-runtime

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends curl tini && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# 仅复制推理必需的模型权重和服务代码
COPY outputs/save_weights/best_model.pth outputs/save_weights/best_model.pth
COPY service.py ./
COPY src/ ./src/

EXPOSE 5003

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -fsS http://127.0.0.1:5003/healthz || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["bentoml", "serve", "service:PRccUnetService", "--host", "0.0.0.0", "--port", "5003"]
