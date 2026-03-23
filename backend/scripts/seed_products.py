import os
import sys
import json
import time
from pymongo import MongoClient
from datetime import datetime, timezone

# Add parent directory to path so we can import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings

def _build_mongo_uri():
    uri = settings.MONGODB_URI
    if not uri:
        raise RuntimeError("MONGODB_URI not set. Check your .env file.")
    if settings.DATABASE_PASSWORD:
        uri = uri.replace("<db_password>", settings.DATABASE_PASSWORD)
    return uri

def get_db():
    mongo_uri = _build_mongo_uri()
    for i in range(3):
        try:
            client = MongoClient(
                mongo_uri,
                serverSelectionTimeoutMS=settings.MONGO_SERVER_SELECTION_TIMEOUT_MS,
                connectTimeoutMS=settings.MONGO_CONNECT_TIMEOUT_MS,
                socketTimeoutMS=settings.MONGO_SOCKET_TIMEOUT_MS,
            )
            client.admin.command('ping')
            return client[settings.DATABASE_NAME]
        except Exception as e:
            print(f"Connection attempt {i+1} failed: {e}")
            if i < 2:
                time.sleep(2)
            else:
                raise

def seed_products():
    db = get_db()
    products_collection = db["products"]
    
    # Load from JSON
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, "products.json")
    
    with open(json_path, "r", encoding="utf-8") as f:
        products = json.load(f)
    
    print("Cleanup: Removing existing products...")
    products_collection.delete_many({})
    
    print(f"Seeding {len(products)} products...")
    
    # Add timestamps before seeding
    for p in products:
        p["created_at"] = datetime.now(timezone.utc)
        p["updated_at"] = datetime.now(timezone.utc)
        
    if products:
        # We'll try to insert in batches to handle any remaining encoding errors gracefully
        batch_size = 50
        for i in range(0, len(products), batch_size):
            batch = products[i:i+batch_size]
            try:
                products_collection.insert_many(batch)
                print(f"Inserted batch {i//batch_size + 1} ({len(batch)} products)")
            except Exception as e:
                print(f"Batch {i//batch_size + 1} failed, trying individually: {e}")
                for p in batch:
                    try:
                        products_collection.insert_one(p)
                    except Exception as ie:
                        print(f"Failed to insert '{p['name']}': {ie}")

    print("Seeding process finished.")

if __name__ == "__main__":
    seed_products()
