# Plan: Multi-Platform Mitra — Web + WhatsApp (Production-Grade)

## Context

3ioNetra's spiritual companion "Mitra" currently runs only on the web. The goal is to make Mitra available on **two platforms** — Web and WhatsApp — with **identical core logic**, hardened for **production with concurrent users on both platforms simultaneously**.

The WhatsApp integration is **provider-agnostic** — it works with any WhatsApp Business API provider:

| Provider | How it connects |
|----------|----------------|
| Meta WhatsApp Cloud API (direct) | You manage the WABA directly via Meta's API |
| Twilio | BSP — wraps Meta's API with Twilio endpoints |
| Gupshup | BSP — popular in India, wraps Meta's API |
| QuickEngage.io | BSP — wraps Meta's API |
| Wati, AiSensy, Interakt, etc. | BSPs — all follow the same webhook + REST pattern |

**All providers follow the same pattern:** they send inbound messages to your webhook, and you send outbound messages via their REST API. The webhook payload format is standardized by Meta's WhatsApp Cloud API — BSPs either pass it through directly or use a very similar format.

**Key decisions:**
- WhatsApp users are **anonymous** — no linking to web accounts
- Core conversation logic is **platform-agnostic** (shared)
- WhatsApp provider layer is **swappable** via config — change provider without code changes
- Must handle concurrent users on both platforms without race conditions, API rate limit hits, or lost messages

---

## Architecture: Shared Core + Platform Adapters

```
                    ┌──────────────────────────────────────┐
                    │        SHARED CORE (unchanged)        │
                    │                                        │
                    │  CompanionEngine  │  IntentAgent        │
                    │  ResponseComposer │  RAGPipeline        │
                    │  SafetyValidator  │  SessionManager     │
                    │  MemoryService    │  ProductService     │
                    │  ContextSynthesizer │ CacheService      │
                    └──────────┬─────────────────────────────┘
                               │
                    ┌──────────┴──────────────┐
                    │  ConversationProcessor   │  ← NEW: extracted from chat.py
                    │  (platform-agnostic)     │
                    │                          │
                    │  + LLM Semaphore (max N) │  ← NEW: concurrency control
                    │  + Request timeout (45s) │  ← NEW: prevents hangs
                    │  + process_turn()        │  ← single entry point
                    └──────┬──────────┬────────┘
                           │          │
              ┌────────────┘          └──────────────┐
              │                                       │
    ┌─────────┴──────────┐             ┌──────────────┴──────────┐
    │  Web Adapter        │             │  WhatsApp Adapter        │
    │  (routers/chat.py)  │             │  (routers/whatsapp.py)   │
    │                     │             │                          │
    │  HTTP req → JSON    │             │  Webhook → Background    │
    │  SSE streaming      │             │  HMAC signature verify   │
    │  Bearer auth        │             │  Per-phone lock (LRU)    │
    │  Products: JSON     │             │  Message dedup           │
    │  Verses: [VERSE]    │             │  Rate limit per phone    │
    └─────────────────────┘             │  Typing indicator        │
                                        │  Retry on send failure   │
                                        │  Products: text msg      │
                                        │  Verses: _italic_        │
                                        │  Phone→session mapping   │
                                        │  Structured logging      │
                                        │  Metrics endpoint        │
                                        └──────────────────────────┘
```

---

## How WhatsApp Business API Works (Provider-Agnostic)

Regardless of which provider you use, the flow is always:

```
User sends WhatsApp message
        ↓
Meta WhatsApp Platform routes to your provider (BSP)
        ↓
Provider sends HTTP POST to YOUR webhook URL
  Body: { object: "whatsapp_business_account", entry: [{ changes: [{ value: { messages: [...] } }] }] }
        ↓
Your backend processes the message
        ↓
Your backend calls Provider's REST API to send reply
  POST https://<provider-api>/v1/<phone_number_id>/messages
  Body: { messaging_product: "whatsapp", to: "<phone>", type: "text", text: { body: "<reply>" } }
        ↓
Provider routes reply through Meta → WhatsApp → User
```

**What changes per provider:** Only the API base URL, auth header format, and minor payload variations. Our config handles all of this:

```
Meta direct:   WHATSAPP_API_BASE_URL=https://graph.facebook.com/v21.0
Twilio:        WHATSAPP_API_BASE_URL=https://api.twilio.com/2010-04-01/Accounts/{sid}
Gupshup:       WHATSAPP_API_BASE_URL=https://api.gupshup.io/wa/api/v1
QuickEngage:   WHATSAPP_API_BASE_URL=https://api.quickengage.io/v1
```

