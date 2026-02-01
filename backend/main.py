"""
Main FastAPI application for 3ioNetra Spiritual Companion
A text-based spiritual companion that listens deeply and offers personalized wisdom
"""
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict
from enum import Enum
import json
import logging

from config import settings
from rag.pipeline import RAGPipeline

# Import conversation flow services
from models.session import SessionState, ConversationPhase
from services.session_manager import get_session_manager
from services.context_synthesizer import get_context_synthesizer
from services.safety_validator import get_safety_validator
from services.response_composer import get_response_composer
from services.companion_engine import get_companion_engine
from services.auth_service import get_auth_service, get_conversation_storage

from rag.pipeline import RAGPipeline
from rag.vector_store import get_vector_store

from llm.service import get_llm_service
from llm.formatter import get_refiner, get_reformatter

# Setup logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="3ioNetra Spiritual Companion API",
    version=settings.API_VERSION,
    description="3ioNetra - A text-based spiritual companion that listens deeply and offers personalized wisdom from Sanatan Dharma"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://3io-netra-spiritual-companion.vercel.app",
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8000",
        "http://localhost:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
rag_pipeline: Optional[RAGPipeline] = None


# Pydantic models
class TextQuery(BaseModel):
    query: str
    language: str = "en"
    include_citations: bool = True
    conversation_history: Optional[List[dict]] = None


class TextResponse(BaseModel):
    answer: str
    citations: List[dict]
    language: str
    confidence: float


# Conversation Flow Models
class ConversationPhaseEnum(str, Enum):
    """Enum for API responses"""
    clarification = "clarification"
    synthesis = "synthesis"
    answering = "answering"
    listening = "listening"
    guidance = "guidance"
    closure = "closure"


class SessionCreateResponse(BaseModel):
    """Response when creating a new session"""
    session_id: str
    phase: ConversationPhaseEnum
    message: str


class SessionStateResponse(BaseModel):
    """Response for session state query"""
    session_id: str
    phase: ConversationPhaseEnum
    turn_count: int
    signals_collected: Dict[str, str]
    created_at: str


class UserProfileContext(BaseModel):
    """User profile for personalization (from authenticated user)"""
    age_group: str = ""
    gender: str = ""
    profession: str = ""
    name: str = ""


class ConversationalQuery(BaseModel):
    """Request body for conversational endpoint"""
    session_id: Optional[str] = None  # None = create new session
    message: str
    language: str = "en"
    user_profile: Optional[UserProfileContext] = None  # Pre-populated from auth


class ConversationalResponse(BaseModel):
    """Response from conversational endpoint"""
    session_id: str
    phase: ConversationPhaseEnum
    response: str
    signals_collected: Dict[str, str]
    turn_count: int
    is_complete: bool  # True when in answering phase
    citations: Optional[List[dict]] = None


# ============================================================================
# AUTHENTICATION MODELS
# ============================================================================

class UserRegisterRequest(BaseModel):
    """Request body for user registration with extended profile"""
    name: str
    email: str
    password: str
    phone: str = ""
    gender: str = ""
    dob: str = ""  # Format: YYYY-MM-DD
    profession: str = ""


class UserLoginRequest(BaseModel):
    """Request body for user login"""
    email: str
    password: str


class UserResponse(BaseModel):
    """User info in responses"""
    id: str
    name: str
    email: str
    phone: str = ""
    gender: str = ""
    dob: str = ""
    age: int = 0
    age_group: str = ""
    profession: str = ""
    created_at: str


class AuthResponse(BaseModel):
    """Response for login/register"""
    user: UserResponse
    token: str


class SaveConversationRequest(BaseModel):
    """Request to save a conversation"""
    conversation_id: Optional[str] = None
    title: str
    messages: List[dict]


