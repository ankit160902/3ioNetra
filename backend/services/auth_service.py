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
    """Get or create MongoDB client"""
    global _mongo_client, _db
    if _mongo_client is None:
        # Construct MongoDB URI with authentication
        mongo_uri = settings.MONGODB_URI

        if settings.DATABASE_PASSWORD:
            # Replace password placeholder if exists
            mongo_uri = mongo_uri.replace("<db_password>", settings.DATABASE_PASSWORD
)
        
        _mongo_client = MongoClient(
            mongo_uri, 
            serverSelectionTimeoutMS=5000, 
            connectTimeoutMS=5000
        )
        _db = _mongo_client[settings.DATABASE_NAME]
        
        # Create indexes with error handling to avoid crashes on configuration conflicts
        try:
            _db.users.create_index("email", unique=True)
            _db.tokens.create_index("token", unique=True)
            _db.tokens.create_index("expires_at", expireAfterSeconds=0)
            _db.conversations.create_index([("user_id", 1), ("updated_at", -1)])
            logger.info("MongoDB connection established and indexes verified")
        except Exception as e:
            logger.warning(f"⚠️ Index creation partially failed: {e}. This usually happens if an index already exists with different options.")
    
    return _db


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
        result = self.db.tokens.delete_one({"token": token})
        return result.deleted_count > 0

class ConversationStorage:
    """Store and retrieve user conversations in MongoDB"""

    def __init__(self):
        self.db = get_mongo_client()

    def save_conversation(
        self,
        user_id: str,
        conversation_id: Optional[str],
        title: str,
        messages: list,
        memory: Optional[Dict] = None
    ) -> str:
        """Add unique messages and persistent memory to user's global history"""
        
        # Find user's conversation document
        user_conversation = self.db.conversations.find_one({"user_id": user_id})
        
        existing_messages = user_conversation.get("messages", []) if user_conversation else []
        
        # Deduplication signature
        existing_sigs = set()
        for m in existing_messages:
            sig = (m.get("role"), m.get("content"), m.get("timestamp"))
            existing_sigs.add(sig)
            
        new_to_add = []
        for m in messages:
            sig = (m.get("role"), m.get("content"), m.get("timestamp"))
            if sig not in existing_sigs:
                new_to_add.append(m)
        
        if not new_to_add and not memory:
            return str(user_conversation["_id"]) if user_conversation else ""

        # Session separator logic
        if existing_messages and new_to_add:
            # Add separator only if the first new message isn't already a separator
            if not any("Session" in str(m.get("content", "")) for m in new_to_add[:1]):
                 existing_messages.append({
                    "role": "system",
                    "content": f"--- New Session: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} ---",
                    "timestamp": datetime.utcnow().isoformat()
                })

        # Add all new messages
        existing_messages.extend(new_to_add)
        
        update_data = {
            "messages": existing_messages,
            "message_count": len(existing_messages),
            "updated_at": datetime.utcnow(),
            "last_title": title
        }
        
        if memory:
            update_data["memory"] = memory

        if user_conversation:
            # Update document
            self.db.conversations.update_one(
                {"user_id": user_id},
                {"$set": update_data}
            )
            conv_id = user_conversation["_id"]
        else:
            # Create new conversation document for user
            conversation_doc = {
                "user_id": user_id,
                "created_at": datetime.utcnow(),
                **update_data
            }
            
            result = self.db.conversations.insert_one(conversation_doc)
            conv_id = result.inserted_id
        
        logger.info(f"Updated persistent history and memory for user {user_id}")
        return str(conv_id)

    def get_conversations_list(self, user_id: str, limit: int = 20) -> list:
        """Get user's conversation (returns single document)"""
        conversation = self.db.conversations.find_one({"user_id": user_id})
        
        if not conversation:
            return []
        
        return [
            {
                "id": str(conversation["_id"]),
                "title": conversation.get("last_title", "All Conversations"),
                "created_at": conversation["created_at"].isoformat(),
                "message_count": conversation["message_count"],
            }
        ]

    def get_conversation(self, user_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get user's complete conversation history"""
        conversation = self.db.conversations.find_one({"user_id": user_id})

        if conversation:
            conversation["created_at"] = conversation["created_at"].isoformat()
            conversation["updated_at"] = conversation["updated_at"].isoformat()
            conversation["id"] = str(conversation["_id"])

        return conversation

    def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        """Delete user's entire conversation history"""
        result = self.db.conversations.delete_one({"user_id": user_id})

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