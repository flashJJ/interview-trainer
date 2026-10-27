# syntax=docker/dockerfile:1

# ---------- builder：独立 venv 装依赖，编译工具不进最终镜像 ----------
FROM python:3.13-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# chromadb 的 Rust/ONNX 绑定在个别平台缺预编译轮子，装最小工具链兜底；
# 装不上时这里会明确失败，而不是留到运行期才报 ImportError
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /build
COPY requirements.txt .
RUN pip install -r requirements.txt

# ---------- runtime ----------
FROM python:3.13-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/app \
    PATH="/opt/venv/bin:${PATH}"

# onnxruntime 运行期需要 libgomp1；slim 已自带 libstdc++
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 appgroup \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin appuser

# venv 在两阶段路径保持一致，控制台脚本的 shebang 才不会失效
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=10001:10001 app ./app
COPY --chown=10001:10001 seed.py ./
COPY --chown=10001:10001 scripts/reindex_embeddings.py ./scripts/
# 内置语料与题库是交付物，必须进镜像；运行时数据（db/chroma）走卷挂载
COPY --chown=10001:10001 data/builtin ./data/builtin
RUN mkdir -p /app/data/chroma && chown -R 10001:10001 /app/data

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --retries=6 --start-period=40s \
    CMD ["python", "-c", "import sys,urllib.request;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3).status==200 else 1)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
