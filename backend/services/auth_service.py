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
        
        _mongo_client = MongoClient(mongo_uri)
        _db = _mongo_client[settings.DATABASE_NAME
]
        
        # Create indexes
        _db.users.create_index("email", unique=True)
        _db.tokens.create_index("token", unique=True)
        _db.tokens.create_index("expires_at", expireAfterSeconds=0)
        _db.conversations.create_index([("user_id", 1), ("updated_at", -1)])
        
        logger.info("MongoDB connection established")
    
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
        rashi: str = "",
        gotra: str = "",
        nakshatra: str = "",
        preferred_deity: str = "",
        temple_visits: List[str] = [],
        purchase_history: List[str] = []
    ) -> Optional[Dict[str, Any]]:
        """Register a new user with extended profile in the new schema structure"""
        email_lower = email.lower()

        # Check if email already exists
        if self.db.users.find_one({"email": email_lower}):
            return None

        # Hash password
        hashed, salt = _hash_password(password)

        # Calculate age and age group from DOB
        age, age_group = _calculate_age_and_group(dob)

        # Create user ID
        user_id = _generate_user_id()
        
        # Map simple lists to the complex structure requested
        # Temples
        temples_data = []
        for t in temple_visits:
            if t.strip():
                temples_data.append({
                    "temple_id": t.strip(),
                    "visits": [{
                        "date": datetime.utcnow().isoformat(),
                        "purpose": "Historical Visit",
                        "event": "",
                        "sevas": [],
                        "activity": []
                    }]
                })
        
        # Purchases
        purchases_data = []
        for p in purchase_history:
            if p.strip():
                purchases_data.append({
                    "type": "Historical",
                    "datetime": datetime.utcnow().isoformat(),
                    "product_id": "",
                    "name": p.strip(),
                    "category": "",
                    "amount": 0
                })

        # Split name into first, middle, last
        name_parts = name.strip().split()
        first_name = name_parts[0] if name_parts else ""
        if len(name_parts) == 1:
            middle_name = ""
            last_name = ""
        elif len(name_parts) == 2:
            middle_name = ""
            last_name = name_parts[1]
        else:
            middle_name = name_parts[1]
            last_name = " ".join(name_parts[2:])

        # Construct the new nested document structure
        # Keeping necessary auth fields at root (email, password, phone, created_at)
        # STRICT SCHEMA IMPLEMENTATION AS PER REQUIREMENTS (Step 211)
        user_doc = {
            "id": user_id,
            "email": email_lower, 
            "phone": phone, # Kept at root as it's contact info
            "password_hash": hashed,
            "password_salt": salt,
            "created_at": datetime.utcnow(),
            
            # Requested Structure Fields
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
            
            "temples": temples_data,
            "purchases": purchases_data
        }

        try:
            # Save user to MongoDB
            self.db.users.insert_one(user_doc)
            logger.info(f"New user registered: {email_lower} (Profile: {age_group}, {profession}, rashi={rashi}, deity={preferred_deity})")

            # Generate token
            token = self._create_token(user_id)
            
            # Return flat structure for frontend compatibility
            return {
                "user": self._flatten_user_msg(user_doc, age, age_group),
                "token": token,
            }
        except DuplicateKeyError:
            logger.error(f"Duplicate email during registration: {email_lower}")
            return None

    def login_user(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Login an existing user"""
        email_lower = email.lower()

        # Find user in MongoDB
        user = self.db.users.find_one({"email": email_lower})
        if not user:
            return None

        # Verify password
        if not _verify_password(password, user["password_hash"], user["password_salt"]):
            return None

        # Generate token
        token = self._create_token(user["id"])

        logger.info(f"User logged in: {email_lower}")

        # Recalculate age/group
        dob = user.get("date_of_birth", user.get("dob", ""))
        age, age_group = _calculate_age_and_group(dob)

        return {
            "user": self._flatten_user_msg(user, age, age_group),
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
        """Verify token and return user info"""
        # Find token in MongoDB
        token_doc = self.db.tokens.find_one({"token": token})
        if not token_doc:
            return None

        # Check expiration
        if datetime.utcnow() > token_doc["expires_at"]:
            # Token expired, remove it
            self.db.tokens.delete_one({"token": token})
            return None

        # Get user
        user = self.db.users.find_one({"id": token_doc["user_id"]})
        if not user:
            return None

        # Recalculate age
        dob = user.get("date_of_birth", user.get("dob", ""))
        age, age_group = _calculate_age_and_group(dob)
        
        return self._flatten_user_msg(user, age, age_group)

    def _flatten_user_msg(self, user_doc: Dict, age: int, age_group: str) -> Dict:
        """Helper to flatten user doc for frontend response"""
        # Handle backward compatibility (some fields might be at root in old docs)
        
        # Deities
        deities = user_doc.get("deities", [])
        pref_deity = deities[0] if deities and isinstance(deities, list) else user_doc.get("preferred_deity", "")
        
        # Spiritual Profile
        sp = user_doc.get("spiritual_profile", {})
        
        # Temples (Flatten to list of names)
        temples = user_doc.get("temples", [])
        temple_names = []
        if temples and isinstance(temples, list):
            for t in temples:
                if isinstance(t, dict):
                    temple_names.append(t.get("temple_id", ""))
                elif isinstance(t, str):
                    temple_names.append(t)
        if not temple_names:
            # Fallback to old field
            temple_names = user_doc.get("temple_visits", [])

        # Purchases (Flatten to list of names)
        purchases = user_doc.get("purchases", [])
        purchase_names = []
        if purchases and isinstance(purchases, list):
            for p in purchases:
                if isinstance(p, dict):
                    purchase_names.append(p.get("name", ""))
                elif isinstance(p, str):
                    purchase_names.append(p)
        if not purchase_names:
            purchase_names = user_doc.get("purchase_history", [])

        return {
            "id": user_doc["id"],
            "name": user_doc.get("first_name", user_doc.get("name", "")),
            "email": user_doc["email"],
            "phone": user_doc.get("phone", ""),
            "gender": user_doc.get("gender", ""),
            "dob": user_doc.get("date_of_birth", user_doc.get("dob", "")),
            "age": age,
            "age_group": age_group,
            "profession": user_doc.get("occupation", user_doc.get("profession", "")),
            "rashi": sp.get("rashi", user_doc.get("rashi", "")),
            "gotra": sp.get("gothra", sp.get("gotra", user_doc.get("gotra", ""))), # Handle spelling diff gothra/gotra
            "nakshatra": sp.get("nakshatra", user_doc.get("nakshatra", "")),
            "preferred_deity": pref_deity,
            "temple_visits": temple_names,
            "purchase_history": purchase_names,
            "created_at": user_doc["created_at"].isoformat() if isinstance(user_doc["created_at"], datetime) else user_doc["created_at"],
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
        
        # Deduplicate: only add messages that don't already exist
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
            if not any("New Session" in str(m.get("content", "")) for m in new_to_add[:1]):
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
        
        logger.info(f"Updated persistent history and story for user {user_id}")
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