# Helper function to verify auth token
async def get_current_user(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    """Extract and verify user from Authorization header"""
    if not authorization:
        return None

    if not authorization.startswith("Bearer "):
        return None

    token = authorization[7:]  # Remove "Bearer " prefix
    auth_service = get_auth_service()
    return auth_service.verify_token(token)


@app.on_event("startup")
async def startup_event():
    """Initialize models on startup"""
    global rag_pipeline

    logger.info("Starting 3ioNetra Spiritual Companion API...")

    # Start heavy initialization in background to allow fast container startup
    import asyncio
    asyncio.create_task(initialize_components_background())
    logger.info("🚀 Server started! Heavy components initializing in background...")


async def initialize_components_background():
    """Background task to initialize heavy components"""
    global rag_pipeline
    
    # Fix MongoDB index issue (run once to clean up)
    try:
        from pymongo import MongoClient
        mongo_uri = settings.MONGODB_URI

        if settings.DATABASE_PASSWORD:
            mongo_uri = mongo_uri.replace("<db_password>", settings.DATABASE_PASSWORD)
        
        client = MongoClient(mongo_uri)
        db = client[settings.DATABASE_NAME]
        
        try:
            db.conversations.drop_index("conversation_id_1")
            logger.info("✅ Dropped old conversation_id_1 index")
        except:
            logger.info("conversation_id_1 index doesn't exist (already cleaned)")
        
        client.close()
    except Exception as e:
        logger.warning(f"Could not drop index: {e}")

    try:
        # Initialize RAG Pipeline
        logger.info("Initializing RAG Pipeline (Background)...")
        rag_pipeline = RAGPipeline()
        await rag_pipeline.initialize()
        logger.info("✅ RAG Pipeline initialized")

        # Initialize LLM Service
        logger.info("Initializing LLM Service...")
        llm_service = get_llm_service()
        if llm_service.available:
            logger.info("✅ LLM Service initialized successfully with Gemini")
        else:
            logger.warning("LLM Service not available - will use fallback templates. Set GEMINI_API_KEY to enable.")

        # Initialize Query Refiner
        logger.info("Initializing Query Refiner...")
        refiner = get_refiner(settings.GEMINI_API_KEY)
        if refiner and refiner.available:
            logger.info("✅ Query Refiner initialized successfully")
        else:
            logger.warning("Query Refiner not available")

        # Initialize Response Reformatter
        logger.info("Initializing Response Reformatter...")
        reformatter = get_reformatter(settings.GEMINI_API_KEY)
        if reformatter and reformatter.available:
            logger.info("✅ Response Reformatter initialized successfully")
        else:
            logger.warning("Response Reformatter not available")

        # Initialize Conversation Flow Services
        logger.info("Initializing Conversation Flow Services...")

        # Session Manager
        session_manager = get_session_manager(ttl_minutes=settings.SESSION_TTL_MINUTES)
        logger.info(f"✅ Session Manager initialized (TTL: {settings.SESSION_TTL_MINUTES} min)")

        # Context Synthesizer
        get_context_synthesizer()
        logger.info("✅ Context Synthesizer initialized")

        # Safety Validator
        safety_validator = get_safety_validator(enable_crisis_detection=settings.ENABLE_CRISIS_DETECTION)
        logger.info(f"✅ Safety Validator initialized (crisis_detection={settings.ENABLE_CRISIS_DETECTION})")

        # Response Composer
        response_composer = get_response_composer()
        if response_composer.available:
            logger.info("✅ Response Composer initialized with Gemini")
        else:
            logger.info("Response Composer using templates")

        # Companion Engine (new empathetic conversation handler)
        companion_engine = get_companion_engine()
        if companion_engine.available:
            logger.info("✅ Companion Engine initialized with Gemini")
        else:
            logger.info("Companion Engine using templates")
        
        # Connect RAG pipeline to Companion Engine for spiritually-informed responses
        if rag_pipeline:
            companion_engine.set_rag_pipeline(rag_pipeline)
            logger.info("✅ RAG pipeline connected to Companion Engine")

        logger.info("🎉 All components initialized successfully!")

    except Exception as e:
        logger.error(f"❌ Failed to initialize components: {str(e)}")
        # Note: We don't raise here because it crashes the background task, 
        # but the server stays running. It's better than crashing the container loop.

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down 3ioNetra Spiritual Companion API...")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to 3ioNetra Spiritual Companion API",
        "version": settings.API_VERSION,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "components": {
            "rag": rag_pipeline is not None
        }
    }


