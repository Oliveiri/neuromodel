FROM pytorch/pytorch:2.4.0-cuda12.1-cudnn9-runtime

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    MKL_SERVICE_FORCE_INTEL=1

RUN apt-get update && apt-get install -y --no-install-recommends curl tini libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY hover_net-master/ ./hover_net-master/
COPY . .

EXPOSE 5004

ENV M3_GPU=0 \
    M3_MAX_BATCH_SIZE=64 \
    M3_SEGMENT_TIMEOUT_SEC=300

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
  CMD curl -fsS http://127.0.0.1:5004/readyz || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5004", "--workers", "2"]
