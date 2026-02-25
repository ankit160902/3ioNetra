"""
Authentication Service - MongoDB-based user management
"""
import hashlib
import secrets
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

from config import settings

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
        
        # Increase connection robustness for slow DNS environments
        _mongo_client = MongoClient(
            mongo_uri, 
            serverSelectionTimeoutMS=10000, # Reduced but more frequent retries
            connectTimeoutMS=10000,
            socketTimeoutMS=10000,
            retryWrites=True
        )
        
        # Access database
        _db = _mongo_client[settings.DATABASE_NAME]
        
        # Test connection with a simple command to catch DNS issues early
        _mongo_client.admin.command('ping')
        
        # Create indexes with error handling
        try:
            _db.users.create_index("email", unique=True)
            _db.tokens.create_index("token", unique=True)
            _db.tokens.create_index("expires_at", expireAfterSeconds=0)
            _db.conversations.create_index([("user_id", 1), ("updated_at", -1)])
            logger.info("✅ MongoDB connection established and indexes verified")
        except Exception as e:
            logger.warning(f"⚠️ Index creation partially failed: {e}")
            
        return _db

    except Exception as e:
        logger.error(f"❌ Critical MongoDB connection failure: {e}")
        _mongo_client = None
        _db = None
        return None


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
    """Verify password against hash"""
    check_hash, _ = _hash_password(password, salt)
    return check_hash == hashed


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

    def __init__(self):
        self.db = get_mongo_client()

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

        if self.db.users.find_one({"email": email_lower}):
            return None

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
                "gothra": gotra,
                "nakshatra": nakshatra,
                "kundli": None
            },
            "temples": [],
            "purchases": []
        }

        try:
            self.db.users.insert_one(user_doc)
            token = self._create_token(user_id)
            return {
                "user": self._flatten_user_msg(user_doc),
                "token": token,
            }
        except DuplicateKeyError:
            return None

    def login_user(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Login an existing user"""
        if self.db is None: return None
        email_lower = email.lower()
        user = self.db.users.find_one({"email": email_lower})
        if not user or not _verify_password(password, user["password_hash"], user["password_salt"]):
            return None

        token = self._create_token(user["id"])
        return {
            "user": self._flatten_user_msg(user),
            "token": token,
        }

    def _create_token(self, user_id: str) -> str:
        """Create and store a new token for user"""
        if self.db is None: return ""
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
        if self.db is None: return None
        token_doc = self.db.tokens.find_one({"token": token})
        if not token_doc or datetime.utcnow() > token_doc["expires_at"]:
            return None

        user = self.db.users.find_one({"id": token_doc["user_id"]})
        return self._flatten_user_msg(user) if user else None

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
            "gotra": spirit.get("gothra") or user.get("gothra") or "",
            "nakshatra": spirit.get("nakshatra") or user.get("nakshatra") or "",
            "preferred_deity": user.get("deities", [user.get("preferred_deity", "")])[0] if user.get("deities") else "",
            "temple_visits": [t.get("temple_id") for t in user.get("temples", [])] if isinstance(user.get("temples"), list) else [],
            "purchase_history": [p.get("name") for p in user.get("purchases", [])] if isinstance(user.get("purchases"), list) else [],
            "created_at": user["created_at"].isoformat() if isinstance(user["created_at"], datetime) else str(user["created_at"]),
        }

    def logout_user(self, token: str) -> bool:
        """Logout user by invalidating token"""
        if self.db is None: return False
        result = self.db.tokens.delete_one({"token": token})
        return result.deleted_count > 0

class ConversationStorage:
    """Store and retrieve user conversations in MongoDB"""

    def __init__(self):
        self.db = get_mongo_client()
        import redis
        self._redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True
        )

    def save_conversation(
        self,
        user_id: str,
        conversation_id: Optional[str],
        title: str,
        messages: list,
        memory: Optional[Dict] = None
    ) -> str:
        """Save a specific session to persistent history"""
        if self.db is None: return ""
        
        # Use session_id/conversation_id to identify the specific session
        if not conversation_id: return "" # Must have a session ID
        
        query = {"user_id": user_id, "session_id": conversation_id}
        
        update_data = {
            "messages": messages,
            "message_count": len(messages),
            "updated_at": datetime.utcnow(),
            "last_title": title
        }
        
        if memory:
            update_data["memory"] = memory

        self.db.conversations.update_one(
            query,
            {"$set": update_data, "$setOnInsert": {"created_at": datetime.utcnow()}},
            upsert=True
        )
        
        # Invalidate cache
        try:
            self._redis.delete(f"history_list:{user_id}")
        except Exception as e:
            logger.error(f"Redis cache invalidation error: {e}")
        
        logger.info(f"Saved persistent history for session {conversation_id}")
        return str(conversation_id)

    def get_conversations_list(self, user_id: str, limit: int = 50) -> list:
        """Get list of individual sessions with Redis caching"""
        import json
        
        # Try cache first
        cache_key = f"history_list:{user_id}"
        try:
            cached_data = self._redis.get(cache_key)
            if cached_data:
                logger.info(f"🚀 Serving history list from Redis for user {user_id}")
                return json.loads(cached_data)
        except Exception as e:
            logger.error(f"Redis history fetch error: {e}")

        if self.db is None: return []
        
        # Find all session documents for user, sorted by most recent
        cursor = self.db.conversations.find({"user_id": user_id}).sort("updated_at", -1).limit(limit)
        
        history_list = []
        for conv in cursor:
            history_list.append({
                "id": str(conv["_id"]),
                "session_id": conv.get("session_id"),
                "title": conv.get("last_title", "New Conversation"),
                "created_at": conv["created_at"].isoformat() if isinstance(conv["created_at"], datetime) else str(conv["created_at"]),
                "updated_at": conv["updated_at"].isoformat() if isinstance(conv["updated_at"], datetime) else str(conv["updated_at"]),
                "message_count": conv.get("message_count", 0),
            })
        
        # Cache for 10 minutes
        try:
            self._redis.setex(cache_key, 600, json.dumps(history_list))
        except Exception as e:
            logger.warning(f"Failed to cache history list: {e}")

        return history_list

    def get_conversation(self, user_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific session's history"""
        if self.db is None: return None
        
        from bson import ObjectId
        query = {"user_id": user_id}
        
        # If conversation_id is provided, try finding by mongo _id or session_id
        if conversation_id:
            try:
                if len(conversation_id) == 24: # MongoDB ObjectId
                    query = {"_id": ObjectId(conversation_id), "user_id": user_id}
                else: # session_id (UUID string)
                    query = {"session_id": conversation_id, "user_id": user_id}
            except:
                query = {"session_id": conversation_id, "user_id": user_id}
        else:
            # Default to latest session if none specified
            cursor = self.db.conversations.find({"user_id": user_id}).sort("updated_at", -1).limit(1)
            conversation = next(cursor, None)
            if not conversation: return None
            query = {"_id": conversation["_id"]}

        conversation = self.db.conversations.find_one(query)

        if conversation:
            conversation["created_at"] = conversation["created_at"].isoformat() if isinstance(conversation["created_at"], datetime) else str(conversation["created_at"])
            conversation["updated_at"] = conversation["updated_at"].isoformat() if isinstance(conversation["updated_at"], datetime) else str(conversation["updated_at"])
            conversation["id"] = str(conversation.pop("_id"))

        return conversation

    def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        """Delete user's entire conversation history"""
        if self.db is None: return False
        result = self.db.conversations.delete_one({"user_id": user_id})

        # Invalidate cache
        try:
            self._redis.delete(f"history_list:{user_id}")
        except Exception as e:
            logger.error(f"Redis cache invalidation error: {e}")

        if result.deleted_count > 0:
            logger.info(f"Deleted all conversations for user {user_id}")
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