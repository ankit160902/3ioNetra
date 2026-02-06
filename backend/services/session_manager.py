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
        self.collection = self.db.sessions
        self._ttl_seconds = ttl_minutes * 60

        self._ensure_indexes()
        logger.info(f"MongoSessionManager initialized (TTL={ttl_minutes}m)")

    def _ensure_indexes(self):
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
        doc = self.collection.find_one({"session_id": session_id})
        if not doc:
            return None

        session = SessionState.from_dict(doc)

        # 🔥 CRITICAL: refresh activity on read
        session.last_activity = datetime.utcnow()
        await self.update_session(session)

        return session

    async def update_session(self, session: SessionState) -> None:
        session.last_activity = datetime.utcnow()
        data = session.to_dict()

        self.collection.update_one(
            {"session_id": session.session_id},
            {"$set": data},
            upsert=True
        )

    async def delete_session(self, session_id: str) -> None:
        self.collection.delete_one({"session_id": session_id})


# ============================================================================
# Singleton Factory
# ============================================================================

_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """
    Singleton session manager.
    MongoDB is preferred if configured, otherwise in-memory.
    """
    global _session_manager

    if _session_manager is None:
        ttl = settings.SESSION_TTL_MINUTES

        if settings.MONGODB_URI and settings.DATABASE_NAME:
            try:
                _session_manager = MongoSessionManager(ttl)
                logger.info("✅ Using MongoDB session storage")
            except Exception as e:
                logger.error(f"❌ FATAL: MongoDB initialization failed: {e}")
                # Critical: Do not fallback to memory if DB is explicitly configured.
                # This prevents silent data loss in production environments.
                raise e
        else:
            logger.info("ℹ️ Using in-memory session storage")
            _session_manager = InMemorySessionManager(ttl)

    return _session_manager
