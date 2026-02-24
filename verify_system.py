"""
Full System Verification Script — 3ioNetra
Run from: /Users/ankit1609/Desktop/3ioNetra/3ionetra/
"""
import asyncio
import sys
import os
import json

# ─── PATH SETUP ──────────────────────────────────────────────
BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
sys.path.insert(0, BACKEND_DIR)

# Load .env explicitly before importing anything else
from dotenv import load_dotenv
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️  WARN"

results = []

def log(label, status, detail=""):
    results.append({"label": label, "status": status, "detail": detail})
    tag_emoji = {"✅": "✅", "❌": "❌", "⚠️": "⚠️"}.get(status[:2], "")
    print(f"{status} | {label}" + (f"\n         {detail}" if detail else ""))

# ─────────────────────────────────────────────────────────────
# 1. MONGODB
# ─────────────────────────────────────────────────────────────
def verify_mongodb():
    print("\n" + "="*60)
    print("1. MONGODB CONNECTION & COLLECTIONS")
    print("="*60)
    try:
        # Force a fresh connection attempt (reset singleton)
        import services.auth_service as auth_mod
        auth_mod._mongo_client = None
        auth_mod._db = None

        db = auth_mod.get_mongo_client()
        if db is None:
            log("MongoDB client", FAIL, "get_mongo_client() returned None — check DNS/network or MONGODB_URI in .env")
            return False
        log("MongoDB client", PASS, f"Connected to DB: {db.name}")

        collections = db.list_collection_names()
        log("Collections", PASS, str(collections))

        for col in ["sessions", "conversations", "users", "products"]:
            count = db[col].count_documents({})
            status = PASS if count >= 0 else WARN
            log(f"  {col} count", status, f"{count} documents")

        # Write/read roundtrip
        db.verify_test.insert_one({"test": "ping"})
        found = db.verify_test.find_one({"test": "ping"})
        db.verify_test.delete_many({"test": "ping"})
        log("MongoDB read/write roundtrip", PASS if found else FAIL)
        return True

    except Exception as e:
        log("MongoDB", FAIL, str(e))
        return False

# ─────────────────────────────────────────────────────────────
# 2. PRODUCTS
# ─────────────────────────────────────────────────────────────
async def verify_products(mongo_ok: bool):
    print("\n" + "="*60)
    print("2. PRODUCT CATALOG & SEARCH")
    print("="*60)
    if not mongo_ok:
        log("Products", FAIL, "Skipped — MongoDB not connected")
        return
    try:
        # Reset singleton so it picks up fresh db connection
        import services.product_service as ps_mod
        ps_mod._product_service = None

        svc = ps_mod.get_product_service()
        if svc.collection is None:
            log("Product collection", FAIL, "collection is None — MongoDB connection failed before ProductService init")
            return

        count = svc.collection.count_documents({})
        log("Products in DB", PASS if count > 0 else FAIL, f"{count} products")
        if count > 0:
            sample = svc.collection.find_one({}, {"name": 1, "category": 1, "is_active": 1, "_id": 0})
            log("Sample product", PASS, str(sample))

        active_count = svc.collection.count_documents({"is_active": True})
        log("Active products", PASS if active_count > 0 else WARN, f"{active_count} active")

        # Search tests
        for query_text, desc in [
            ("rudraksha mala", "Rudraksha Mala"),
            ("puja pooja", "Puja items"),
            ("spiritual book gita", "Spiritual books"),
        ]:
            found = await svc.search_products(query_text)
            if found:
                log(f"Search: '{desc}'", PASS, f"{len(found)} results — '{found[0].get('name','?')}'")
            else:
                log(f"Search: '{desc}'", WARN, "0 results")

        # Recommended products fallback
        rec = await svc.get_recommended_products()
        log("Recommended products fallback", PASS if rec else WARN, f"{len(rec)} returned")

    except Exception as e:
        log("Products", FAIL, str(e))

