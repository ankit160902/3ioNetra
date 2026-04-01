"""
Authentication Service - MongoDB-based user management
"""
import asyncio
import hashlib
import hmac
import secrets
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging
from pymongo import MongoClient, ReadPreference
from pymongo.errors import DuplicateKeyError, OperationFailure

from config import settings

# Map config string names to pymongo ReadPreference constants (Issue 25)
_READ_PREF_MAP = {
    "primary": ReadPreference.PRIMARY,
    "primaryPreferred": ReadPreference.PRIMARY_PREFERRED,
    "secondary": ReadPreference.SECONDARY,
    "secondaryPreferred": ReadPreference.SECONDARY_PREFERRED,
    "nearest": ReadPreference.NEAREST,
}

logger = logging.getLogger(__name__)

# MongoDB client and database
_mongo_client: Optional[MongoClient] = None
_db = None


def get_mongo_client():
    """Get or create MongoDB client (Resilient Version)"""
    global _mongo_client, _db
    
    if _mongo_client is not None:
        return _db

    try:
        # Construct MongoDB URI with authentication
        mongo_uri = settings.MONGODB_URI
        if not mongo_uri:
            logger.warning("MONGODB_URI not found in settings")
            return None

        if settings.DATABASE_PASSWORD:
            mongo_uri = mongo_uri.replace("<db_password>", settings.DATABASE_PASSWORD)
        
        # Resolve read preference from config (Issue 25)
        read_pref = _READ_PREF_MAP.get(
            settings.MONGO_READ_PREFERENCE, ReadPreference.PRIMARY_PREFERRED
        )

        # Connection with explicit pool sizing for production workloads
        _mongo_client = MongoClient(
            mongo_uri,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
            socketTimeoutMS=10000,
            retryWrites=True,
            maxPoolSize=settings.MONGO_MAX_POOL_SIZE,
            minPoolSize=settings.MONGO_MIN_POOL_SIZE,
            maxIdleTimeMS=settings.MONGO_MAX_IDLE_TIME_MS,
            read_preference=read_pref,
        )
        
        # Access database
        _db = _mongo_client[settings.DATABASE_NAME]
        
        # Test connection with a simple command to catch DNS issues early
        _mongo_client.admin.command('ping')

        # Run database migrations before index creation (Issue 28)
        if settings.ENABLE_AUTO_MIGRATIONS:
            try:
                from scripts.migrations import run_migrations
                run_migrations(_db)
            except Exception as e:
                logger.warning(f"⚠️ Auto-migrations failed (non-fatal): {e}")

        # Create indexes with error handling
        try:
            _db.users.create_index("email", unique=True)
            _db.users.create_index("id", unique=True)
            _db.tokens.create_index("token", unique=True)
            _db.tokens.create_index("expires_at", expireAfterSeconds=0)
            _db.tokens.create_index("user_id")
            _db.conversations.create_index([("user_id", 1), ("updated_at", -1)])
            _db.conversations.create_index([("user_id", 1), ("session_id", 1)])
            try:
                _db.feedback.drop_index("session_id_1_message_index_1_user_id_1")
            except OperationFailure:
                pass
            _db.feedback.create_index([("session_id", 1), ("message_index", 1), ("response_hash", 1), ("user_id", 1)], unique=True)
            # Product indexes for search performance
            _db.products.create_index("is_active")
            _db.products.create_index(
                [("name", "text"), ("category", "text"), ("description", "text")],
                name="products_text_search"
            )
            logger.info("✅ MongoDB connection established and indexes verified")
        except Exception as e:
            logger.warning(f"⚠️ Index creation partially failed: {e}")
            
        return _db

    except Exception as e:
        logger.error(f"❌ Critical MongoDB connection failure: {e}")
        _mongo_client = None
        _db = None
        return None


def close_mongo_client():
    """Close MongoDB client connection on shutdown"""
    global _mongo_client, _db
    if _mongo_client:
        logger.info("Closing MongoDB connection...")
        _mongo_client.close()
        _mongo_client = None
        _db = None


def _hash_password(password: str, salt: str = None) -> tuple[str, str]:
    """Hash password with salt"""
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    return hashed, salt


def _verify_password(password: str, hashed: str, salt: str) -> bool:
    """Verify password against hash (constant-time comparison to prevent timing attacks)"""
    check_hash, _ = _hash_password(password, salt)
    return hmac.compare_digest(check_hash, hashed)


