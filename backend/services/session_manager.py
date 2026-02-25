from typing import Optional, Dict
from datetime import datetime, timedelta
import logging

from models.session import SessionState, ConversationPhase
from config import settings

logger = logging.getLogger(__name__)


# ============================================================================
# Base Interface
# ============================================================================

class SessionManager:
    async def create_session(self, **kwargs) -> SessionState:
        raise NotImplementedError

    async def get_session(self, session_id: str) -> Optional[SessionState]:
        raise NotImplementedError

    async def update_session(self, session: SessionState) -> None:
        raise NotImplementedError

    async def delete_session(self, session_id: str) -> None:
        raise NotImplementedError

    async def transition_phase(
        self,
        session: SessionState,
        new_phase: ConversationPhase
    ) -> SessionState:
        session.phase = new_phase
        await self.update_session(session)
        return session


# ============================================================================
# In-Memory Session Manager (Local Dev)
# ============================================================================

class InMemorySessionManager(SessionManager):
    def __init__(self, ttl_minutes: int):
        self._sessions: Dict[str, SessionState] = {}
        self._ttl = timedelta(minutes=ttl_minutes)
        logger.info(f"InMemorySessionManager initialized (TTL={ttl_minutes}m)")

    async def create_session(self, min_signals=4, min_turns=3, max_turns=6) -> SessionState:
        session = SessionState(
            min_signals_threshold=min_signals,
            min_clarification_turns=min_turns,
            max_clarification_turns=max_turns
        )
        self._sessions[session.session_id] = session
        return session

    async def get_session(self, session_id: str) -> Optional[SessionState]:
        session = self._sessions.get(session_id)
        if not session:
            return None

        if datetime.utcnow() - session.last_activity > self._ttl:
            del self._sessions[session_id]
            return None

        session.last_activity = datetime.utcnow()
        return session

    async def update_session(self, session: SessionState) -> None:
        session.last_activity = datetime.utcnow()
        self._sessions[session.session_id] = session

    async def delete_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


# ============================================================================
# MongoDB Session Manager (Production)
# ============================================================================

class MongoSessionManager(SessionManager):
    def __init__(self, ttl_minutes: int):
        from services.auth_service import get_mongo_client

        self.db = get_mongo_client()
        self._ttl_seconds = ttl_minutes * 60
        
        if self.db is not None:
            self.collection = self.db.sessions
            self._ensure_indexes()
        else:
            self.collection = None
            logger.warning("MongoSessionManager: Database connection failed. Operations will be no-ops.")
        logger.info(f"MongoSessionManager initialized (TTL={ttl_minutes}m)")

    def _ensure_indexes(self):
        # This method is only called if self.db is not None, so self.collection is guaranteed to exist.
        indexes = self.collection.index_information()

        if "session_id_1" not in indexes:
            self.collection.create_index("session_id", unique=True)

        if "last_activity_1" not in indexes:
            self.collection.create_index(
                "last_activity",
                expireAfterSeconds=self._ttl_seconds
            )

    async def create_session(self, min_signals=4, min_turns=3, max_turns=6) -> SessionState:
        session = SessionState(
            min_signals_threshold=min_signals,
            min_clarification_turns=min_turns,
            max_clarification_turns=max_turns
        )
        await self.update_session(session)
        logger.info(f"🆕 Created session {session.session_id}")
        return session

    async def get_session(self, session_id: str) -> Optional[SessionState]:
        if self.collection is None: return None
        doc = self.collection.find_one({"session_id": session_id})
        if not doc:
            return None

        session = SessionState.from_dict(doc)

        # 🔥 CRITICAL: refresh activity on read
        session.last_activity = datetime.utcnow()
        await self.update_session(session)

        return session

    async def update_session(self, session: SessionState) -> None:
        if self.collection is None: return
        session.last_activity = datetime.utcnow()
        data = session.to_dict()

        self.collection.update_one(
            {"session_id": session.session_id},
            {"$set": data},
            upsert=True
        )

    async def delete_session(self, session_id: str) -> None:
        if self.collection is None: return
        self.collection.delete_one({"session_id": session_id})


# ============================================================================
# Redis Session Manager (Production-Grade)
# ============================================================================

class RedisSessionManager(SessionManager):
    def __init__(self, ttl_minutes: int):
        import redis
        import json
        
        self._ttl_seconds = ttl_minutes * 60
        self._redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True
        )
        logger.info(f"RedisSessionManager initialized (TTL={ttl_minutes}m)")
        
        # Test connection
        try:
            self._redis.ping()
            logger.info("✅ Redis connection established")
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            raise e

    async def create_session(self, min_signals=4, min_turns=3, max_turns=6) -> SessionState:
        session = SessionState(
            min_signals_threshold=min_signals,
            min_clarification_turns=min_turns,
            max_clarification_turns=max_turns
        )
        await self.update_session(session)
        logger.info(f"🆕 Created Redis session {session.session_id}")
        return session

    async def get_session(self, session_id: str) -> Optional[SessionState]:
        import json
        try:
            data = self._redis.get(f"session:{session_id}")
            if not data:
                return None
            
            session_dict = json.loads(data)
            return SessionState.from_dict(session_dict)
        except Exception as e:
            logger.error(f"Redis get_session error: {e}")
            return None

    async def update_session(self, session: SessionState) -> None:
        import json
        session.last_activity = datetime.utcnow()
        data = session.to_dict()
        
        try:
            # Store as JSON with TTL
            self._redis.setex(
                f"session:{session.session_id}",
                self._ttl_seconds,
                json.dumps(data)
            )
        except Exception as e:
            logger.error(f"Redis update_session error: {e}")

    async def delete_session(self, session_id: str) -> None:
        try:
            self._redis.delete(f"session:{session_id}")
        except Exception as e:
            logger.error(f"Redis delete_session error: {e}")


# ============================================================================
# Singleton Factory
# ============================================================================

_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """
    Singleton session manager.
    Redis is preferred for production, then MongoDB, then in-memory.
    """
    global _session_manager

    if _session_manager is None:
        ttl = settings.SESSION_TTL_MINUTES

        # 1. Try Redis first (High Performance)
        if settings.REDIS_HOST:
            try:
                _session_manager = RedisSessionManager(ttl)
                logger.info("🚀 Using Redis session storage")
                return _session_manager
            except Exception as e:
                logger.error(f"⚠️ Redis initialization failed: {e}")

        # 2. Try MongoDB (Persistence fallback)
        if settings.MONGODB_URI and settings.DATABASE_NAME:
            try:
                _session_manager = MongoSessionManager(ttl)
                logger.info("✅ Using MongoDB session storage")
            except Exception as e:
                logger.error(f"⚠️ MongoDB initialization failed: {e}")
                logger.warning("🔄 FALLBACK: Using in-memory session storage. Data will not persist.")
                _session_manager = InMemorySessionManager(ttl)
        else:
            logger.info("ℹ️ Using in-memory session storage")
            _session_manager = InMemorySessionManager(ttl)

    return _session_manager