---

## Production Audit: Current State vs What's Needed

### Already in place (strong foundation)

| Component | Status | Details |
|-----------|--------|---------|
| CircuitBreaker | Done | CLOSED→OPEN→HALF_OPEN, 5-fail threshold, 60s recovery |
| Redis cache | Done | L1 memory (200 entries) + L2 Redis, 20-conn pool, 3-5s timeout |
| Session fallback | Done | Redis → MongoDB → InMemory |
| MongoDB pooling | Done | 5-50 connections, read preference, retry writes |
| LLM fallback | Done | Graceful "I'm here with you" when Gemini unavailable |
| Gemini context caching | Done | Per-model+phase cached content, 6h TTL |
| Memory-mapped embeddings | Done | `mmap_mode='r'` prevents OOM |

### Gaps this plan addresses

| Gap | Risk | Solution |
|-----|------|----------|
| No LLM concurrency limit | Gemini 429 rate limits under load | **Asyncio Semaphore** (max 20 concurrent calls) in ConversationProcessor |
| No per-user rate limiting | Abuse, runaway costs | **Redis sliding window** per phone (WhatsApp) + per IP/user (web) |
| No request timeout | Hung Gemini call blocks worker forever | **asyncio.timeout(45s)** around process_turn() |
| No message ordering for WhatsApp | Race condition: 2 messages from same phone processed simultaneously corrupt session | **Per-phone asyncio.Lock** in WhatsApp router |
| No webhook deduplication | Provider retries on timeout = duplicate responses | **Redis set** of processed message_ids (5min TTL) |
| No retry on outbound send | WhatsApp user never gets response | **3 retries with exponential backoff** in WhatsApp sender |
| No typing indicator | User thinks bot is dead during 5-15s processing | **Send "typing" status** before processing starts |
| No graceful circuit fallback | User gets HTTP 500 when Gemini is down | **Canned wisdom responses** instead of error |
| No webhook signature verification | Anyone can POST fake messages to webhook → trigger responses, waste API credits | **HMAC-SHA256 verification** of request body using app secret |
| Phone lock memory leak | `_phone_locks` dict grows unbounded over months → OOM | **LRU eviction** — cap at 10K entries, evict least-recently-used |
| No observability | Can't diagnose issues, no visibility into platform health | **Structured logging** + `/api/whatsapp/metrics` endpoint |
| Cloud Run cold start | ~2GB model load on startup → 30-60s → webhook timeout → retries | **min-instances: 1** in Cloud Run config |
| No load testing | Concurrency assumptions unvalidated | **Load test step** with concurrent simulated users |

---

## Phase 1: Extract Shared ConversationProcessor (refactor only)

### New file: `backend/services/conversation_processor.py`

Extracts platform-agnostic logic from `chat.py` into a shared module. **No behavior change** — web flow stays identical.

**What moves out of `chat.py`:**

| Function | chat.py line | Purpose |
|----------|-------------|---------|
| `_init_services()` | 250 | Returns 5 core service singletons |
| `_populate_session_with_user_context()` | 39 | Populates session with user profile + memory |
| `_get_or_create_session()` | 107 | Session lookup/creation |
| `_preflight()` | 261 | Session setup + crisis detection |
| `_run_speculative_rag()` | 279 | Engine + speculative RAG in parallel |
| `_build_guidance_context()` | 304 | Dharmic query + RAG docs |
| `_make_flow_metadata()` | 325 | Build FlowMetadata |
| `_postprocess_and_save()` | 334 | Safety validation + session persist |

**New additions in this module:**

```python
# Concurrency control — shared across ALL platforms
_llm_semaphore = asyncio.Semaphore(settings.LLM_MAX_CONCURRENT)  # default 20

@dataclass
class ConversationResult:
    """Platform-agnostic result from a conversation turn."""
    session_id: str
    phase: ConversationPhase
    response: str
    signals_collected: Dict[str, str]
    turn_count: int
    is_complete: bool              # True = guidance given
    is_crisis: bool
    recommended_products: List[dict]
    flow_metadata: FlowMetadata

async def process_turn(
    session_id: Optional[str],
    message: str,
    language: str = "en",
    user: Optional[dict] = None,
    user_profile: Optional[any] = None,
) -> ConversationResult:
    """
    THE single entry point for both Web and WhatsApp.

    Handles: session setup → crisis check → intent analysis →
    readiness assessment → guidance/listening → safety → persist.
    """
    async with asyncio.timeout(settings.REQUEST_TIMEOUT_SECONDS):
        async with _llm_semaphore:
            # ... exact same logic as current conversational_query() ...
```