@app.post("/api/text/query", response_model=TextResponse)
async def text_query(query: TextQuery):
    """
    Process text query and return text response with citations
    """
    try:
        if not rag_pipeline:
            raise HTTPException(status_code=500, detail="RAG pipeline not initialized")

        logger.info(f"Processing text query: {query.query[:50]}...")

        # Get response from RAG pipeline with conversation history
        result = await rag_pipeline.query(
            query=query.query,
            language=query.language,
            include_citations=query.include_citations,
            conversation_history=query.conversation_history
        )

        return TextResponse(
            answer=result["answer"],
            citations=result["citations"],
            language=query.language,
            confidence=result["confidence"]
        )

    except Exception as e:
        logger.error(f"Error processing text query: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/text/query/stream")
async def text_query_stream(query: TextQuery):
    """
    Process text query and return streaming text response
    """
    try:
        if not rag_pipeline:
            raise HTTPException(status_code=500, detail="RAG pipeline not initialized")

        logger.info(f"Processing streaming text query: {query.query[:50]}...")

        async def generate_stream():
            try:
                # Stream response from RAG pipeline with conversation history
                async for chunk in rag_pipeline.query_stream(
                    query=query.query,
                    language=query.language,
                    include_citations=query.include_citations,
                    conversation_history=query.conversation_history
                ):
                    # For SSE format, we need to escape newlines in the chunk
                    # because \n\n terminates an SSE event
                    # Replace actual newlines with escaped newlines for JSON compatibility
                    import json
                    # JSON encode the chunk to escape special characters
                    chunk_escaped = json.dumps(chunk)
                    # Send as Server-Sent Events format
                    yield f"data: {chunk_escaped}\n\n"
            except Exception as e:
                logger.error(f"Error in stream generation: {str(e)}")
                yield f"data: [ERROR] {str(e)}\n\n"

        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    except Exception as e:
        logger.error(f"Error processing streaming text query: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/scripture/search")
async def search_scripture(
    query: str,
    scripture: Optional[str] = None,
    language: str = "en",
    limit: int = 5
):
    """
    Search scriptures directly
    """
    try:
        if not rag_pipeline:
            raise HTTPException(status_code=500, detail="RAG pipeline not initialized")

        results = await rag_pipeline.search(
            query=query,
            scripture_filter=scripture,
            language=language,
            top_k=limit
        )

        return {
            "query": query,
            "results": results,
            "count": len(results)
        }

    except Exception as e:
        logger.error(f"Error searching scripture: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/embeddings/generate")