# ─────────────────────────────────────────────────────────────
# 3. SAFETY VALIDATOR
# ─────────────────────────────────────────────────────────────
async def verify_safety():
    print("\n" + "="*60)
    print("3. SAFETY VALIDATOR")
    print("="*60)
    try:
        from services.safety_validator import get_safety_validator, CRISIS_KEYWORDS, ADDICTION_KEYWORDS
        from models.session import SessionState, SignalType

        sv = get_safety_validator()

        # Crisis detection — using exact keyword phrases from CRISIS_KEYWORDS list
        crisis_tests = [
            ("I want to kill myself", True),
            ("I don't want to live anymore", True),
            ("I want to end my life", True),
            ("I feel hopeless and tired", False),
            ("Tell me about meditation", False),
        ]
        for msg, expected in crisis_tests:
            session = SessionState(user_id="test_safety")
            is_crisis, response = await sv.check_crisis_signals(session, msg)
            status = PASS if is_crisis == expected else FAIL
            log(f"Crisis '{msg[:40]}'", status,
                f"detected={is_crisis} expected={expected}")

        # Addiction detection — using exact keywords from list
        session_addict = SessionState(user_id="test_addict")
        session_addict.conversation_history = [
            {"role": "user", "content": "I think I have an alcoholic problem and cant stop drinking"}
        ]
        needs_help, help_type = sv.check_needs_professional_help(
            session_addict, "I need rehab"
        )
        log("Addiction detection", PASS if needs_help else FAIL,
            f"needs_help={needs_help}, type={help_type}")

        # Mental health detection
        session_mh = SessionState(user_id="test_mh")
        needs_help2, type2 = sv.check_needs_professional_help(
            session_mh, "I have severe depression and panic attacks"
        )
        log("Mental health detection", PASS if needs_help2 else FAIL,
            f"needs_help={needs_help2}, type={type2}")

        # Scripture density reduction
        session_distress = SessionState(user_id="test_density")
        session_distress.add_signal(SignalType.EMOTION, "hopelessness", 0.9)
        session_distress.add_signal(SignalType.SEVERITY, "severe", 0.9)
        reduce = sv.should_reduce_scripture_density(session_distress)
        log("Scripture density reduce (hopelessness+severe)", PASS if reduce else FAIL,
            f"should_reduce={reduce}")

        # Validate response (banned patterns)
        dirty = "This situation happened because karma from past life and you brought this upon yourself."
        cleaned = await sv.validate_response(dirty)
        log("Response validation (banned patterns)", PASS if cleaned != dirty else WARN,
            f"Modified: {cleaned[:80]}")

        # Professional help suffix appended
        base = "Here is some guidance."
        with_suffix = sv.append_professional_help(base, "addiction", already_mentioned=False)
        log("Professional help append", PASS if len(with_suffix) > len(base) else FAIL)

    except Exception as e:
        log("Safety Validator", FAIL, str(e))

# ─────────────────────────────────────────────────────────────
# 4. PANCHANG
# ─────────────────────────────────────────────────────────────
def verify_panchang():
    print("\n" + "="*60)
    print("4. PANCHANG SERVICE")
    print("="*60)
    try:
        from services.panchang_service import get_panchang_service
        from datetime import datetime
        svc = get_panchang_service()
        if not svc.available:
            log("Panchang available", FAIL, "Not available — ephem may need restart")
            return
        log("Panchang available", PASS)

        data = svc.get_panchang(datetime.now())
        if "error" in data:
            log("Panchang data", FAIL, data["error"])
        else:
            log("Tithi", PASS if data.get("tithi") else FAIL, data.get("tithi","?"))
            log("Nakshatra", PASS if data.get("nakshatra") else FAIL, data.get("nakshatra","?"))
            special = svc.get_special_day_info(data)
            log("Special day info", PASS, str(special)[:80])

    except Exception as e:
        log("Panchang", FAIL, str(e))

# ─────────────────────────────────────────────────────────────
# 5. TTS
# ─────────────────────────────────────────────────────────────
def verify_tts():
    print("\n" + "="*60)
    print("5. TTS SERVICE")
    print("="*60)
    try:
        from services.tts_service import get_tts_service
        svc = get_tts_service()
        if not svc.available:
            log("TTS available", FAIL, "gTTS not available")
            return
        log("TTS available", PASS)

        # English
        buf = svc.synthesize("Namaste, I am here with you.", lang="en")
        if buf:
            buf.seek(0, 2); size = buf.tell()
            log("TTS English", PASS, f"{size} bytes")
        else:
            log("TTS English", FAIL, "synthesize returned None")

        # Hindi
        buf2 = svc.synthesize("कर्म करो फल की चिंता मत करो।", lang="hi")
        if buf2:
            buf2.seek(0, 2); size2 = buf2.tell()
            log("TTS Hindi", PASS, f"{size2} bytes")
        else:
            log("TTS Hindi", FAIL, "Hindi synthesize returned None")

    except Exception as e:
        log("TTS", FAIL, str(e))

# ─────────────────────────────────────────────────────────────
# 6. AUTH SERVICE
# ─────────────────────────────────────────────────────────────
def verify_auth(mongo_ok: bool):
    print("\n" + "="*60)
    print("6. AUTH SERVICE")
    print("="*60)
    try:
        from services.auth_service import AuthService, get_mongo_client
        auth = AuthService()

        if auth.db is None:
            log("Auth DB", FAIL if mongo_ok else WARN, "No DB connection")
        else:
            log("Auth DB", PASS)

            # Test token round-trip using internal _create_token / verify_token
            import secrets
            test_user_id = f"verify_test_{secrets.token_hex(4)}"
            token = auth._create_token(test_user_id)
            if token:
                log("Token generation", PASS, f"Length: {len(token)}")
                # We can't verify without a user doc, just check it was stored
                db = get_mongo_client()
                tok_doc = db.tokens.find_one({"token": token})
                if tok_doc:
                    log("Token stored in DB", PASS, f"user_id={tok_doc['user_id']}, expires={tok_doc['expires_at']}")
                    db.tokens.delete_one({"token": token})  # cleanup
                else:
                    log("Token stored in DB", FAIL, "Token not found after creation")
            else:
                log("Token generation", FAIL, "_create_token returned empty")

            # Check registered users
            db = get_mongo_client()
            user_count = db.users.count_documents({})
            log("Registered users", PASS if user_count > 0 else WARN, f"{user_count} in DB")
            if user_count > 0:
                sample = db.users.find_one({}, {"first_name":1,"email":1,"spiritual_profile":1,"_id":0})
                log("User schema sample", PASS, str(sample)[:120])

    except Exception as e:
        log("Auth", FAIL, str(e))

