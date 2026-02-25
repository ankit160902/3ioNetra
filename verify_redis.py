import sys
import os
import json
import asyncio
from datetime import datetime

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from dotenv import load_dotenv
load_dotenv('backend/.env')

from services.session_manager import get_session_manager, RedisSessionManager
from services.auth_service import get_conversation_storage
from config import settings

async def verify_redis():
    print("🔍 Starting Redis Verification v2...")
    
    # 1. Verify Session Manager
    sm = get_session_manager()
    print(f"✅ Session Manager type: {type(sm)}")
    
    # Create two different sessions
    s1 = await sm.create_session()
    s2 = await sm.create_session()
    print(f"✅ Created sessions: {s1.session_id}, {s2.session_id}")
    
    await sm.update_session(s1)
    await sm.update_session(s2)
    
    r1 = await sm.get_session(s1.session_id)
    r2 = await sm.get_session(s2.session_id)
    
    if r1 and r2 and r1.session_id != r2.session_id:
        print("✅ Redis Session isolation verified")
    else:
        print("❌ Redis Session isolation failed")

    # 2. Verify Conversation Storage Cache & Multi-Session
    storage = get_conversation_storage()
    user_id = "test_user_multi_session"
    
    print("🔍 Testing Multi-Session History...")
    
    # Save session 1
    storage.save_conversation(user_id, s1.session_id, "Session 1 Title", [{"role":"user", "content":"hi"}])
    # Save session 2
    storage.save_conversation(user_id, s2.session_id, "Session 2 Title", [{"role":"user", "content":"hello"}])
    
    h_list = storage.get_conversations_list(user_id)
    print(f"✅ Fetched history list: found {len(h_list)} sessions")
    
    if len(h_list) >= 2:
        print("✅ Multi-session history verified")
    else:
        print(f"❌ Multi-session history failed (count={len(h_list)})")

    # Check cache
    import redis
    r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, decode_responses=True)
    cache_key = f"history_list:{user_id}"
    cached = r.get(cache_key)
    if cached:
        print("✅ History list correctly cached in Redis")
    else:
        print("❌ History list not found in Redis cache")
    
    # Invalidate check
    storage.save_conversation(user_id, s1.session_id, "Updated S1", [{"role":"user", "content":"updated"}])
    if not r.get(cache_key):
        print("✅ Cache invalidation verified")
    else:
        print("❌ Cache invalidation failed")

    print("🚀 Redis Verification Complete!")

if __name__ == "__main__":
    asyncio.run(verify_redis())
