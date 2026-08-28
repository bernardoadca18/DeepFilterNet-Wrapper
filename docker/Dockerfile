FROM nvidia/cuda:11.8.0-cudnn8-devel-ubuntu22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive
ENV RUST_VERSION=1.75.0
ENV PYTHON_VERSION=3.11

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    wget \
    git \
    pkg-config \
    libssl-dev \
    libhdf5-dev \
    patchelf \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-dev \
    python${PYTHON_VERSION}-venv \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python${PYTHON_VERSION} /usr/bin/python3 && \
    ln -sf /usr/bin/python${PYTHON_VERSION} /usr/bin/python

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain ${RUST_VERSION}
ENV PATH="/root/.cargo/bin:${PATH}"

RUN python3 -m pip install --upgrade pip setuptools wheel

RUN pip3 install maturin poetry

WORKDIR /build

COPY Cargo.toml Cargo.lock ./
COPY libDF ./libDF
COPY pyDF ./pyDF
COPY pyDF-data ./pyDF-data
COPY ladspa ./ladspa
COPY demo ./demo
COPY DeepFilterNet ./DeepFilterNet

RUN maturin build --release -m pyDF/Cargo.toml --find-interpreter

RUN maturin build --release -m pyDF-data/Cargo.toml --find-interpreter

FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHON_VERSION=3.11
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-venv \
    python3-pip \
    libsndfile1 \
    ffmpeg \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python${PYTHON_VERSION} /usr/bin/python3 && \
    ln -sf /usr/bin/python${PYTHON_VERSION} /usr/bin/python

RUN useradd -m -u 1000 -s /bin/bash appuser

WORKDIR /app

COPY --from=builder /build/target/wheels/*.whl /tmp/wheels/

COPY app/backend/requirements.txt ./requirements.txt

RUN pip3 install --no-cache-dir torch==2.1.0+cu118 torchaudio==2.1.0+cu118 \
    --index-url https://download.pytorch.org/whl/cu118

RUN pip3 install --no-cache-dir -r requirements.txt

RUN pip3 install --no-cache-dir /tmp/wheels/*cp311*.whl && rm -rf /tmp/wheels

COPY DeepFilterNet ./DeepFilterNet
ENV PYTHONPATH="/app/DeepFilterNet:${PYTHONPATH}"

COPY app/backend/main.py ./main.py
COPY app/backend/entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

RUN mkdir -p /app/model_cache /app/temp_files && \
    chown -R appuser:appuser /app

ENV MODEL_CACHE_DIR=/app/model_cache
ENV TEMP_FILES_DIR=/app/temp_files
ENV DEFAULT_MODEL=DeepFilterNet3

USER appuser

EXPOSE 8994

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8994/api/health || exit 1

ENTRYPOINT ["./entrypoint.sh"]
CMD ["python3", "main.py"]