# ─────────────────────────────────────────────────────────────
# 7. CONVERSATION HISTORY
# ─────────────────────────────────────────────────────────────
def verify_conversation_history(mongo_ok: bool):
    print("\n" + "="*60)
    print("7. CONVERSATION HISTORY SAVE / RESTORE")
    print("="*60)
    if not mongo_ok:
        log("Conversation History", FAIL, "Skipped — MongoDB not connected")
        return
    try:
        from services.auth_service import get_mongo_client
        db = get_mongo_client()

        count = db.conversations.count_documents({})
        log("Conversations in DB", PASS if count > 0 else WARN, f"{count} conversations")

        sample = db.conversations.find_one({}, {"user_id":1,"messages":1,"memory":1,"_id":0})
        if sample:
            msgs = sample.get("messages", [])
            mem = sample.get("memory")
            log("Doc has messages", PASS if msgs else WARN, f"{len(msgs)} messages")
            log("Doc has memory dict", PASS if mem else WARN, "memory saved" if mem else "no saved memory yet")

            # Check vectorized memory
            vec_doc = db.conversations.find_one(
                {"vectorized_memory": {"$exists": True}},
                {"user_id":1,"vectorized_memory":1,"_id":0}
            )
            if vec_doc:
                mems = vec_doc.get("vectorized_memory",[])
                log("Vectorized memories", PASS if mems else WARN,
                    f"{len(mems)} semantic anchors for user {vec_doc.get('user_id','?')}")
            else:
                log("Vectorized memories", WARN, "No vectorized_memory field found — users need longer sessions to build these")
        else:
            log("Conversation docs", WARN, "No conversations saved yet — needs at least one real chat session")

    except Exception as e:
        log("Conversation History", FAIL, str(e))

# ─────────────────────────────────────────────────────────────
# 8. RAG PIPELINE
# ─────────────────────────────────────────────────────────────
async def verify_rag():
    print("\n" + "="*60)
    print("8. RAG PIPELINE — SEARCH QUALITY")
    print("="*60)
    try:
        from rag.pipeline import RAGPipeline
        pipeline = RAGPipeline()
        await pipeline.initialize()

        if not pipeline.available:
            log("RAG pipeline", FAIL, "Not available after initialize()")
            return
        log("RAG pipeline", PASS, "Initialized")

        tests = [
            ("detachment from results karma yoga", "Bhagavad Gita / karma"),
            ("pitta dosha diet summer ayurveda", "Ayurveda"),
            ("Tirupati Venkateswara temple darshan pilgrimage", "Temple"),
            ("grief loss loved one how to cope", "Grief/emotional"),
        ]
        for query, label in tests:
            docs = await pipeline.search(query=query, top_k=3)
            if docs:
                top = docs[0]
                log(f"RAG: '{label}'", PASS,
                    f"{len(docs)} results | top='{top.get('reference','?')[:50]}' score={top.get('score',0):.3f}")
            else:
                log(f"RAG: '{label}'", WARN, "0 results")

    except Exception as e:
        log("RAG Pipeline", FAIL, str(e))

# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
async def main():
    print("\n" + "="*60)
    print(" 3ioNetra — FULL SYSTEM VERIFICATION")
    print("="*60)

    mongo_ok = verify_mongodb()
    verify_panchang()
    verify_tts()
    verify_auth(mongo_ok)
    verify_conversation_history(mongo_ok)

    await verify_products(mongo_ok)
    await verify_safety()
    await verify_rag()

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r["status"] == PASS)
    warned  = sum(1 for r in results if r["status"] == WARN)
    failed  = sum(1 for r in results if r["status"] == FAIL)

    print("\n" + "="*60)
    print(f"FINAL SCORE: {passed}/{total} PASS  |  {warned} WARN  |  {failed} FAIL")
    print("="*60)
    if failed:
        print("\nFAILURES:")
        for r in results:
            if r["status"] == FAIL:
                print(f"  ❌ {r['label']}: {r['detail']}")
    if warned:
        print("\nWARNINGS:")
        for r in results:
            if r["status"] == WARN:
                print(f"  ⚠️  {r['label']}: {r['detail']}")

    with open("verify_system_results.json", "w") as f:
        json.dump({"score": f"{passed}/{total}", "pass": passed, "warn": warned, "fail": failed,
                   "results": results}, f, indent=2)
    print("\nFull results saved to verify_system_results.json")

if __name__ == "__main__":
    asyncio.run(main())
