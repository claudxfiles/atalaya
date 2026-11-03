FROM node:22-slim AS interfaz
WORKDIR /f
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 ATALAYA_DATOS=/datos
WORKDIR /app
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/app ./backend/app
COPY --from=interfaz /f/dist ./frontend/dist
RUN useradd --create-home atalaya && mkdir /datos && chown -R atalaya /app /datos
USER atalaya
WORKDIR /app/backend
EXPOSE 8790
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8790}
