"""
Configuration management for 3ioNetra Spiritual Companion
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""

    # ------------------------------------------------------------------
    # API Settings
    # ------------------------------------------------------------------
    API_TITLE: str = "3ioNetra Spiritual Companion API"
    API_VERSION: str = "1.1.3"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8080
    DEBUG: bool = False

    # ------------------------------------------------------------------
    # LLM Settings
    # ------------------------------------------------------------------
    GEMINI_MODEL: str = "gemini-2.5-pro"
    GEMINI_FAST_MODEL: str = "gemini-2.0-flash"  # lightweight model for intent/query expansion

    # Per-task LLM temperatures
    RESPONSE_TEMPERATURE: float = 0.7
    RESPONSE_MAX_TOKENS: int = 1024
    INTENT_TEMPERATURE: float = 0.1
    QUERY_TRANSLATE_TEMPERATURE: float = 0.1
    QUERY_EXPAND_TEMPERATURE: float = 0.3
    QUERY_SUMMARIZE_TEMPERATURE: float = 0.1
    HYDE_TEMPERATURE: float = 0.5
 
    # ------------------------------------------------------------------
    # Embedding Settings
    # ------------------------------------------------------------------
    EMBEDDING_MODEL: str = "intfloat/multilingual-e5-large"  # benchmark-validated: instruct variant scored lower (0.784 vs 0.840)
    EMBEDDING_DIM: int = 1024
    EMBEDDING_ONNX_ENABLED: bool = Field(default=False, env="EMBEDDING_ONNX_ENABLED")  # ONNX INT8 for ~30-50ms faster embedding
    EMBEDDING_ONNX_PATH: str = Field(default="./models/e5-large-onnx", env="EMBEDDING_ONNX_PATH")  # exported ONNX model path
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50

    # ------------------------------------------------------------------
    # Vector DB (Qdrant)
    # ------------------------------------------------------------------
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "sanatan_scriptures"
    VECTOR_DB_PATH: str = "./data/vector_db"

    # ------------------------------------------------------------------
    # RAG Settings
    # ------------------------------------------------------------------
    RETRIEVAL_TOP_K: int = 5          # benchmark: Hit@5 = Hit@7, no accuracy loss
    RERANK_TOP_K: int = 3
    MIN_SIMILARITY_SCORE: float = 0.28
    MAX_DOCS_PER_SOURCE: int = 2
    RAG_SEARCH_CACHE_TTL: int = Field(default=3600, env="RAG_SEARCH_CACHE_TTL")

    # RAG scoring & fusion
    RERANKER_WEIGHT: float = 0.75           # semantic weight = 1 - this (was 0.7, updated per RAKS report Section 8)
    INTENT_WEIGHT_SCALE: float = 0.3       # how much intent adjusts final score
    SOFT_FLOOR_RATIO: float = 0.75         # min_score * this = soft floor in search()
    CONTEXT_VERSE_SCORE_RATIO: float = 0.5 # parent-child context verse discount
    MIN_CANDIDATE_POOL: int = 40           # default pool; was 60 — adaptive sizing now handles per-intent
    CANDIDATE_POOL_MULTIPLIER: int = 5     # top_k * this = candidate pool target (legacy fallback)
    CANDIDATE_POOL_KEYWORD: int = 25       # simple ASKING_INFO queries
    CANDIDATE_POOL_DEFAULT: int = 40       # most queries
    CANDIDATE_POOL_THEMATIC: int = 50      # emotional/thematic queries
    CANDIDATE_POOL_COMPARATIVE: int = 60   # comparative queries needing broad retrieval
    CURATED_SLOT_LIMIT: int = 10           # max curated docs in slot reservation
    CURATED_VIABILITY_THRESHOLD: float = 0.5  # min score for curated doc injection
    EXPAND_TOP_N: int = 2                  # how many top docs get parent-child expansion
    CURATED_FLOOR: float = 0.35
    CURATED_RATIO: float = 0.6
    TRADITION_BONUS: float = 0.05
    SECTION_CHUNKS_ENABLED: bool = Field(default=False, env="SECTION_CHUNKS_ENABLED")
    SPLADE_ENABLED: bool = Field(default=False, env="SPLADE_ENABLED")
    SPLADE_MODEL: str = "naver/splade-cocondenser-ensembledistil"

    # Reranker skip — when top candidate is decisive, skip neural reranking
    SKIP_RERANK_THRESHOLD: float = Field(default=0.75, env="SKIP_RERANK_THRESHOLD")
    SKIP_RERANK_GAP: float = Field(default=0.15, env="SKIP_RERANK_GAP")

    # Content validation
    DYNAMIC_RELEVANCE_RATIO: float = 0.5   # top_score * this = dynamic floor
    MIN_CONTENT_LENGTH: int = 10           # min chars for content gate
    RELEVANCE_RATIO_EMOTIONAL: float = 0.40
    RELEVANCE_RATIO_CITATION: float = 0.55
    RELEVANCE_RATIO_COMPARATIVE: float = 0.25
    RELEVANCE_RATIO_GUIDANCE: float = 0.45
    RELEVANCE_RATIO_DEFAULT: float = 0.50
    MEMORY_DEDUP_THRESHOLD: float = 0.85
    MEMORY_MAX_RESULTS: int = 5
    MAX_DOCS_PER_TRADITION: int = 3
    MEMORY_SIMILARITY_THRESHOLD: float = 0.35  # min cosine sim for memory recall

    # Semantic Response Cache (saves 5-15s on repeat patterns)
    RESPONSE_CACHE_ENABLED: bool = Field(default=True, env="RESPONSE_CACHE_ENABLED")
    RESPONSE_CACHE_TTL: int = Field(default=21600, env="RESPONSE_CACHE_TTL")  # 6 hours
    RESPONSE_CACHE_SIMILARITY_THRESHOLD: float = Field(default=0.92, env="RESPONSE_CACHE_SIMILARITY_THRESHOLD")

    # HyDE (Hypothetical Document Embedding)
    HYDE_ENABLED: bool = Field(default=True, env="HYDE_ENABLED")
    HYDE_COUNT: int = Field(default=2, env="HYDE_COUNT")
    HYDE_CACHE_TTL: int = Field(default=86400, env="HYDE_CACHE_TTL")

    # Adaptive Fusion Logging
    LOG_FUSION_WEIGHTS: bool = Field(default=True, env="LOG_FUSION_WEIGHTS")

    # Parent-Child Verse Retrieval
    PARENT_CHILD_ENABLED: bool = Field(default=True, env="PARENT_CHILD_ENABLED")
    VERSE_CONTEXT_WINDOW: int = Field(default=1, env="VERSE_CONTEXT_WINDOW")

    # Long Query Summarization
    LONG_QUERY_SUMMARIZATION_ENABLED: bool = Field(default=True, env="LONG_QUERY_SUMMARIZATION_ENABLED")
    LONG_QUERY_THRESHOLD: int = Field(default=15, env="LONG_QUERY_THRESHOLD")

    # DharmicQueryObject → RAG pre-filtering
    DHARMIC_QUERY_RAG_ENABLED: bool = Field(default=True, env="DHARMIC_QUERY_RAG_ENABLED")

    # ------------------------------------------------------------------
    # Hybrid RAG / Retrieval Judge
    # ------------------------------------------------------------------
    HYBRID_RAG_ENABLED: bool = Field(default=True, env="HYBRID_RAG_ENABLED")
    JUDGE_MIN_SCORE: int = Field(default=4, env="JUDGE_MIN_SCORE")
    JUDGE_MAX_RETRIES: int = Field(default=1, env="JUDGE_MAX_RETRIES")
    JUDGE_CACHE_TTL: int = Field(default=86400, env="JUDGE_CACHE_TTL")
    GROUNDING_ENABLED: bool = Field(default=True, env="GROUNDING_ENABLED")
    GROUNDING_MIN_CONFIDENCE: float = Field(default=0.5, env="GROUNDING_MIN_CONFIDENCE")

    # ------------------------------------------------------------------
    # Conversation Flow
    # ------------------------------------------------------------------
    MIN_SIGNALS_THRESHOLD: int = 2
    MIN_CLARIFICATION_TURNS: int = 1
    MAX_CLARIFICATION_TURNS: int = 4
    SESSION_TTL_MINUTES: int = 60
    READINESS_POST_GUIDANCE: float = 0.3   # readiness reset after guidance phase

    # ------------------------------------------------------------------
    # Product Recommendation Throttling
    # ------------------------------------------------------------------
    PRODUCT_SESSION_CAP: int = 3                    # Max proactive product events per session
    PRODUCT_COOLDOWN_TURNS: int = 5                 # Min turns between proactive product events
    PRODUCT_COOLDOWN_AFTER_REJECTION: int = 10      # Cooldown turns after user rejects products
    PRODUCT_MIN_TURN_FOR_PROACTIVE: int = 3         # No proactive products before this turn
    PRODUCT_SUPPRESS_EMOTIONS: str = "grief,despair,hopelessness,crisis,shame"
    PRODUCT_GUIDANCE_CONTEXT_ENABLED: bool = True   # Allow context-based products in guidance phase
    PRODUCT_LISTENING_PROACTIVE_ENABLED: bool = False  # Disable proactive products in listening phase

    # ------------------------------------------------------------------
    # Safety / Crisis
    # ------------------------------------------------------------------
    ENABLE_CRISIS_DETECTION: bool = True
    CRISIS_HELPLINE_IN: str = (
        "iCall: 9152987821, Vandrevala: 1860-2662-345"
    )

    # ------------------------------------------------------------------
    # Scripture Data Paths
    # ------------------------------------------------------------------
    DATA_DIR: str = "./data"
    SCRIPTURES_DIR: str = "./data/scriptures"
    PROCESSED_DIR: str = "./data/processed"
    TRANSLATION_CACHE_PATH: str = "./data/cache/translations"

    # ------------------------------------------------------------------
    # MongoDB Settings
    # ------------------------------------------------------------------
    MONGODB_URI: str = Field(default="", env="MONGODB_URI")
    DATABASE_NAME: str = Field(default="", env="DATABASE_NAME")
    DATABASE_PASSWORD: str = Field(default="", env="DATABASE_PASSWORD")
    MONGO_MAX_POOL_SIZE: int = Field(default=10, env="MONGO_MAX_POOL_SIZE")
    MONGO_MIN_POOL_SIZE: int = Field(default=1, env="MONGO_MIN_POOL_SIZE")
    MONGO_MAX_IDLE_TIME_MS: int = Field(default=30000, env="MONGO_MAX_IDLE_TIME_MS")
    MONGO_READ_PREFERENCE: str = Field(default="primaryPreferred", env="MONGO_READ_PREFERENCE")
    MONGO_SERVER_SELECTION_TIMEOUT_MS: int = Field(default=30000, env="MONGO_SERVER_SELECTION_TIMEOUT_MS")
    MONGO_CONNECT_TIMEOUT_MS: int = Field(default=20000, env="MONGO_CONNECT_TIMEOUT_MS")
    MONGO_SOCKET_TIMEOUT_MS: int = Field(default=20000, env="MONGO_SOCKET_TIMEOUT_MS")
    ENABLE_AUTO_MIGRATIONS: bool = Field(default=True, env="ENABLE_AUTO_MIGRATIONS")
    MAX_CONVERSATIONS_PER_USER: int = Field(default=100, env="MAX_CONVERSATIONS_PER_USER")

    # ------------------------------------------------------------------
    # Redis Settings
    # ------------------------------------------------------------------
    REDIS_HOST: str = Field(default="localhost", env="REDIS_HOST")
    REDIS_PORT: int = Field(default=6379, env="REDIS_PORT")
    REDIS_DB: int = Field(default=0, env="REDIS_DB")
    CACHE_REDIS_DB: int = Field(default=0, env="CACHE_REDIS_DB")
    REDIS_PASSWORD: Optional[str] = Field(default=None, env="REDIS_PASSWORD")

    # ------------------------------------------------------------------
    # External API Keys
    # ------------------------------------------------------------------
    GEMINI_API_KEY: str = Field(default="", env="GEMINI_API_KEY")
    OPENAI_API_KEY: str = Field(default="", env="OPENAI_API_KEY")
    ANTHROPIC_API_KEY: str = Field(default="", env="ANTHROPIC_API_KEY")
    COHERE_API_KEY: str = Field(default="", env="COHERE_API_KEY")
    HUGGINGFACE_TOKEN: str = Field(default="", env="HUGGINGFACE_TOKEN")

    # ------------------------------------------------------------------
    # Evaluation Model Settings
    # ------------------------------------------------------------------
    EVAL_GEMINI_MODEL: str = "gemini-2.5-pro"
    EVAL_CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    EVAL_OPENAI_MODEL: str = "gpt-4o"
    EVAL_GEMINI_FAST_MODEL: str = "gemini-2.0-flash"
    EVAL_CLAUDE_HAIKU_MODEL: str = "claude-haiku-4-5-20251001"
    EVAL_OPENAI_MINI_MODEL: str = "gpt-4o-mini"

    # ------------------------------------------------------------------
    # Reranker Settings
    # ------------------------------------------------------------------
    # bge-reranker-v2-m3: multilingual, accurate but heavier (~200ms)
    # BAAI/bge-reranker-base: English-focused, lighter (~50ms) — use if most queries are English/Hindi
    RERANKER_MODEL: str = Field(default="BAAI/bge-reranker-v2-m3", env="RERANKER_MODEL")
    RERANKER_TYPE: str = "cross-encoder"  # "cross-encoder" or "api"

    # ------------------------------------------------------------------
    # Model Routing Settings
    # ------------------------------------------------------------------
    MODEL_ROUTING_ENABLED: bool = Field(default=True, env="MODEL_ROUTING_ENABLED")
    MODEL_ECONOMY: str = "gemini-2.0-flash"
    MODEL_STANDARD: str = "gemini-2.5-pro"
    MODEL_PREMIUM: str = "gemini-2.5-pro"
    MODEL_COST_TRACKING_ENABLED: bool = Field(default=False, env="MODEL_COST_TRACKING_ENABLED")

    # ------------------------------------------------------------------
    # Circuit Breaker Settings
    # ------------------------------------------------------------------
    CIRCUIT_BREAKER_THRESHOLD: int = 5
    CIRCUIT_BREAKER_TIMEOUT: int = 60

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./logs/app.log"

    # ------------------------------------------------------------------
    # Query Logging
    # ------------------------------------------------------------------
    QUERY_LOG_ENABLED: bool = Field(default=True, env="QUERY_LOG_ENABLED")
    QUERY_LOG_PATH: str = "./data/logs/queries.db"

    # ------------------------------------------------------------------
    # Pydantic Settings Config
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    allowed_origins: str = Field(default="http://localhost:3000", env="allowed_origins")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# ----------------------------------------------------------------------
# Global settings instance
# ----------------------------------------------------------------------
settings = Settings()
