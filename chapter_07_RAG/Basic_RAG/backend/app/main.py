from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import explorer, ingest, query

app = FastAPI(title="RAG Explorer API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router)
app.include_router(query.router)
app.include_router(explorer.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
