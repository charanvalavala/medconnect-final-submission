FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements-lock.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt -c backend/requirements-lock.txt
COPY backend ./backend
COPY database ./database
COPY scripts ./scripts
COPY schema.sql ./schema.sql
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
