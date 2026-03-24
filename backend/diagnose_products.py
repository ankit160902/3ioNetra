import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient

# Add parent directory to path to import config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import settings

async def check_products():
    print(f"Connecting to MongoDB at {settings.MONGODB_URI}...")
    try:
        client = AsyncIOMotorClient(settings.MONGODB_URI)
        db = client[settings.MONGODB_DB_NAME]
        collection = db["products"]
        
        count = await collection.count_documents({})
        print(f"Total products in 'products' collection: {count}")
        
        if count > 0:
            active_count = await collection.count_documents({"is_active": True})
            print(f"Active products: {active_count}")
            
            print("\nSample Products:")
            async for doc in collection.find({}).limit(3):
                print(f"- {doc.get('name')} ({doc.get('category')}) [Active: {doc.get('is_active')}]")
        else:
            print("❌ No products found in the collection.")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(check_products())
