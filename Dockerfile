FROM python:3.11-slim
ARG INSTALL_AI_PROFILE=1
ARG INSTALL_VIDEO_PROFILE=1
ARG INSTALL_LOCAL_MODEL=0
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libsm6 libxext6 libgl1 fonts-dejavu-core ca-certificates && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements-ai.txt requirements-video.txt requirements-local-model.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && if [ "$INSTALL_AI_PROFILE" = "1" ]; then \
         pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
         && pip install --no-cache-dir -r requirements-ai.txt; \
       fi \
    && if [ "$INSTALL_VIDEO_PROFILE" = "1" ]; then pip install --no-cache-dir -r requirements-video.txt; fi \
    && if [ "$INSTALL_LOCAL_MODEL" = "1" ]; then \
         pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
         && pip install --no-cache-dir -r requirements-local-model.txt; \
       fi
COPY backend ./backend
COPY ai_memory ./ai_memory
COPY knowledge ./knowledge
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
COPY config.yaml ./config.yaml
COPY scripts ./scripts
COPY docs/skill-parity-matrix.csv ./docs/skill-parity-matrix.csv
RUN mkdir -p /app/storage/chroma /app/storage/videos && useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["sh","-c","alembic upgrade head && exec uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1"]