async def generate_embeddings(text: str):
    """
    Generate embeddings for text (utility endpoint)
    """
    try:
        if not rag_pipeline:
            raise HTTPException(status_code=500, detail="RAG pipeline not initialized")

        embeddings = await rag_pipeline.generate_embeddings(text)

        return {
            "text": text,
            "embeddings": embeddings.tolist(),
            "dimension": len(embeddings)
        }

    except Exception as e:
        logger.error(f"Error generating embeddings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CONVERSATION FLOW ENDPOINTS
# ============================================================================

@app.post("/api/session/create", response_model=SessionCreateResponse)
async def create_session():
    """
    Create a new conversation session.
    Returns session ID and welcome message.
    """
    try:
        session_manager = get_session_manager()

        session = await session_manager.create_session(
            min_signals=settings.MIN_SIGNALS_THRESHOLD,
            min_turns=settings.MIN_CLARIFICATION_TURNS,
            max_turns=settings.MAX_CLARIFICATION_TURNS
        )

        welcome_message = "Namaste. I'm here to listen and understand what you're going through. Please share what's on your mind, and I'll do my best to offer guidance from the wisdom of Sanātana Dharma."

        logger.info(f"Created new session: {session.session_id}")

        return SessionCreateResponse(
            session_id=session.session_id,
            phase=ConversationPhaseEnum(session.phase.value),
            message=welcome_message
        )

    except Exception as e:
        logger.error(f"Error creating session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/session/{session_id}", response_model=SessionStateResponse)
async def get_session_state(session_id: str):
    """
    Get current session state.
    """
    try:
        session_manager = get_session_manager()
        session = await session_manager.get_session(session_id)

        if not session:
            raise HTTPException(status_code=404, detail="Session not found or expired")

        return SessionStateResponse(
            session_id=session.session_id,
            phase=ConversationPhaseEnum(session.phase.value),
            turn_count=session.turn_count,
            signals_collected=session.get_signals_summary(),
            created_at=session.created_at.isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session state: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/conversation", response_model=ConversationalResponse)
async def conversational_query(query: ConversationalQuery, user: dict = Depends(get_current_user)):
    """
    Main conversational endpoint with empathetic companion flow.

    Enhanced Flow:
    1. Create/retrieve session
    2. Safety check for crisis
    3. Companion Engine processes message:
       - Listens deeply and builds memory context
       - Decides if ready for wisdom
    4. If not ready: Ask empathetic follow-up question
    5. If ready: Synthesize understanding + retrieve wisdom + compose personalized response
    """
    try:
        if not rag_pipeline:
            raise HTTPException(status_code=500, detail="RAG pipeline not initialized")

        # Get services
        session_manager = get_session_manager()
        companion_engine = get_companion_engine()
        context_synthesizer = get_context_synthesizer()
        safety_validator = get_safety_validator()
        response_composer = get_response_composer()

        # Get or create session
        if query.session_id:
            session = await session_manager.get_session(query.session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session expired. Please start a new conversation.")
        else:
            session = await session_manager.create_session(
                min_signals=settings.MIN_SIGNALS_THRESHOLD,
                min_turns=settings.MIN_CLARIFICATION_TURNS,
                max_turns=settings.MAX_CLARIFICATION_TURNS
            )

        # ALWAYS refresh user data in session memory if user is authenticated
        # This ensures even existing sessions get updated with user profile
        if user:
            # Update authenticated user information in memory
            session.memory.user_id = user.get('id', '')
            session.memory.user_name = user.get('name', '')
            session.memory.user_email = user.get('email', '')
            session.memory.user_phone = user.get('phone', '')
            session.memory.user_dob = user.get('dob', '')
            session.memory.user_created_at = user.get('created_at', '')
            
            # Update user demographics in story (only if not already set or if user data has changed)
            story = session.memory.story
            if user.get('age_group'):
                story.age_group = user.get('age_group')
            if user.get('gender'):
                story.gender = user.get('gender')
            if user.get('profession'):
                story.profession = user.get('profession')
            
            logger.info(
                f"Session {session.session_id}: Refreshed user data "
                f"(id={session.memory.user_id}, name={session.memory.user_name}, age_group={story.age_group})"
            )
        
        # Also populate from user_profile if provided in query
        if query.user_profile:
            profile = query.user_profile
            story = session.memory.story
            if profile.age_group:
                story.age_group = profile.age_group
            if profile.gender:
                story.gender = profile.gender
            if profile.profession:
                story.profession = profile.profession
            logger.info(
                f"Session {session.session_id}: Updated with user profile "
                f"(age_group={profile.age_group}, profession={profile.profession})"
            )

        # Safety check first
        is_crisis, crisis_response = await safety_validator.check_crisis_signals(
            session, query.message
        )
        if is_crisis:
            session.add_message('user', query.message)
            session.add_message('assistant', crisis_response)
            await session_manager.update_session(session)

            return ConversationalResponse(
                session_id=session.session_id,
                phase=ConversationPhaseEnum(session.phase.value),
                response=crisis_response,
                signals_collected=session.get_signals_summary(),
                turn_count=session.turn_count,
                is_complete=False
            )

        # Add user message to history
        session.add_message('user', query.message)
        session.turn_count += 1

        # Let the companion engine process the message
        # It will: analyze, build memory, and decide if ready for wisdom
        companion_response, is_ready_for_wisdom = await companion_engine.process_message(
            session, query.message
        )

        logger.info(f"Session {session.session_id}: turn={session.turn_count}, memory_readiness={session.memory.readiness_for_wisdom:.2f}, ready={is_ready_for_wisdom}")

        if is_ready_for_wisdom:
            # Transition to guidance phase
            session.phase = ConversationPhase.GUIDANCE
            
            # Use memory-aware synthesis
            session.dharmic_query = context_synthesizer.synthesize_from_memory(session)
            dharmic_query = session.dharmic_query
            search_query = dharmic_query.build_search_query()

            # Retrieve relevant verses
            retrieved_docs = await rag_pipeline.search(
                query=search_query,
                scripture_filter=None,
                language=query.language,
                top_k=5
            )

            # Check if we should reduce scripture density
            reduce_scripture = safety_validator.should_reduce_scripture_density(session)

            response_text = await response_composer.compose_with_memory(
                dharmic_query=dharmic_query,
                memory=session.memory,
                retrieved_verses=retrieved_docs,
                reduce_scripture=reduce_scripture,
                phase=ConversationPhase.GUIDANCE,
                original_query=query.message
            )

            # Validate response
            response_text = await safety_validator.validate_response(response_text)

            
            # Add to history
            session.add_message('assistant', response_text)

            # Oscillation Logic: Reset readiness to encourage listening phase next
            session.memory.readiness_for_wisdom = 0.3  # Drop significantly to force listening turns
            session.last_guidance_turn = session.turn_count # Mark this turn as guidance

            await session_manager.update_session(session)

            # Auto-save conversation to MongoDB if user is authenticated
            if user:
                try:
                    storage = get_conversation_storage()
                    first_user_msg = next((msg['content'] for msg in session.conversation_history if msg['role'] == 'user'), 'Conversation')
                    title = first_user_msg[:50] + '...' if len(first_user_msg) > 50 else first_user_msg
                    
                    storage.save_conversation(
                        user_id=user["id"],
                        conversation_id=session.session_id,
                        title=title,
                        messages=session.conversation_history
                    )
                    logger.info(f"Auto-saved conversation {session.session_id} for user {user['id']}")
                except Exception as e:
                    logger.error(f"Failed to auto-save conversation: {e}")


            # Build citations
            citations = [
                {
                    'reference': doc.get('reference', ''),
                    'scripture': doc.get('scripture', ''),
                    'text': doc.get('text', '')[:200],
                    'score': doc.get('score', 0)
                }
                for doc in retrieved_docs[:2]
            ]

            return ConversationalResponse(
                session_id=session.session_id,
                phase=ConversationPhaseEnum.guidance,
                response=response_text,
                signals_collected=session.get_signals_summary(),
                turn_count=session.turn_count,
                is_complete=True,
                citations=citations
            )

        else:
            # Still in listening phase - return companion's empathetic response
            session.add_message('assistant', companion_response)
            await session_manager.update_session(session)
            
            # Auto-save conversation to MongoDB if user is authenticated
            if user:
                try:
                    storage = get_conversation_storage()
                    first_user_msg = next((msg['content'] for msg in session.conversation_history if msg['role'] == 'user'), 'Conversation')
                    title = first_user_msg[:50] + '...' if len(first_user_msg) > 50 else first_user_msg
                    
                    storage.save_conversation(
                        user_id=user["id"],
                        conversation_id=session.session_id,
                        title=title,
                        messages=session.conversation_history
                    )
                    logger.info(f"Auto-saved conversation {session.session_id} for user {user['id']}")
                except Exception as e:
                    logger.error(f"Failed to auto-save conversation: {e}")

            return ConversationalResponse(
                session_id=session.session_id,
                phase=ConversationPhaseEnum.listening,
                response=companion_response,
                signals_collected=session.get_signals_summary(),
                turn_count=session.turn_count,
                is_complete=False
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in conversational query: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/conversation/stream")
async def conversational_query_stream(query: ConversationalQuery, user: dict = Depends(get_current_user)):
    """
    Streaming version of conversational endpoint.
    Streams response during ANSWERING phase only.
    During CLARIFICATION, returns complete question immediately.
    """
    try:
        if not rag_pipeline:
            raise HTTPException(status_code=500, detail="RAG pipeline not initialized")

        # For now, use the non-streaming endpoint and wrap in SSE
        # Full streaming implementation can be added later
        # Create a modified query object for the conversational endpoint
        response = await conversational_query(query, user)

        async def generate_stream():
            # Send the response as a single SSE event with metadata
            data = {
                "session_id": response.session_id,
                "phase": response.phase.value,
                "turn_count": response.turn_count,
                "signals_collected": response.signals_collected,
                "is_complete": response.is_complete,
                "citations": response.citations,
            }
            yield f"data: {json.dumps(data)}\n\n"

            # Stream the response text
            yield f"data: {json.dumps(response.response)}\n\n"

            # End signal
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in streaming conversational query: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    """
    Delete a session explicitly.
    """
    try:
        session_manager = get_session_manager()
        await session_manager.delete_session(session_id)

        return {"message": "Session deleted", "session_id": session_id}

    except Exception as e:
        logger.error(f"Error deleting session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@app.post("/api/auth/register", response_model=AuthResponse)
async def register_user(request: UserRegisterRequest):
    """
    Register a new user account with extended profile.
    """
    try:
        auth_service = get_auth_service()

        result = auth_service.register_user(
            name=request.name,
            email=request.email,
            password=request.password,
            phone=request.phone,
            gender=request.gender,
            dob=request.dob,
            profession=request.profession
        )

        if not result:
            raise HTTPException(status_code=400, detail="Email already registered")

        return AuthResponse(
            user=UserResponse(**result["user"]),
            token=result["token"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auth/login", response_model=AuthResponse)
async def login_user(request: UserLoginRequest):
    """
    Login an existing user.
    """
    try:
        auth_service = get_auth_service()

        result = auth_service.login_user(
            email=request.email,
            password=request.password
        )

        if not result:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        return AuthResponse(
            user=UserResponse(**result["user"]),
            token=result["token"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error logging in user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/auth/verify")
async def verify_auth(user: dict = Depends(get_current_user)):
    """
    Verify authentication token.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return {"valid": True, "user": user}


@app.post("/api/auth/logout")
async def logout_user(authorization: Optional[str] = Header(None)):
    """
    Logout user and invalidate token.
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        auth_service = get_auth_service()
        auth_service.logout_user(token)

    return {"message": "Logged out successfully"}


# ============================================================================
# USER CONVERSATION HISTORY ENDPOINTS
# ============================================================================

@app.get("/api/user/conversations")
async def get_user_conversations(user: dict = Depends(get_current_user)):
    """
    Get list of user's saved conversations.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        storage = get_conversation_storage()
        conversations = storage.get_conversations_list(user["id"])

        return {"conversations": conversations}

    except Exception as e:
        logger.error(f"Error getting conversations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/user/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Get a specific conversation.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        storage = get_conversation_storage()
        conversation = storage.get_conversation(user["id"], conversation_id)

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return conversation

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/user/conversations")
async def save_conversation(
    request: SaveConversationRequest,
    user: dict = Depends(get_current_user)
):
    """
    Save or update a conversation.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        storage = get_conversation_storage()
        conversation_id = storage.save_conversation(
            user_id=user["id"],
            conversation_id=request.conversation_id,
            title=request.title,
            messages=request.messages
        )

        return {
            "message": "Conversation saved",
            "conversation_id": conversation_id
        }

    except Exception as e:
        logger.error(f"Error saving conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/user/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Delete a conversation.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        storage = get_conversation_storage()
        deleted = storage.delete_conversation(user["id"], conversation_id)

        if not deleted:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return {"message": "Conversation deleted", "conversation_id": conversation_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG
    )
