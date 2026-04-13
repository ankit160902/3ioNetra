import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from datetime import datetime
from config import settings
from services.panchang_service import get_panchang_service
from services.tts_service import get_tts_service
from services.context_validator import get_context_validator
from pydantic import BaseModel
from routers.dependencies import get_rag_pipeline
from routers.auth import get_current_user

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

@router.post("/cache/flush")
async def flush_response_cache(user: dict = Depends(get_current_user)):
    """Flush stale response cache entries from Redis. Requires authentication."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    from services.cache_service import get_cache_service
    cache = get_cache_service()
    count = await cache.flush_prefix("response_semantic")
    return {"flushed": count}

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
        scripture_filter=[scripture] if scripture else None,
        language=language,
        top_k=min(limit, 50)
    )
    validator = get_context_validator()
    results = validator.validate(docs=results, query=query, min_score=settings.MIN_SIMILARITY_SCORE, max_docs=min(limit, 50))
    return {"query": query, "results": results, "count": len(results)}

@router.post("/embeddings/generate")
async def generate_embeddings(text: str, user: dict = Depends(get_current_user)):
    """Generate embeddings for text (utility endpoint). Requires authentication."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    pipeline = get_rag_pipeline()
    if not pipeline or not pipeline.available:
        raise HTTPException(status_code=503, detail="RAG system unavailable")
    embeddings = await pipeline.generate_embeddings(text)
    return {"text": text, "embeddings": embeddings.tolist(), "dimension": len(embeddings)}

def _resolve_tz_offset(tz_value: str) -> Optional[float]:
    """Resolve a timezone string to a numeric UTC offset in hours.

    Accepts:
      - Numeric strings: '5.5', '-8', '0'
      - IANA timezone names: 'Asia/Kolkata', 'America/New_York'
    Returns None if the value is neither.
    """
    # Try numeric first (backwards compat)
    try:
        return float(tz_value)
    except (ValueError, TypeError):
        pass

    # Try IANA timezone name
    try:
        from zoneinfo import ZoneInfo
        tz_info = ZoneInfo(tz_value)
        now = datetime.now(tz_info)
        offset_seconds = now.utcoffset().total_seconds()
        return offset_seconds / 3600
    except (KeyError, ImportError, AttributeError):
        return None

@router.get("/panchang/today")
async def get_today_panchang(lat: float = 28.6139, lon: float = 77.2090, tz: str = "5.5"):
    """Get current Panchang for the given location with enriched spiritual context.

    tz accepts either an IANA timezone name (e.g. 'Asia/Kolkata') or a
    numeric UTC offset (e.g. '5.5'). IANA names are resolved to the
    current UTC offset automatically.
    """
    panchang_service = get_panchang_service()
    if not panchang_service.available:
        raise HTTPException(status_code=503, detail="Panchang service unavailable")

    # Resolve tz: try numeric first (backwards compat), then IANA name
    tz_offset = _resolve_tz_offset(tz)
    if tz_offset is None:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid timezone: '{tz}'. Use IANA name (e.g. 'Asia/Kolkata') or numeric offset (e.g. '5.5').",
        )

    result = panchang_service.get_enriched_panchang(
        datetime.now(), latitude=lat, longitude=lon, timezone_offset=tz_offset
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
