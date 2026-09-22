FROM node:22-alpine AS frontend-build

WORKDIR /src/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CVINSIGHT_FRONTEND_DIST=/app/frontend/dist \
    CVINSIGHT_DATABASE_URL=sqlite:////var/lib/cvinsight/cvinsight.db \
    CVINSIGHT_BOOTSTRAP_FILES=/app/data/cvf_pre2022.csv,/app/data/cvf_2022_2025_full.csv \
    CVINSIGHT_CVF_CACHE_DIR=/var/lib/cvinsight/cvf-cache

WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/ /app/backend/
COPY data/ /app/data/
COPY --from=frontend-build /src/frontend/dist /app/frontend/dist

RUN mkdir -p /var/lib/cvinsight
WORKDIR /app/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
