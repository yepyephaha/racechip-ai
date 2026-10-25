FROM node:22-alpine AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements-lock.txt ./backend/requirements-lock.txt
RUN pip install --no-cache-dir -r backend/requirements-lock.txt
COPY backend ./backend
COPY data ./data
COPY --from=frontend /build/frontend/dist ./frontend/dist
COPY artifacts/live ./artifacts/live
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python","-m","uvicorn","app.main:app","--app-dir","backend","--host","0.0.0.0","--port","8000"]
