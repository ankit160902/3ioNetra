import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from datetime import datetime
from config import settings
from services.panchang_service import get_panchang_service
from services.tts_service import get_tts_service
from services.context_validator import get_context_validator
from services.auth_service import get_mongo_client
from services.cache_service import get_cache_service
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
    mongo_ok = False
    try:
        db = get_mongo_client()
        if db is not None:
            await asyncio.to_thread(db.command, "ping")
            mongo_ok = True
    except Exception as e:
        logger.warning(f"Health check: MongoDB unavailable: {e}")

    redis_ok = False
    try:
        cache = get_cache_service()
        redis_ok = cache.available
    except Exception as e:
        logger.warning(f"Health check: Redis unavailable: {e}")

    rag = get_rag_pipeline()
    rag_ok = rag.available if rag else False
    all_healthy = mongo_ok and redis_ok and rag_ok

    return {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.now().isoformat(),
        "version": settings.API_VERSION,
        "rag_available": rag_ok,
        "mongodb_available": mongo_ok,
        "redis_available": redis_ok,
    }

@router.get("/ready")
async def readiness_check():
    """System readiness check endpoint."""
    rag = get_rag_pipeline()
    if not rag or not rag.available:
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
        scripture_filter=[scripture] if scripture else None,
        language=language,
        top_k=min(limit, 50)
    )
    validator = get_context_validator()
    results = validator.validate(docs=results, query=query, min_score=settings.MIN_SIMILARITY_SCORE, max_docs=min(limit, 50))
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
    """Get current Panchang for the given location with enriched spiritual context."""
    panchang_service = get_panchang_service()
    if not panchang_service.available:
        raise HTTPException(status_code=503, detail="Panchang service unavailable")
    result = panchang_service.get_enriched_panchang(
        datetime.now(), latitude=lat, longitude=lon, timezone_offset=tz
    )
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
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
