# ============================================================
# Stage 1 — build do frontend (React/Vite)
# ============================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app

# Instala dependências primeiro (cache de camada Docker eficiente)
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm ci

# Copia o código e faz o build -> gera frontend/dist
COPY frontend/ ./frontend/
RUN cd frontend && npm run build


# ============================================================
# Stage 2 — runtime (FastAPI)
# ============================================================
FROM python:3.12-slim AS runtime

WORKDIR /app

# Dependências Python primeiro (cache de camada)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Preserva a árvore do repositório para que os caminhos relativos
# (BASE_DIR / static / templates / Relatorios_Metricas) funcionem
COPY main.py ./
COPY app/ ./app/
COPY templates/ ./templates/
COPY static/ ./static/
COPY Relatorios_Metricas/ ./Relatorios_Metricas/

# Frontend buildado (vindo do stage 1)
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

EXPOSE 8000

# $PORT é injetado pelo Render; fallback para 8000 em ambiente local
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
