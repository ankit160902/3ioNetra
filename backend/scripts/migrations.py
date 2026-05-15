"""
Database Migrations Framework for 3ioNetra

Lightweight migration system that tracks applied migrations in a `_migrations`
collection and runs pending ones in version order on startup.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Migration functions — each receives the database handle
# ---------------------------------------------------------------------------

def migration_001_index_users_id(db):
    """Issue 15: Create unique index on users.id for O(1) lookups."""
    db.users.create_index("id", unique=True)
    logger.info("Migration 001: Created unique index on users.id")


def migration_002_remove_empty_arrays(db):
    """Issue 16: Remove empty temples/purchases arrays from user documents."""
    result_t = db.users.update_many({"temples": []}, {"$unset": {"temples": ""}})
    result_p = db.users.update_many({"purchases": []}, {"$unset": {"purchases": ""}})
    logger.info(
        "Migration 002: Removed empty arrays — "
        f"temples: {result_t.modified_count}, purchases: {result_p.modified_count}"
    )


def migration_003_collection_schema_validation(db):
    """Issue 19: Apply $jsonSchema validators to all collections (warn mode)."""
    schemas = {
        "users": {
            "bsonType": "object",
            "required": ["id", "email", "password_hash", "password_salt", "created_at"],
            "properties": {
                "id": {"bsonType": "string"},
                "email": {"bsonType": "string"},
                "password_hash": {"bsonType": "string"},
                "password_salt": {"bsonType": "string"},
                "created_at": {"bsonType": "date"},
            },
        },
        "tokens": {
            "bsonType": "object",
            "required": ["token", "user_id", "created_at", "expires_at"],
            "properties": {
                "token": {"bsonType": "string"},
                "user_id": {"bsonType": "string"},
                "created_at": {"bsonType": "date"},
                "expires_at": {"bsonType": "date"},
            },
        },
        "conversations": {
            "bsonType": "object",
            "required": ["user_id", "session_id", "messages"],
            "properties": {
                "user_id": {"bsonType": "string"},
                "session_id": {"bsonType": "string"},
                "messages": {"bsonType": "array"},
            },
        },
        "sessions": {
            "bsonType": "object",
            "required": ["session_id"],
            "properties": {
                "session_id": {"bsonType": "string"},
            },
        },
        "feedback": {
            "bsonType": "object",
            "required": ["session_id", "message_index", "feedback"],
            "properties": {
                "session_id": {"bsonType": "string"},
                "message_index": {"bsonType": "int"},
                "feedback": {"enum": ["like", "dislike"]},
            },
        },
        "products": {
            "bsonType": "object",
            "required": ["name", "is_active"],
            "properties": {
                "name": {"bsonType": "string"},
                "is_active": {"bsonType": "bool"},
            },
        },
        "user_memories": {
            "bsonType": "object",
            "required": ["user_id", "text", "embedding"],
            "properties": {
                "user_id": {"bsonType": "string"},
                "text": {"bsonType": "string"},
                "embedding": {"bsonType": "array"},
            },
        },
    }

    for collection_name, schema in schemas.items():
        try:
            db.command("collMod", collection_name, validator={"$jsonSchema": schema}, validationAction="warn")
        except Exception as e:
            # Collection may not exist yet — create it with the validator
            if "not found" in str(e).lower() or "ns not found" in str(e).lower():
                try:
                    db.create_collection(collection_name, validator={"$jsonSchema": schema})
                    db.command("collMod", collection_name, validationAction="warn")
                except Exception as create_err:
                    logger.warning(f"Migration 003: Could not create collection {collection_name}: {create_err}")
            else:
                logger.warning(f"Migration 003: Could not set validator on {collection_name}: {e}")

    logger.info("Migration 003: Applied $jsonSchema validators (warn mode) to all collections")


# ---------------------------------------------------------------------------
# Migration registry — (version, name, up_function)
# Add new migrations at the end. Never reorder or remove existing entries.
# ---------------------------------------------------------------------------

MIGRATIONS = [
    (1, "index_users_id", migration_001_index_users_id),
    (2, "remove_empty_arrays", migration_002_remove_empty_arrays),
    (3, "collection_schema_validation", migration_003_collection_schema_validation),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_migrations(db):
    """Run all pending migrations in version order.

    Each migration is recorded in the ``_migrations`` collection with its
    version, name, applied_at timestamp, and status (``applied`` or ``failed``).
    On failure the error is logged and execution stops — no migration is skipped.
    """
    migrations_coll = db["_migrations"]

    applied = {doc["version"] for doc in migrations_coll.find({}, {"version": 1})}

    pending = [(v, name, fn) for v, name, fn in MIGRATIONS if v not in applied]
    if not pending:
        logger.info("Migrations: all up-to-date, nothing to run")
        return

    pending.sort(key=lambda m: m[0])

    for version, name, fn in pending:
        logger.info(f"Migrations: running {version} — {name}")
        try:
            fn(db)
            migrations_coll.insert_one({
                "version": version,
                "name": name,
                "applied_at": datetime.utcnow(),
                "status": "applied",
            })
            logger.info(f"Migrations: {version} — {name} applied successfully")
        except Exception as exc:
            migrations_coll.insert_one({
                "version": version,
                "name": name,
                "applied_at": datetime.utcnow(),
                "status": "failed",
            })
            logger.error(f"Migrations: {version} — {name} FAILED: {exc}")
            break  # Stop on failure — do not skip
