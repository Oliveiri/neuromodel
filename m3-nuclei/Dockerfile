FROM python:3.10-slim-bullseye

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    tini \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    proj-data \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./

ARG TURING_SEGMENT_PKG=turing_segment
ARG TURING_SEGMENT_PIP_INDEX_URL=
ARG TURING_SEGMENT_PIP_EXTRA_INDEX_URL=

RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt && \
    install_cmd="pip install -U \"$TURING_SEGMENT_PKG\"" && \
    if [ -n "$TURING_SEGMENT_PIP_INDEX_URL" ]; then \
      install_cmd="$install_cmd -i \"$TURING_SEGMENT_PIP_INDEX_URL\""; \
    fi && \
    if [ -n "$TURING_SEGMENT_PIP_EXTRA_INDEX_URL" ]; then \
      install_cmd="$install_cmd --extra-index-url \"$TURING_SEGMENT_PIP_EXTRA_INDEX_URL\""; \
    fi && \
    echo "[BUILD] $install_cmd" && eval "$install_cmd"

COPY . .

EXPOSE 5004

ENV M3_MAX_BATCH_SIZE=64 \
    M3_MAX_INFLIGHT_PER_REQUEST=8 \
    M3_GLOBAL_MAX_INFLIGHT=32 \
    M3_SEGMENT_TIMEOUT_SEC=120 \
    M3_MODEL_TYPE=he2 \
    M3_CHANNELS=0,1,2 \
    M3_IMAGE_TYPE=cv2

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:5004/readyz || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5004", "--workers", "2"]
