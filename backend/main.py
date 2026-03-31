"""
Main FastAPI application for 3ioNetra Spiritual Companion
Lean bootstrap script that orchestrates modular routers and heavy component initialization.
"""
import asyncio
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Request

# Increase thread pool to prevent exhaustion from hanging Gemini calls
asyncio.get_event_loop().set_default_executor(ThreadPoolExecutor(max_workers=128))
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager

from config import settings
from rag.pipeline import RAGPipeline

# Import routers after they are created
from routers import auth, chat, admin
from routers.dependencies import set_rag_pipeline

# Setup logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager for FastAPI tasks (Startup/Shutdown)"""
    logger.info("Starting 3ioNetra Spiritual Companion API Refinement Phase...")
    
    # 1. Initialize RAG Pipeline
    logger.info("Initializing RAG Pipeline (High Precision)...")
    rag_pipe = RAGPipeline()
    await rag_pipe.initialize()
    
    # 2. Inject RAG pipeline into routers (single shared reference)
    set_rag_pipeline(rag_pipe)
    
    # 3. Initialize other services
    from services.companion_engine import get_companion_engine
    companion_engine = get_companion_engine()
    companion_engine.set_rag_pipeline(rag_pipe)

    # 3b. Pre-initialize cache (surface Redis issues at boot, not first request)
    from services.cache_service import get_cache_service
    get_cache_service()

    # 3c. Pre-initialize ConceptOntology (loads SCO graph, avoids first-request latency)
    from services.concept_ontology import get_concept_ontology
    get_concept_ontology()

    # 4. Initialize query logger (async SQLite for RAG analytics)
    if settings.QUERY_LOG_ENABLED:
        from services.query_logger import get_query_logger
        await get_query_logger().initialize()

    logger.info("🎉 3ioNetra Backend Successfully Initialized!")
    
    yield
    
    # Shutdown logic
    logger.info("Shutting down 3ioNetra Spiritual Companion API...")
    
    # 1. Close Cache Connections
    from services.cache_service import get_cache_service
    cache_service = get_cache_service()
    await cache_service.close()
    
    # 2. Close MongoDB Connections
    from services.auth_service import close_mongo_client
    close_mongo_client()

    # 3. Close query logger
    if settings.QUERY_LOG_ENABLED:
        from services.query_logger import get_query_logger
        await get_query_logger().close()

    logger.info("👋 3ioNetra Backend Shutdown Complete.")

# Initialize FastAPI app
app = FastAPI(
    title="3ioNetra Spiritual Companion API",
    version=settings.API_VERSION,
    description="3ioNetra - A modularized, high-performance spiritual bot backend.",
    lifespan=lifespan
)

# Request latency middleware
class LatencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000)
        path = request.url.path
        # Only log API endpoints, skip static/health
        if path.startswith("/api") and path not in ("/api/health", "/api/ready"):
            logger.info(f"REQ_LATENCY {request.method} {path} {response.status_code} {elapsed_ms}ms")
        response.headers["X-Response-Time-Ms"] = str(elapsed_ms)
        return response

app.add_middleware(LatencyMiddleware)

# CORS middleware
_default_origins = [
    "https://3iomitra.3iosetu.com",
    "https://3io-netra.vercel.app",
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:8000",
    "http://localhost:8080",
]
_extra = os.environ.get("ALLOWED_ORIGINS", "")
_extra_origins = [o.strip() for o in _extra.split(",") if o.strip()] if _extra else []

app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins + _extra_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(admin.router)

@app.get("/")
async def root():
    return {
        "app": "3ioNetra API",
        "version": settings.API_VERSION,
        "mode": "modular_refined"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG
    )