def _generate_token() -> str:
    """Generate a secure token"""
    return secrets.token_urlsafe(32)


def _generate_user_id() -> str:
    """Generate a unique user ID"""
    return secrets.token_hex(12)


def _calculate_age_and_group(dob: str) -> tuple[int, str]:
    """Calculate age and age group from date of birth (YYYY-MM-DD format)"""
    try:
        birth_date = datetime.strptime(dob, "%Y-%m-%d")
        today = datetime.today()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

        # Determine age group
        if age < 20:
            age_group = "teen"
        elif age < 35:
            age_group = "young_adult"
        elif age < 55:
            age_group = "middle_aged"
        else:
            age_group = "senior"

        return age, age_group
    except (ValueError, TypeError):
        return 0, "unknown"


class AuthService:
    """MongoDB-based authentication service"""

    _TOKEN_CACHE_TTL = 300  # 5 minutes

    def __init__(self):
        self.db = get_mongo_client()
        self._token_cache: dict[str, tuple[float, dict]] = {}  # token -> (expiry_mono, user_data)

    def register_user(
        self,
        name: str,
        email: str,
        password: str,
        phone: str = "",
        gender: str = "",
        dob: str = "",
        profession: str = "",
        preferred_deity: str = "",
        rashi: str = "",
        gotra: str = "",
        nakshatra: str = "",
        temple_visits: list = None,
        purchase_history: list = None
    ) -> Optional[Dict[str, Any]]:
        """Register a new user with nested schema support"""
        if self.db is None: 
            logger.error("AuthService: Database not connected")
            return None
        
        email_lower = email.lower()

        hashed, salt = _hash_password(password)
        name_parts = name.strip().split()
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[-1] if len(name_parts) > 1 else ""
        middle_name = " ".join(name_parts[1:-1]) if len(name_parts) > 2 else ""

        user_id = _generate_user_id()
        user_doc = {
            "id": user_id,
            "email": email_lower,
            "phone": phone,
            "password_hash": hashed,
            "password_salt": salt,
            "created_at": datetime.utcnow(),
            "first_name": first_name,
            "middle_name": middle_name,
            "last_name": last_name,
            "date_of_birth": dob,
            "occupation": profession,
            "gender": gender,
            "deities": [preferred_deity] if preferred_deity else [],
            "spiritual_profile": {
                "rashi": rashi,
                "gotra": gotra,
                "nakshatra": nakshatra,
                "kundli": None
            },
            "temples": [
                {
                    "temple_id": t,
                    "visits": [{
                        "date": datetime.utcnow().isoformat(),
                        "purpose": "Historical Visit",
                        "event": "",
                        "sevas": [],
                        "activity": []
                    }]
                }
                for t in (temple_visits or [])
            ],
            "purchases": [
                {
                    "type": "Historical",
                    "datetime": datetime.utcnow().isoformat(),
                    "product_id": "",
                    "name": p,
                    "category": "Spiritual Item",
                    "amount": 0
                }
                for p in (purchase_history or [])
            ],
            "is_active": True,
            "deleted_at": None
        }

        try:
            self.db.users.insert_one(user_doc)
            token = self._create_token(user_id)
            return {
                "user": self._flatten_user_msg(user_doc),
                "token": token,
            }
        except DuplicateKeyError:
            logger.info(f"Registration failed: duplicate email '{email_lower}'")
            return None

    def login_user(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Login an existing user"""
        if self.db is None:
            return None
        email_lower = email.lower()
        try:
            user = self.db.users.find_one({"email": email_lower})
        except Exception as e:
            logger.error(f"login_user DB error: {e}")
            return None
        if not user or not _verify_password(password, user["password_hash"], user["password_salt"]):
            return None

        token = self._create_token(user["id"])
        return {
            "user": self._flatten_user_msg(user),
            "token": token,
        }

    def _create_token(self, user_id: str) -> str:
        """Create and store a new token for user"""
        if self.db is None:
            return ""
        token = _generate_token()
        token_doc = {
            "token": token,
            "user_id": user_id,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(days=30),
        }
        self.db.tokens.insert_one(token_doc)
        return token

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify token and return flattened user info"""
        import time as _time

        # Check in-memory cache first
        cached = self._token_cache.get(token)
        if cached is not None:
            cache_expiry, user_data = cached
            if _time.monotonic() < cache_expiry:
                return user_data
            del self._token_cache[token]

        if self.db is None:
            return None
        try:
            token_doc = self.db.tokens.find_one({"token": token})
        except Exception as e:
            logger.error(f"verify_token token lookup error: {e}")
            return None
        # Belt-and-suspenders expiry check: the TTL index on expires_at handles
        # cleanup asynchronously (MongoDB runs the TTL monitor every ~60s), so a
        # token can linger briefly after expiration. This app-side check covers
        # the gap, ensuring an expired token is never accepted even if the TTL
        # monitor hasn't swept it yet.
        expires_at = token_doc.get("expires_at") if token_doc else None
        if not token_doc or not expires_at or datetime.utcnow() > expires_at:
            return None

        user_id = token_doc.get("user_id")
        if not user_id:
            return None
        try:
            user = self.db.users.find_one({"id": user_id}, {"password_hash": 0, "password_salt": 0})
        except Exception as e:
            logger.error(f"verify_token user lookup error: {e}")
            return None
        result = self._flatten_user_msg(user) if user else None

        # Cache successful verification
        if result is not None:
            self._token_cache[token] = (_time.monotonic() + self._TOKEN_CACHE_TTL, result)

        return result

    def _flatten_user_msg(self, user: Dict[str, Any]) -> Dict[str, Any]:
        """Flatten nested MongoDB document for application use"""
        dob = user.get("date_of_birth") or user.get("dob") or ""
        age, age_group = _calculate_age_and_group(dob)
        
        name = user.get("name")
        if not name:
            parts = [user.get("first_name", ""), user.get("middle_name", ""), user.get("last_name", "")]
            name = " ".join([p for p in parts if p]).strip()
            
        spirit = user.get("spiritual_profile", {})
        
        return {
            "id": user["id"],
            "name": name,
            "first_name": user.get("first_name", ""),
            "last_name": user.get("last_name", ""),
            "email": user["email"],
            "phone": user.get("phone", ""),
            "gender": user.get("gender", ""),
            "dob": dob,
            "age": age,
            "age_group": age_group,
            "profession": user.get("occupation") or user.get("profession") or "",
            "rashi": spirit.get("rashi") or user.get("rashi") or "",
            "gotra": spirit.get("gotra") or spirit.get("gothra") or user.get("gotra") or user.get("gothra") or "",
            "nakshatra": spirit.get("nakshatra") or user.get("nakshatra") or "",
            "preferred_deity": user.get("deities", [""])[0] if user.get("deities") else user.get("preferred_deity", ""),
            "temple_visits": [t.get("temple_id") for t in user.get("temples", [])] if isinstance(user.get("temples"), list) else [],
            "purchase_history": [p.get("name") for p in user.get("purchases", [])] if isinstance(user.get("purchases"), list) else [],
            "created_at": user["created_at"].isoformat() if isinstance(user["created_at"], datetime) else str(user["created_at"]),
        }

    def logout_user(self, token: str) -> bool:
        """Logout user by invalidating token"""
        self._token_cache.pop(token, None)
        if self.db is None:
            return False
        try:
            result = self.db.tokens.delete_one({"token": token})
        except Exception as e:
            logger.error(f"logout_user DB error: {e}")
            return False
        return result.deleted_count > 0

    def invalidate_user_tokens(self, user_id: str) -> int:
        """Invalidate all tokens for a user (e.g. after password change).
        Returns the number of tokens deleted."""
        # Clear cached tokens for this user
        self._token_cache = {
            k: v for k, v in self._token_cache.items()
            if v[1].get("id") != user_id
        }
        if self.db is None:
            return 0
        try:
            result = self.db.tokens.delete_many({"user_id": user_id})
        except Exception as e:
            logger.error(f"invalidate_user_tokens DB error: {e}")
            return 0
        logger.info(f"Invalidated {result.deleted_count} tokens for user {user_id}")
        return result.deleted_count

    def update_user_profile(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """Update user's permanent profile fields (e.g. profession, rashi, nakshatra)"""
        if self.db is None:
            return False

        # Prepare MongoDB update object
        set_data = {}
        spirit_updates = {}
        
        # Map flat updates to nested schema
        if "profession" in updates:
            set_data["occupation"] = updates["profession"]
        if "gender" in updates:
            set_data["gender"] = updates["gender"]
        if "dob" in updates:
            set_data["date_of_birth"] = updates["dob"]
        
        # Deities is a list
        if "preferred_deity" in updates: 
            set_data["deities"] = [updates["preferred_deity"]]
            
        # Spiritual profile nesting
        if "rashi" in updates:
            spirit_updates["rashi"] = updates["rashi"]
        if "gotra" in updates:
            spirit_updates["gotra"] = updates["gotra"]
        if "nakshatra" in updates:
            spirit_updates["nakshatra"] = updates["nakshatra"]
        
        if spirit_updates:
            # $set nested fields
            for k, v in spirit_updates.items():
                set_data[f"spiritual_profile.{k}"] = v
                
        if not set_data:
            return True

        set_data["updated_at"] = datetime.utcnow()
        try:
            result = self.db.users.update_one({"id": user_id}, {"$set": set_data})
        except Exception as e:
            logger.error(f"update_user_profile DB error: {e}")
            return False
        return result.modified_count > 0

class ConversationStorage:
    """Store and retrieve user conversations in MongoDB.
    Uses async Redis to avoid blocking the FastAPI event loop.
    """

    def __init__(self):
        self.db = get_mongo_client()
        import redis.asyncio as aioredis
        self._redis = aioredis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
            max_connections=100,
            socket_connect_timeout=3,
            socket_timeout=5,
            retry_on_timeout=True,
        )

    async def save_conversation(
        self,
        user_id: str,
        conversation_id: Optional[str],
        title: str,
        messages: list,
        memory: Optional[Dict] = None
    ) -> str:
        """Save a specific session to persistent history"""
        if self.db is None:
            return ""

        # Use session_id/conversation_id to identify the specific session
        if not conversation_id:
            return ""  # Must have a session ID

        query = {"user_id": user_id, "session_id": conversation_id}

        update_data = {
            "messages": messages,
            "message_count": len(messages),
            "updated_at": datetime.utcnow(),
            "last_title": title
        }

        if memory:
            update_data["memory"] = memory

        await asyncio.to_thread(
            self.db.conversations.update_one,
            query,
            {"$set": update_data, "$setOnInsert": {"created_at": datetime.utcnow()}},
            upsert=True,
        )

        # Prune oldest conversations if user exceeds limit (Issue 22)
        try:
            max_convos = settings.MAX_CONVERSATIONS_PER_USER

            def _prune():
                count = self.db.conversations.count_documents({"user_id": user_id})
                if count > max_convos:
                    excess = count - max_convos
                    oldest = (
                        self.db.conversations.find({"user_id": user_id}, {"_id": 1})
                        .sort("updated_at", 1)
                        .limit(excess)
                    )
                    ids_to_delete = [doc["_id"] for doc in oldest]
                    if ids_to_delete:
                        self.db.conversations.delete_many({"_id": {"$in": ids_to_delete}})
                        logger.info(f"Pruned {len(ids_to_delete)} old conversations for user {user_id}")

            await asyncio.to_thread(_prune)
        except Exception as e:
            logger.warning(f"Conversation pruning failed (non-fatal): {e}")

        # Invalidate cache (async)
        try:
            await self._redis.delete(f"history_list:{user_id}")
        except Exception as e:
            logger.error(f"Redis cache invalidation error: {e}")

        logger.info(f"Saved persistent history for session {conversation_id}")
        return str(conversation_id)

    async def get_conversations_list(self, user_id: str, limit: int = 50) -> list:
        """Get list of individual sessions with async Redis caching"""
        import json

        # Try cache first (async)
        cache_key = f"history_list:{user_id}"
        try:
            cached_data = await self._redis.get(cache_key)
            if cached_data:
                logger.info(f"Serving history list from Redis cache for user {user_id}")
                return json.loads(cached_data)
        except Exception as e:
            logger.error(f"Redis history fetch error: {e}")

        if self.db is None:
            return []

        # Aggregation pipeline computes message_count server-side from the
        # actual messages array length, eliminating drift (Issue 23).
        agg_pipeline = [
            {"$match": {"user_id": user_id}},
            {"$sort": {"updated_at": -1}},
            {"$limit": limit},
            {"$project": {
                "session_id": 1,
                "last_title": 1,
                "created_at": 1,
                "updated_at": 1,
                "message_count": {"$size": {"$ifNull": ["$messages", []]}},
            }},
        ]

        def _run_aggregate():
            result = []
            for conv in self.db.conversations.aggregate(agg_pipeline):
                created_at = conv.get("created_at")
                updated_at = conv.get("updated_at") or created_at or datetime.utcnow()
                if not created_at:
                    created_at = updated_at
                result.append({
                    "id": str(conv["_id"]),
                    "session_id": conv.get("session_id"),
                    "title": conv.get("last_title", "New Conversation"),
                    "created_at": created_at.isoformat() if isinstance(created_at, datetime) else str(created_at),
                    "updated_at": updated_at.isoformat() if isinstance(updated_at, datetime) else str(updated_at),
                    "message_count": conv.get("message_count", 0),
                })
            return result

        history_list = await asyncio.to_thread(_run_aggregate)

        # Cache for 10 minutes (async)
        try:
            await self._redis.setex(cache_key, 600, json.dumps(history_list))
        except Exception as e:
            logger.warning(f"Failed to cache history list: {e}")

        return history_list

    async def get_conversation(self, user_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific session's history"""
        if self.db is None:
            return None

        from bson import ObjectId

        def _fetch():
            if conversation_id:
                try:
                    if len(conversation_id) == 24:  # MongoDB ObjectId
                        q = {"_id": ObjectId(conversation_id), "user_id": user_id}
                    else:  # session_id (UUID string)
                        q = {"session_id": conversation_id, "user_id": user_id}
                except Exception as e:
                    logger.debug(f"ObjectId parse failed for '{conversation_id}', using UUID query: {e}")
                    q = {"session_id": conversation_id, "user_id": user_id}
                return self.db.conversations.find_one(q)
            else:
                cursor = self.db.conversations.find({"user_id": user_id}).sort("updated_at", -1).limit(1)
                return next(cursor, None)

        conversation = await asyncio.to_thread(_fetch)

        if conversation:
            created_at = conversation.get("created_at")
            updated_at = conversation.get("updated_at") or created_at or datetime.utcnow()
            if not created_at:
                created_at = updated_at

            conversation["created_at"] = created_at.isoformat() if isinstance(created_at, datetime) else str(created_at)
            conversation["updated_at"] = updated_at.isoformat() if isinstance(updated_at, datetime) else str(updated_at)
            conversation["id"] = str(conversation.pop("_id"))

        return conversation

    async def get_recent_conversation_summaries(self, user_id: str, limit: int = 5) -> list:
        """Fetch memory snapshots from last N conversations (lightweight projection)."""
        if self.db is None:
            return []
        try:
            def _fetch():
                cursor = self.db.conversations.find(
                    {"user_id": user_id},
                    {"memory": 1, "updated_at": 1, "last_title": 1, "conversation_summary": 1}
                ).sort("updated_at", -1).limit(limit)
                return list(cursor)
            return await asyncio.to_thread(_fetch)
        except Exception as e:
            logger.error(f"Failed to fetch recent conversations: {e}")
            return []

    async def update_conversation_field(self, user_id: str, conversation_id: str, field: str, value):
        """Update a single field on a saved conversation."""
        if self.db is None:
            return
        await asyncio.to_thread(
            self.db.conversations.update_one,
            {"user_id": user_id, "session_id": conversation_id},
            {"$set": {field: value}}
        )

    async def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        """Delete a specific conversation"""
        if self.db is None:
            return False
        result = await asyncio.to_thread(
            self.db.conversations.delete_one,
            {"user_id": user_id, "session_id": conversation_id},
        )

        # Invalidate cache (async)
        try:
            await self._redis.delete(f"history_list:{user_id}")
        except Exception as e:
            logger.error(f"Redis cache invalidation error: {e}")

        if result.deleted_count > 0:
            logger.info(f"Deleted conversation {conversation_id} for user {user_id}")
            return True

        return False


# Singleton instances
_auth_service: Optional[AuthService] = None
_conversation_storage: Optional[ConversationStorage] = None


def get_auth_service() -> AuthService:
    """Get or create the singleton AuthService instance"""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


def get_conversation_storage() -> ConversationStorage:
    """Get or create the singleton ConversationStorage instance"""
    global _conversation_storage
    if _conversation_storage is None:
        _conversation_storage = ConversationStorage()
    return _conversation_storage