**Why the semaphore matters:** Without it, 50 concurrent users each trigger 2-3 Gemini calls = 100-150 simultaneous API requests. Gemini returns 429. With semaphore(20), we queue excess calls instead of hitting rate limits.

**Why the timeout matters:** If Gemini hangs (network issue), without timeout the async task blocks indefinitely. With 45s timeout, the caller gets a graceful error and the resource is freed.

### Modified file: `backend/routers/chat.py`

Becomes a thin wrapper — imports everything from `conversation_processor`:

```python
@router.post("/conversation", response_model=ConversationalResponse)
async def conversational_query(query: ConversationalQuery, user: dict = Depends(get_current_user)):
    result = await process_turn(
        session_id=query.session_id,
        message=query.message,
        language=query.language,
        user=user,
        user_profile=query.user_profile,
    )
    return ConversationalResponse(
        session_id=result.session_id,
        phase=ConversationPhaseEnum(result.phase.value),
        response=result.response,
        signals_collected=result.signals_collected,
        turn_count=result.turn_count,
        is_complete=result.is_complete,
        recommended_products=result.recommended_products,
        flow_metadata=result.flow_metadata,
    )
```

**Streaming endpoint** stays in `chat.py` but imports the individual helpers (`_preflight`, `_run_speculative_rag`, `_build_guidance_context`, `_postprocess_and_save`) from `conversation_processor`. Streaming is web-specific (WhatsApp doesn't need it).

---

## Phase 2: WhatsApp Adapter (5 new files)

### 2a. `backend/models/whatsapp_schemas.py`

Pydantic models following the **standard Meta WhatsApp Cloud API format** (used by all BSPs):

```python
# ── Inbound (webhook payload from provider) ──────────────────

class TextBody(BaseModel):
    body: str

class WhatsAppWebhookMessage(BaseModel):
    from_phone: str = Field(..., alias="from")   # E.164 phone number
    id: str                                       # WhatsApp message ID (for dedup)
    timestamp: str
    type: str                                     # "text", "image", "audio", etc.
    text: Optional[TextBody] = None

class WhatsAppContact(BaseModel):
    wa_id: str
    profile: Optional[dict] = None                # { "name": "User Name" }

class WhatsAppStatus(BaseModel):
    id: str
    status: str                                   # "sent", "delivered", "read", "failed"
    timestamp: str
    recipient_id: str

class WhatsAppChangeValue(BaseModel):
    messaging_product: str = "whatsapp"
    metadata: dict                                # { display_phone_number, phone_number_id }
    contacts: Optional[List[WhatsAppContact]] = None
    messages: Optional[List[WhatsAppWebhookMessage]] = None
    statuses: Optional[List[WhatsAppStatus]] = None

class WhatsAppChange(BaseModel):
    value: WhatsAppChangeValue
    field: str = "messages"

class WhatsAppWebhookEntry(BaseModel):
    id: str
    changes: List[WhatsAppChange]

class WhatsAppWebhookPayload(BaseModel):
    object: str = "whatsapp_business_account"
    entry: List[WhatsAppWebhookEntry]

# ── Phone-to-session mapping (MongoDB document) ─────────────

class PhoneSessionMapping(BaseModel):
    phone: str                    # E.164 normalized
    session_id: str
    wa_name: Optional[str] = None # WhatsApp display name
    created_at: datetime
    last_active: datetime
    message_count: int = 0
```

**Provider compatibility note:** If your BSP uses a non-standard webhook format, only this file needs to change. Everything else stays the same.

### 2b. `backend/services/whatsapp_session_mapper.py`

Phone → session mapping. MongoDB collection: `whatsapp_sessions`.

**Methods:**
- `get_or_create_session(phone, wa_name)` → `(SessionState, is_new: bool)`
  1. Normalize phone to E.164 (strip non-digits, prepend `91` for Indian numbers)
  2. Look up `whatsapp_sessions` by phone
  3. If mapping found → try `SessionManager.get_session(session_id)`
     - Session exists → return it, touch `last_active`
     - Session expired → create new, update mapping
  4. No mapping → create new session + insert mapping
- `update_activity(phone)` — touch `last_active` to prevent TTL expiry
- `increment_message_count(phone)` — bump counter for analytics

**Indexes:**
- `phone` (unique)
- `last_active` (TTL: 7 days — `WHATSAPP_SESSION_TTL_HOURS`)

**Singleton:** `get_whatsapp_session_mapper()`

### 2c. `backend/services/whatsapp_sender.py`

Outbound message delivery. **Provider-agnostic** — works with any WhatsApp BSP via config.

```python
class WhatsAppSender:
    """
    Sends messages to WhatsApp users via the configured provider's REST API.

    Provider is configured via env vars:
        WHATSAPP_API_BASE_URL    — provider's API endpoint
        WHATSAPP_API_KEY         — Bearer token or API key
        WHATSAPP_PHONE_NUMBER_ID — your WhatsApp business phone number ID
    """

    def __init__(self):
        self._client = httpx.AsyncClient(
            base_url=settings.WHATSAPP_API_BASE_URL,
            headers={
                "Authorization": f"Bearer {settings.WHATSAPP_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        self._circuit = CircuitBreaker(
            name="whatsapp_api",
            failure_threshold=5,
            recovery_timeout=60,
        )

    async def send_text(self, to_phone: str, body: str) -> bool:
        """Send text message with retry + exponential backoff."""
        for attempt in range(3):
            try:
                resp = await self._circuit.call(
                    self._client.post,
                    f"/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages",
                    json={
                        "messaging_product": "whatsapp",
                        "to": to_phone,
                        "type": "text",
                        "text": {"body": body},
                    },
                )
                if resp.status_code in (200, 201):
                    return True
                if resp.status_code == 429:
                    await asyncio.sleep(2 ** attempt)  # backoff
                    continue
                logger.error(f"WA send failed: {resp.status_code}")
                return False
            except Exception as e:
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                    continue
                logger.error(f"WA send error after 3 retries: {e}")
                return False

    async def send_typing(self, to_phone: str) -> None:
        """Send typing indicator — non-critical, fire-and-forget."""
        try:
            await self._client.post(
                f"/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages",
                json={
                    "messaging_product": "whatsapp",
                    "to": to_phone,
                    "status": "typing",
                },
            )
        except Exception:
            pass  # Never fail on typing indicator

    async def send_template(
        self, to_phone: str, template_name: str,
        language_code: str = "en", parameters: Optional[List[dict]] = None,
    ) -> bool:
        """Send template message (required for messages after 24h window)."""
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            },
        }
        if parameters:
            payload["template"]["components"] = parameters
        try:
            resp = await self._client.post(
                f"/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages",
                json=payload,
            )
            return resp.status_code in (200, 201)
        except Exception:
            return False

    async def close(self):
        """Cleanup on app shutdown."""
        if self._client:
            await self._client.aclose()
```

**Singleton:** `get_whatsapp_sender()`

### 2d. `backend/services/whatsapp_formatter.py`

Adapts Mitra's responses for WhatsApp's plain-text format:

| Method | What it does |
|--------|-------------|
| `format_response(text)` | Pipeline: format verses → mantras → strip markdown → truncate to 4096 |
| `_format_verses(text)` | `[VERSE]text - Citation[/VERSE]` → `_"text"_\n~ Citation` (WhatsApp italic) |
| `_format_mantras(text)` | `[MANTRA]text[/MANTRA]` → `*text*` (WhatsApp bold) |
| `_strip_residual_markdown(text)` | Remove headers, links, code blocks (safety net) |
| `_truncate(text)` | Cap at 4096 chars, break at last complete sentence |
| `format_products(products)` | Numbered list: `*Name* - Rs X\n  description\n  URL` |
| `format_crisis_response(text)` | Bold-wrap helpline numbers: `*iCall: 9152987821*` (tappable on WhatsApp) |

**Singleton:** `get_whatsapp_formatter()`

### 2e. `backend/routers/whatsapp.py` — THE MAIN ADAPTER

**Prefix:** `/api/whatsapp`

**Four endpoints:**

#### GET `/webhook` — Verification handshake

```python
@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """Standard WhatsApp webhook verification — all providers use this."""
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN:
        return PlainTextResponse(content=hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")
```

#### POST `/webhook` — Inbound messages (production-hardened)

```python
# ── SECURITY ───────────────────────────────────────────────────

async def _verify_signature(request: Request) -> bool:
    """
    Verify webhook payload via HMAC-SHA256.
    Meta and all BSPs sign payloads with X-Hub-Signature-256 header.
    """
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not signature or not settings.WHATSAPP_APP_SECRET:
        return not settings.WHATSAPP_REQUIRE_SIGNATURE  # configurable
    body = await request.body()
    expected = "sha256=" + hmac.new(
        settings.WHATSAPP_APP_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)

# ── PRODUCTION SAFEGUARDS ──────────────────────────────────────

# 1. Per-phone locks WITH LRU eviction
from collections import OrderedDict

_phone_locks: OrderedDict[str, asyncio.Lock] = OrderedDict()
_MAX_PHONE_LOCKS = 10_000

def _get_phone_lock(phone: str) -> asyncio.Lock:
    if phone in _phone_locks:
        _phone_locks.move_to_end(phone)
        return _phone_locks[phone]
    lock = asyncio.Lock()
    _phone_locks[phone] = lock
    while len(_phone_locks) > _MAX_PHONE_LOCKS:
        _phone_locks.popitem(last=False)  # evict LRU
    return lock

# 2. Message deduplication (Redis, 5min TTL)
async def _is_duplicate(message_id: str) -> bool:
    cache = get_cache_service()
    key = f"wa_dedup:{message_id}"
    if await cache.get(key):
        return True
    await cache.set(key, "1", ttl=300)
    return False

# 3. Rate limiting per phone (Redis sliding window)
async def _check_rate_limit(phone: str) -> bool:
    cache = get_cache_service()
    key = f"wa_rate:{phone}"
    count = await cache.increment(key, ttl=settings.WHATSAPP_RATE_LIMIT_WINDOW)
    return count <= settings.WHATSAPP_RATE_LIMIT_PER_PHONE
```

**POST handler:**

```python
@router.post("/webhook")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    # Verify signature
    if not await _verify_signature(request):
        raise HTTPException(status_code=403)

    body = await request.json()
    payload = WhatsAppWebhookPayload(**body)

    # Extract messages, dispatch to background
    for entry in payload.entry:
        for change in entry.changes:
            if change.value.messages:
                for msg in change.value.messages:
                    wa_name = None
                    if change.value.contacts:
                        wa_name = change.value.contacts[0].profile.get("name")
                    background_tasks.add_task(
                        _process_whatsapp_message,
                        phone=msg.from_phone,
                        text=msg.text.body if msg.text else None,
                        message_id=msg.id,
                        msg_type=msg.type,
                        wa_name=wa_name,
                    )

    return {"status": "ok"}  # ALWAYS 200 — prevents retry storms
```

**Background processing — the core flow:**

```
_process_whatsapp_message(phone, text, message_id, msg_type, wa_name):

    # Unsupported message types
    if msg_type != "text" or not text:
        sender.send_text(phone,
            "I can read text messages for now. Please type your thoughts.")
        return

    async with _get_phone_lock(phone):       ← serialize per user

        1. if _is_duplicate(message_id): return          ← prevent retries
        2. if not _check_rate_limit(phone):
             sender.send_text(phone, "Please wait a moment...")
             return
        3. sender.send_typing(phone)                     ← UX feedback
        4. session, is_new = mapper.get_or_create_session(phone, wa_name)
        5. if is_new: sender.send_text(welcome_message)

        6. ┌──────────────────────────────────────────┐
           │  result = await process_turn(             │
           │      session_id=session.session_id,       │  ← SAME function
           │      message=text,                        │    as web!
           │      language="auto",                     │
           │      user=None,                           │
           │      user_profile=None,                   │
           │  )                                        │
           └──────────────────────────────────────────┘

        7. formatted = formatter.format_response(result.response)
        8. sender.send_text(phone, formatted)            ← with retry
        9. if result.recommended_products:
             sender.send_text(phone,
                 formatter.format_products(result.recommended_products))
        10. mapper.update_activity(phone)

        # Auto-save every 5 turns (WhatsApp has no explicit "save")
        11. if result.turn_count % 5 == 0:
              auto_save_conversation(session, phone)
```

**Why per-phone lock matters:** Without it, if a user sends "I feel lost" and "Please help" within 1 second, both webhooks arrive simultaneously. Both read session (turn_count=3), both increment to 4, both write — second overwrites first. With the lock: turn 3 → 4 → 5, in order.

**Error handling:** If anything fails, send a polite error via WhatsApp. Never return non-200 from webhook (causes retry storms).

#### GET `/metrics` — Observability

```json
{
    "messages_received": 1523,
    "messages_processed": 1520,
    "messages_failed": 3,
    "messages_deduplicated": 12,
    "messages_rate_limited": 5,
    "active_phone_locks": 47,
    "avg_latency_ms": 4200,
    "circuit_state": "CLOSED",
    "sessions_active": 83
}
```

---

## Phase 3: Configuration & Wiring

### Modified: `backend/config.py`

```python
# ------------------------------------------------------------------
# WhatsApp Business API (provider-agnostic)
# ------------------------------------------------------------------
WHATSAPP_ENABLED: bool = Field(default=False, env="WHATSAPP_ENABLED")

# Provider connection — change these to switch BSPs without code changes
WHATSAPP_API_BASE_URL: str = Field(
    default="https://graph.facebook.com/v21.0",  # Meta direct (default)
    env="WHATSAPP_API_BASE_URL"
)
WHATSAPP_API_KEY: str = Field(default="", env="WHATSAPP_API_KEY")
WHATSAPP_PHONE_NUMBER_ID: str = Field(default="", env="WHATSAPP_PHONE_NUMBER_ID")

# Webhook security
WHATSAPP_WEBHOOK_VERIFY_TOKEN: str = Field(default="", env="WHATSAPP_WEBHOOK_VERIFY_TOKEN")
WHATSAPP_APP_SECRET: str = Field(default="", env="WHATSAPP_APP_SECRET")  # HMAC signing
WHATSAPP_REQUIRE_SIGNATURE: bool = Field(default=True, env="WHATSAPP_REQUIRE_SIGNATURE")

# Session & limits
WHATSAPP_SESSION_TTL_HOURS: int = Field(default=168, env="WHATSAPP_SESSION_TTL_HOURS")  # 7 days
WHATSAPP_MAX_RESPONSE_LENGTH: int = Field(default=4096, env="WHATSAPP_MAX_RESPONSE_LENGTH")
WHATSAPP_RATE_LIMIT_PER_PHONE: int = Field(default=30, env="WHATSAPP_RATE_LIMIT_PER_PHONE")
WHATSAPP_RATE_LIMIT_WINDOW: int = Field(default=60, env="WHATSAPP_RATE_LIMIT_WINDOW")  # seconds

# ------------------------------------------------------------------
# Concurrency Control (shared across all platforms)
# ------------------------------------------------------------------
LLM_MAX_CONCURRENT: int = Field(default=20, env="LLM_MAX_CONCURRENT")
REQUEST_TIMEOUT_SECONDS: int = Field(default=45, env="REQUEST_TIMEOUT_SECONDS")
```

**Switching providers is just env var changes:**

```bash
# Meta Cloud API (direct)
WHATSAPP_API_BASE_URL=https://graph.facebook.com/v21.0
WHATSAPP_API_KEY=<your-meta-access-token>

# QuickEngage
WHATSAPP_API_BASE_URL=https://api.quickengage.io/v1
WHATSAPP_API_KEY=<your-quickengage-key>

# Twilio
WHATSAPP_API_BASE_URL=https://api.twilio.com/...
WHATSAPP_API_KEY=<your-twilio-auth-token>

# Gupshup
WHATSAPP_API_BASE_URL=https://api.gupshup.io/wa/api/v1
WHATSAPP_API_KEY=<your-gupshup-key>
```

### Modified: `backend/main.py`

```python
from routers import auth, chat, admin, whatsapp

# Register router
app.include_router(whatsapp.router)

# Shutdown — close httpx client
if settings.WHATSAPP_ENABLED:
    from services.whatsapp_sender import get_whatsapp_sender
    await get_whatsapp_sender().close()
```

### Modified: `backend/requirements.txt`

Add: `httpx>=0.25.0`

---

## How Both Platforms Compare

| What | Web | WhatsApp | Shared? |
|------|-----|----------|---------|
| CompanionEngine | Yes | Yes | **100% same** |
| IntentAgent (9-field classifier) | Yes | Yes | **100% same** |
| Phase state machine | LISTENING→GUIDANCE→CLOSURE | LISTENING→GUIDANCE→CLOSURE | **100% same** |
| Readiness assessment | Signal threshold + turn count | Signal threshold + turn count | **100% same** |
| Oscillation control (2-turn cooldown) | Yes | Yes | **100% same** |
| RAG pipeline + reranking | Yes | Yes | **100% same** |
| Safety/crisis detection | Yes | Yes | **100% same** |
| Product gating (6-gate) | Yes | Yes | **100% same** |
| Response generation (Gemini) | Yes | Yes | **100% same** |
| Response length (30-100 words) | Yes | Yes | **100% same** |
| Session storage (Redis/Mongo) | Yes | Yes | **100% same** |
| `process_turn()` | Yes | Yes | **100% same function** |
| **I/O + delivery** | HTTP JSON/SSE | Webhook + Provider API | **Different** |
| **Auth** | Bearer token | None (anonymous) | **Different** |
| **Session creation** | Frontend-initiated | Auto on first message | **Different** |
| **Product display** | JSON → card UI | Text message | **Different** |
| **Verse display** | [VERSE] tags → UI | _italic_ + citation | **Different** |
| **Typing indicator** | SSE status events | WhatsApp typing API | **Different** |

---

## Session Lifecycle (Both Platforms)

```
                          WEB                                    WHATSAPP
                          ───                                    ────────
First interaction:    POST /session/create               First message from phone
                      → session in Redis                  → phone mapping in MongoDB
                      → session_id to frontend            → session in Redis
                      → welcome message returned          → welcome message SENT

Normal turn:          POST /conversation                  Webhook POST
                      {session_id, message}               → phone lookup → session_id
                      → process_turn()                    → process_turn()          ← SAME
                      → JSON response                     → format → send via API

Session expires:      Frontend sends session_id           Phone mapping still exists
(Redis TTL 60min)     → not found → create new            → session_id → not found
                      → if auth'd, inherit memory          → create new session
                                                           → update mapping

Long absence:         Session_id invalid                  7-day TTL expires
                      → fresh session                     → no mapping → fresh start
                      → if auth'd, inherit memory          → new welcome message
```

---

## Files Summary

### New files (7)

| # | File | Purpose | Lines (est) |
|---|------|---------|-------------|
| 1 | `backend/services/conversation_processor.py` | Shared core — `process_turn()` + extracted helpers + semaphore + timeout | ~250 |
| 2 | `backend/models/whatsapp_schemas.py` | Pydantic models for webhook payloads + phone mapping | ~80 |
| 3 | `backend/services/whatsapp_session_mapper.py` | Phone → session mapping (MongoDB) | ~120 |
| 4 | `backend/services/whatsapp_sender.py` | Provider-agnostic outbound messages with retry + typing | ~120 |
| 5 | `backend/services/whatsapp_formatter.py` | Format verses/products/crisis for WhatsApp | ~100 |
| 6 | `backend/routers/whatsapp.py` | Webhook router with HMAC verify + LRU locks + dedup + rate limit + metrics | ~220 |
| 7 | `backend/tests/test_whatsapp_integration.py` | Unit tests | ~150 |

### Modified files (4)

| # | File | Changes |
|---|------|---------|
| 1 | `backend/routers/chat.py` | Remove extracted helpers → import from `conversation_processor` |
| 2 | `backend/config.py` | Add WhatsApp settings (provider-agnostic) + concurrency settings |
| 3 | `backend/main.py` | Register WhatsApp router + shutdown hook |
| 4 | `backend/requirements.txt` | Add `httpx>=0.25.0` |

---

## Production Observability

### Structured logging in `routers/whatsapp.py`

Every WhatsApp message processed gets a structured log entry:

```python
logger.info("WA_MSG", extra={
    "phone_last4": phone[-4:],       # privacy — never log full phone
    "session_id": session.session_id,
    "turn": result.turn_count,
    "phase": result.phase.value,
    "is_crisis": result.is_crisis,
    "has_products": bool(result.recommended_products),
    "latency_ms": int((time.perf_counter() - start) * 1000),
    "platform": "whatsapp",
})
```

### Cloud Run deployment hardening

```yaml
# CRITICAL: Prevent cold start webhook timeouts
min-instances: 1                    # Always 1 warm instance (~$30/month)
# Without this, first WhatsApp message after idle = 30-60s cold start
# = provider timeout = retries = duplicate/lost messages

max-instances: 4                    # Current setting
timeout: 300                        # Current setting
concurrency: 80                     # Current setting
```

---

## Implementation Order

```
PHASE 1 — Shared core extraction (web must keep working identically)
  Step 1: Create services/conversation_processor.py
          - Move 8 helpers from chat.py
          - Add ConversationResult dataclass
          - Add process_turn() with semaphore + timeout
  Step 2: Update routers/chat.py to import from conversation_processor
  Step 3: TEST — full web conversation (listening → guidance → closure)
          Must be identical to before

PHASE 2 — WhatsApp adapter
  Step 4: config.py — add WhatsApp + concurrency settings
  Step 5: models/whatsapp_schemas.py
  Step 6: services/whatsapp_formatter.py (standalone, testable immediately)
  Step 7: services/whatsapp_session_mapper.py
  Step 8: services/whatsapp_sender.py (with retry + typing)
  Step 9: routers/whatsapp.py (HMAC + LRU locks + dedup + rate limit + metrics)
  Step 10: main.py — register router + shutdown hook
  Step 11: requirements.txt — add httpx

PHASE 3 — Testing
  Step 12: tests/test_whatsapp_integration.py (unit tests)
  Step 13: curl/Postman — simulate webhook payloads locally
  Step 14: ngrok + provider webhook — live WhatsApp test

PHASE 4 — Deploy
  Step 15: Set env vars (WHATSAPP_ENABLED, WHATSAPP_API_KEY,
           WHATSAPP_API_BASE_URL, WHATSAPP_PHONE_NUMBER_ID, etc.)
  Step 16: Cloud Run: set min-instances=1
  Step 17: Register webhook URL in provider dashboard
  Step 18: End-to-end production test (both platforms simultaneously)

PHASE 5 — Load validation
  Step 19: Load test — 20 concurrent users (10 web + 10 WhatsApp)
  Step 20: Verify metrics, check for 429s, dedup, lock ordering
  Step 21: Monitor 48h — error rates, latency distribution
```

---

## WhatsApp Provider Setup — What You Need

Regardless of which provider you use, you'll need:

| What | Where it goes | How to get it |
|------|---------------|---------------|
| API access token / key | `WHATSAPP_API_KEY` | Provider dashboard → API settings |
| API base URL | `WHATSAPP_API_BASE_URL` | Provider docs (see examples above) |
| Phone Number ID | `WHATSAPP_PHONE_NUMBER_ID` | Provider dashboard → Phone numbers |
| App Secret | `WHATSAPP_APP_SECRET` | Provider dashboard → Webhook settings (for HMAC) |
| Webhook URL | Set in provider dashboard | `https://<your-domain>/api/whatsapp/webhook` |
| Verify Token | `WHATSAPP_WEBHOOK_VERIFY_TOKEN` | You generate this, set in both places |
| Event subscriptions | Set in provider dashboard | Enable "messages" + "statuses" |
| Sample webhook payload | For testing | Send yourself a test message, check provider logs |

---

## Verification Plan

### Phase 1 (core extraction):
- Start backend → web conversation → must work identically
- Streaming endpoint works
- Full listening → guidance → closure cycle

### Phase 2 (WhatsApp adapter):
- `GET /api/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=TOKEN&hub.challenge=test` → `test`
- `POST /api/whatsapp/webhook` with mock payload → 200 + background processing
- Formatter: `[VERSE]` → italic, products → numbered list, crisis → bold helplines

### Phase 3 (end-to-end):
- ngrok → provider webhook → real WhatsApp message → response arrives
- 5+ turn conversation: listening → guidance → product → verse
- Crisis message → helpline numbers (bold, tappable)
- Rapid messages → rate limit response
- 2h gap between messages → new session, still works
- Send image → "text only" reply

### Phase 4 (production):
- Multiple users simultaneously on both web + WhatsApp
- No Gemini 429 errors (semaphore working)
- No duplicate responses (dedup working)
- Per-phone ordering correct (lock working)

### Phase 5 (load testing):

```bash
# Test 1: 20 concurrent WhatsApp users sending messages every 10s
#   → All get responses, no 429s, latency < 15s
# Test 2: 10 web + 10 WhatsApp concurrent users
#   → Both platforms responsive, no cross-platform interference
# Test 3: Same phone sends 5 messages in 2 seconds
#   → Per-phone lock serializes, all 5 get ordered responses
# Test 4: Same message_id sent 3x (simulate provider retry)
#   → Only 1 response sent, 2 deduped
# Test 5: Mock Gemini 503
#   → Circuit breaker trips, fallback response on WhatsApp
```

Check `/api/whatsapp/metrics` during and after load test.
