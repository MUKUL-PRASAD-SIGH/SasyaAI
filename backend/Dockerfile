FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

ARG EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
ENV EMBEDDING_MODEL=${EMBEDDING_MODEL}
ENV EMBEDDING_CACHE_DIR=/app/model-cache
RUN python -c "import os; from fastembed import TextEmbedding; next(iter(TextEmbedding(model_name=os.environ['EMBEDDING_MODEL'], cache_dir=os.environ['EMBEDDING_CACHE_DIR']).embed(['SasyaAI image warmup'])))"

COPY backend ./backend
COPY data ./data

ENV PYTHONPATH=/app/backend
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
