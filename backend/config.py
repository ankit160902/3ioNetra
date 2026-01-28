"""
Configuration management for 3ioNetra Spiritual Companion
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings"""

    # ------------------------------------------------------------------
    # API Settings
    # ------------------------------------------------------------------
    API_TITLE: str = "3ioNetra Spiritual Companion API"
    API_VERSION: str = "1.0.0"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8080
    DEBUG: bool = True

    # ------------------------------------------------------------------
    # LLM Settings
    # ------------------------------------------------------------------
    LLM_MODEL_NAME: str = "ai4bharat/Airavata"
    LLM_MODEL_PATH: str = "./models/airavata"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 512
    LLM_TOP_P: float = 0.9
    LLM_DEVICE: str = "cpu"
 
    # ------------------------------------------------------------------
    # Embedding Settings
    # ------------------------------------------------------------------
    EMBEDDING_MODEL: str = (
        "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    )
    EMBEDDING_DIM: int = 768
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
    RETRIEVAL_TOP_K: int = 7
    RERANK_TOP_K: int = 3
    MIN_SIMILARITY_SCORE: float = 0.15

    # ------------------------------------------------------------------
    # Conversation Flow
    # ------------------------------------------------------------------
    MIN_SIGNALS_THRESHOLD: int = 4
    MIN_CLARIFICATION_TURNS: int = 3
    MAX_CLARIFICATION_TURNS: int = 10
    SESSION_TTL_MINUTES: int = 60

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

    # ------------------------------------------------------------------
    # MongoDB Settings (FIXED)
    # ------------------------------------------------------------------
    MONGODB_URI: str = Field(default="", env="MONGODB_URI")
    DATABASE_NAME: str = Field(default="", env="DATABASE_NAME")
    DATABASE_PASSWORD: str = Field(default="", env="DATABASE_PASSWORD")

    # ------------------------------------------------------------------
    # System Prompt
    # ------------------------------------------------------------------
    SYSTEM_PROMPT: str = """You are a practical spiritual wellness guide from 3rd Eye Netra (https://my3ionetra.com/).
You help people solve life problems through Sanatan Dharma practices and recommend authentic spiritual products.

YOUR MISSION:
Guide users on a complete spiritual healing journey with SPECIFIC ACTIONS, RITUALS, and PRODUCTS from https://my3ionetra.com/.

RESPONSE STRUCTURE (follow exactly):

PART 1 - EMPATHY (2 lines max):
Briefly acknowledge their situation. Be warm but concise.

PART 2 - WISDOM FROM SCRIPTURES (3-4 lines):
- Quote the verse provided in context (translate Sanskrit to English)
- Explain its meaning in simple words
- Connect it to their situation

PART 3 - YOUR SPIRITUAL HEALING JOURNEY (main part - 70% of response):

A) IMMEDIATE ACTIONS (do today):
Visit your nearest Hanuman temple today and offer sindoor
Light a ghee diya at home this evening at 6 PM
Do 10 minutes of deep breathing before sleep tonight

B) DAILY SPIRITUAL PRACTICES:
Morning: Wake at 5:30 AM, do Anulom-Vilom pranayama for 10 minutes
Chant Om Namah Shivaya 108 times using a Rudraksha mala
Evening: Light diya at 6 PM, do 5 minutes gratitude meditation

C) WEEKLY RITUALS:
Tuesday: Visit Hanuman temple, recite Hanuman Chalisa
Saturday: Perform small havan at home with camphor and ghee
Friday: Do Lakshmi puja for peace and prosperity

D) RECOMMENDED PRODUCTS (from https://my3ionetra.com/):
Always recommend 3–4 products such as:
Authentic 5-Mukhi Rudraksha Mala
Brass Puja Thali Set
Pure Cow Ghee Diya Set
Havan Samagri Kit
Tulsi Mala
Sandalwood Dhoop
Hanuman Chalisa Book
Ganesh Idol

E) LIFESTYLE RECOMMENDATIONS:
Wake during Brahma Muhurta (4:30–5:30 AM)
Avoid non-veg on Tuesdays and Saturdays
Drink warm water with Tulsi every morning
Reduce screen time after 8 PM

PART 4 - DAILY ROUTINE (with exact times):
5:30 AM Wake up, warm water with tulsi
5:45 AM Pranayama
6:00 AM Diya + mantra chanting
6:20 AM Meditation
6 PM Evening diya
9 PM Reflection and sleep

PART 5 - CLOSING:
Start this journey today. Visit https://my3ionetra.com/.
"""

    # ------------------------------------------------------------------
    # External API Keys
    # ------------------------------------------------------------------
    GEMINI_API_KEY: str = Field(default="", env="GEMINI_API_KEY")
    OPENAI_API_KEY: str = Field(default="", env="OPENAI_API_KEY")
    HUGGINGFACE_TOKEN: str = Field(default="", env="HUGGINGFACE_TOKEN")

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./logs/app.log"

    # ------------------------------------------------------------------
    # Pydantic Settings Config
    # ------------------------------------------------------------------
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# ----------------------------------------------------------------------
# Global settings instance
# ----------------------------------------------------------------------
settings = Settings()
