from fastapi import APIRouter, File, HTTPException, UploadFile

from app import config, embeddings, ingestion, vectorstore

router = APIRouter(prefix="/api", tags=["ingestion"])

ALLOWED_UPLOAD_SUFFIXES = (".pdf", ".txt", ".md")


@router.get("/status")
def status():
    return {
        "chunk_count": vectorstore.count(),
        "collection": config.COLLECTION_NAME,
        "data_dir": str(config.DATA_DIR),
        "groq_model": config.GROQ_MODEL,
        "embedding_model": config.MISTRAL_MODEL,
    }


@router.post("/ingest")
def ingest():
    try:
        chunks = ingestion.build_chunks(config.DATA_DIR)
    except Exception as exc:
        raise HTTPException(
            502, f"Document extraction failed ({type(exc).__name__}): {exc}."
        ) from exc

    if not chunks:
        raise HTTPException(
            400,
            f"No PDF/.txt/.md documents found in {config.DATA_DIR}. "
            "Upload a requirements file first.",
        )

    try:
        vectorstore.reset_collection()
        vectors = embeddings.embed_documents([c["text"] for c in chunks])
        vectorstore.add_chunks(chunks, vectors)
    except Exception as exc:
        raise HTTPException(
            502,
            f"Ingestion pipeline failed during embedding/storage ({type(exc).__name__}): {exc}.",
        ) from exc

    return {
        "documents_ingested": len({c["source"] for c in chunks}),
        "chunk_count": len(chunks),
        "chunks": [
            {
                "id": c["id"],
                "source": c["source"],
                "chunk_index": c["chunk_index"],
                "char_count": c["char_count"],
                "est_tokens": c["est_tokens"],
                "extraction_method": c["extraction_method"],
                "preview": c["text"][:220],
            }
            for c in chunks
        ],
    }


@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(ALLOWED_UPLOAD_SUFFIXES):
        raise HTTPException(400, "Only .pdf, .txt, and .md files are supported")

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    dest = config.DATA_DIR / file.filename
    content = await file.read()
    dest.write_bytes(content)

    return {"saved": file.filename, "size_bytes": len(content)}
