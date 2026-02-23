import os
import json
from pymongo import MongoClient
from datetime import datetime, timezone

# MongoDB Connection
MONGO_URI = "mongodb+srv://ankit:ozHqxvsmsM5MLFpq@cluster0.zmoledd.mongodb.net/"
DB_NAME = "spiritual_voice_bot"

def get_db():
    import time
    for i in range(3):
        try:
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            client.admin.command('ping')
            return client[DB_NAME]
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
