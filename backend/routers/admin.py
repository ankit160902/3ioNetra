import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from datetime import datetime
from config import settings
from services.panchang_service import get_panchang_service
from services.tts_service import get_tts_service
from services.context_validator import get_context_validator
from pydantic import BaseModel
from routers.dependencies import get_rag_pipeline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["admin"])

class TTSRequest(BaseModel):
    """Request body for TTS synthesis"""
    text: str
    lang: str = "hi"

# ----------------------------------------------------------------------------
# SYSTEM & HEALTH ENDPOINTS
# ----------------------------------------------------------------------------

@router.get("/health")
async def health_check():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": settings.API_VERSION,
        "rag_available": get_rag_pipeline().available if get_rag_pipeline() else False
    }

@router.get("/ready")
async def readiness_check():
    """System readiness check endpoint."""
    if not get_rag_pipeline() or not get_rag_pipeline().available:
        raise HTTPException(status_code=503, detail="RAG pipeline not ready")
    return {"status": "ready"}

# ----------------------------------------------------------------------------
# UTILITY ENDPOINTS
# ----------------------------------------------------------------------------

@router.get("/scripture/search")
async def search_scripture(
    query: str,
    scripture: Optional[str] = None,
    language: str = "en",
    limit: int = 5
):
    """Search scriptures directly."""
    pipeline = get_rag_pipeline()
    if not pipeline or not pipeline.available:
        raise HTTPException(status_code=503, detail="RAG system unavailable")

    results = await pipeline.search(
        query=query,
        scripture_filter=scripture,
        language=language,
        top_k=limit
    )
    validator = get_context_validator()
    results = validator.validate(docs=results, min_score=0.12, max_docs=limit)
    return {"query": query, "results": results, "count": len(results)}

@router.post("/embeddings/generate")
async def generate_embeddings(text: str):
    """Generate embeddings for text (utility endpoint)."""
    pipeline = get_rag_pipeline()
    if not pipeline or not pipeline.available:
        raise HTTPException(status_code=503, detail="RAG system unavailable")
    embeddings = await pipeline.generate_embeddings(text)
    return {"text": text, "embeddings": embeddings.tolist(), "dimension": len(embeddings)}

@router.get("/panchang/today")
async def get_today_panchang(lat: float = 28.6139, lon: float = 77.2090, tz: float = 5.5):
    """Get current Panchang for the given location."""
    panchang_service = get_panchang_service()
    if not panchang_service.available:
        raise HTTPException(status_code=503, detail="Panchang service unavailable")
    result = panchang_service.get_panchang(datetime.now(), latitude=lat, longitude=lon, timezone_offset=tz)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    result["special_info"] = panchang_service.get_special_day_info(result)
    return result

@router.post("/tts")
async def text_to_speech(request: TTSRequest):
    """Convert text to speech audio."""
    tts = get_tts_service()
    if not tts.available:
        raise HTTPException(status_code=503, detail="TTS unavailable")
    audio_buffer = tts.synthesize(request.text[:5000], lang=request.lang)
    if audio_buffer is None:
        raise HTTPException(status_code=500, detail="Synthesis failed")
    return StreamingResponse(
        audio_buffer,
        media_type="audio/mpeg",
        headers={"Content-Disposition": "inline; filename=tts.mp3", "Cache-Control": "public, max-age=3600"}
    )
