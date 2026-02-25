
import shutil
import asyncio
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from src.config import config, DOCUMENTS_DIR
from src.rag_engine import RAGEngine
from src.document_ingestion import DocumentIngestionPipeline
from src.vector_store import get_vector_store
from src.logging_config import get_logger

logger = get_logger(__name__)

# Global Engine & Pipeline
rag_engine = None
ingestion_pipeline = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global rag_engine, ingestion_pipeline
    logger.info("Starting RAG Backend...")
    rag_engine = RAGEngine()
    
    # Check Health of LLM
    if not rag_engine.llm.check_health():
        logger.error("❌ LLM Health Check Failed on Startup")
    
    ingestion_pipeline = DocumentIngestionPipeline()
    logger.info("✅ RAG Backend Ready")
    yield  # Application runs here
    logger.info("Shutting down RAG Backend...")

app = FastAPI(title="RAG Locale API", version="1.0.0", lifespan=lifespan)

# CORS (Allow Frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development, allow all. In prod, strict list.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Models ---
class ChatRequest(BaseModel):
    message: str
    enableEvaluation: bool = False

class ChatResponse(BaseModel):
    text: str
    sources: List[dict]
    steps: List[dict] = []
    evaluation: Optional[dict] = None

class DocumentResponse(BaseModel):
    id: str
    name: str
    size: int
    indexed: bool

# --- Endpoints ---

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "RAG Locale"}

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    if not rag_engine:
        raise HTTPException(status_code=503, detail="RAG Engine not initialized")
    
    try:
        # Run blocking query in thread to avoid blocking event loop (Python 3.10+)
        response = await asyncio.to_thread(
            rag_engine.query,
            request.message,
            auto_approve_if_high_confidence=True
        )
        
        # Map RAGResponse to API format
        sources_data = [
            {
                "source": s.source,
                "section": s.section,
                "score": s.score,
                "snippet": s.document[:200] + "..."
            }
            for s in response.sources
        ]
        
        return {
            "text": response.answer,
            "sources": sources_data,
            "steps": [], # Future: expose reasoning steps
            "evaluation": None # Future: expose eval metrics
        }
    except Exception as e:
        logger.error(f"Chat Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/documents", response_model=List[DocumentResponse])
async def list_documents():
    # Use vector store metadata instead of filesystem scan for better performance
    vector_store = get_vector_store()
    indexed_files = vector_store.list_indexed_files()

    docs = []
    for filename in indexed_files:
        file_path = DOCUMENTS_DIR / filename
        size = file_path.stat().st_size if file_path.exists() else 0
        docs.append({
            "id": filename,
            "name": filename,
            "size": size,
            "indexed": True
        })
    return docs

@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    try:
        # FIX CRITICAL-2: Sanitizza filename per prevenire path traversal
        # Estrai solo il nome file base, mai il percorso completo
        from pathlib import Path as PathlibPath
        safe_filename = PathlibPath(file.filename).name

        if not safe_filename or safe_filename.startswith('.'):
            raise HTTPException(status_code=400, detail="Nome file non valido")

        # Verifica estensione file
        allowed_extensions = {'.pdf', '.txt', '.md', '.docx'}
        if PathlibPath(safe_filename).suffix.lower() not in allowed_extensions:
            raise HTTPException(status_code=400, detail="Tipo file non supportato")

        file_path = DOCUMENTS_DIR / safe_filename

        # Verifica che il path risolto sia dentro DOCUMENTS_DIR
        if not file_path.resolve().is_relative_to(DOCUMENTS_DIR.resolve()):
            raise HTTPException(status_code=400, detail="Path non autorizzato")

        # Save file
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Ingest - Process the single uploaded file
        if ingestion_pipeline:
            logger.info(f"🔍 Ingestione file: {file.filename}")
            try:
                chunks_count = ingestion_pipeline.ingest_single_file(file_path)
                logger.info(f"✓ File ingestito: {chunks_count} chunk creati")
                # Invalidate query cache so new document is immediately searchable
                if rag_engine:
                    rag_engine.invalidate_cache()
            except Exception as e:
                logger.error(f"✗ Errore ingestione: {e}")
                raise

        return {"filename": file.filename, "status": "uploaded and ingestion started"}
    except Exception as e:
        logger.error(f"Upload Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Run on port 5000 to match frontend's expected default
    # Run on localhost for security; use "0.0.0.0" only when deploying in Docker
    uvicorn.run(app, host="127.0.0.1", port=5000)
