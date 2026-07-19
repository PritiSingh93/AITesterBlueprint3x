# QABuddyAI backend + ingestion (one image; the scheduler shells into it)
FROM python:3.11-slim

# git: needed for repo commit hashes + phase-2 `git pull` of the two frameworks
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common/ common/
COPY ingest/ ingest/
COPY backend/ backend/
COPY eval/ eval/
COPY config/ config/
COPY QABuddyAI_Generation_Prompt.md .

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
