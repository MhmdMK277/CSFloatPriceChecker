# ---- frontend build ---------------------------------------------------
FROM node:22-alpine AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- runtime -----------------------------------------------------------
FROM python:3.12-slim
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY data ./data
RUN pip install --no-cache-dir .

COPY --from=frontend /build/frontend/dist /app/static

ENV CSFLOAT_TRACKER_DATA=/data \
    CSFLOAT_TRACKER_STATIC=/app/static
VOLUME /data
EXPOSE 8422

CMD ["csfloat-tracker", "serve", "--host", "0.0.0.0", "--port", "8422"]
