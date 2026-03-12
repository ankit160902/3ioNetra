import json
import logging
import asyncio
from datetime import datetime
from typing import List, Optional, Dict
from fastapi import APIRouter, HTTPException, Depends, status, Header
from fastapi.responses import StreamingResponse

from config import settings
from models.api_schemas import (
    ConversationalQuery, ConversationalResponse,
    SessionCreateResponse, SessionStateResponse,
    TextQuery, TextResponse, SaveConversationRequest,
    FeedbackRequest,
    ConversationPhaseEnum, SourceReference, FlowMetadata
)
from models.session import SessionState, ConversationPhase
from services.session_manager import get_session_manager
from services.companion_engine import get_companion_engine
from services.context_synthesizer import get_context_synthesizer
from services.safety_validator import get_safety_validator
from services.response_composer import get_response_composer
from services.auth_service import get_conversation_storage, get_auth_service
from models.dharmic_query import QueryType
from routers.auth import get_current_user

# Global pipeline reference that will be set by main.py
rag_pipeline = None

def set_rag_pipeline(pipeline):
    global rag_pipeline
    rag_pipeline = pipeline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])

# ----------------------------------------------------------------------------
# Helper to populate session with auth user and profile data
# ----------------------------------------------------------------------------
async def _populate_session_with_user_context(session: SessionState, user: Optional[dict], user_profile: Optional[any]):
    if user:
        session.memory.user_id = user.get('id')
        session.memory.user_name = user.get('name')
        
        # 🧠 CORE MEMORY INHERITANCE: If this is a fresh session (no memory story yet), 
        # try to inherit the synthesized "story" from the user's latest past session.
        if not session.memory.story.primary_concern and not session.is_returning_user:
            try:
                storage = get_conversation_storage()
                # Get latest session (passing None for conversation_id fetches the latest)
                latest_conv = storage.get_conversation(user["id"], None)
                if latest_conv and latest_conv.get("memory"):
                    from models.memory_context import ConversationMemory
                    snapshot = latest_conv.get("memory")
                    session.memory = ConversationMemory.from_dict(snapshot)
                    session.is_returning_user = True
                    session.memory.is_returning_user = True
                    
                    # 📝 Add a structural reminder to the LLM about where we left off
                    summary = session.memory.get_memory_summary()
                    session.add_message("system", f"RESUMING CONTEXT from previous session: {summary}. This is a new session, but the user is returning. Acknowledge this naturally.")
                    
                    logger.info(f"Inherited persistent memory context from latest session {latest_conv.get('id')} for user {user['id']}")
            except Exception as e:
                logger.error(f"Failed to inherit memory context: {e}")

        # Pre-populate from permanent user record if not already set (fills gaps or updates)
        if not session.memory.story.profession: session.memory.story.profession = user.get('profession', '')
        if not session.memory.story.gender: session.memory.story.gender = user.get('gender', '')
        if not session.memory.story.age_group: session.memory.story.age_group = user.get('age_group', '')
        if not session.memory.story.rashi: session.memory.story.rashi = user.get('rashi', '')
        if not session.memory.story.gotra: session.memory.story.gotra = user.get('gotra', '')
        if not session.memory.story.nakshatra: session.memory.story.nakshatra = user.get('nakshatra', '')
        if not session.memory.story.preferred_deity: session.memory.story.preferred_deity = user.get('preferred_deity', '')
        if not session.memory.story.location: session.memory.story.location = user.get('location', '')
        
    if user_profile:
        # Override with explicit frontend-provided profile if available
        if hasattr(user_profile, 'age_group') and user_profile.age_group: session.memory.story.age_group = user_profile.age_group
        if hasattr(user_profile, 'gender') and user_profile.gender: session.memory.story.gender = user_profile.gender
        if hasattr(user_profile, 'profession') and user_profile.profession: session.memory.story.profession = user_profile.profession
        if hasattr(user_profile, 'preferred_deity') and user_profile.preferred_deity: session.memory.story.preferred_deity = user_profile.preferred_deity
        if hasattr(user_profile, 'location') and user_profile.location: session.memory.story.location = user_profile.location
        if hasattr(user_profile, 'spiritual_interests') and user_profile.spiritual_interests: session.memory.story.spiritual_interests = user_profile.spiritual_interests

# ----------------------------------------------------------------------------
# STANDALONE QUERY ENDPOINTS
# ----------------------------------------------------------------------------

@router.post("/text/query", response_model=TextResponse)
async def text_query(query: TextQuery):
    """Process standalone text query and return response with citations."""
    if not rag_pipeline or not rag_pipeline.available:
        raise HTTPException(status_code=500, detail="RAG pipeline not available")
        
    try:
        result = await rag_pipeline.query(
            query=query.query,
            language=query.language,
            include_citations=query.include_citations,
            conversation_history=query.conversation_history
        )
        return TextResponse(**result)
    except Exception as e:
        logger.error(f"Error in text query: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------------------------------------------------------
# CONVERSATION SESSION ENDPOINTS
# ----------------------------------------------------------------------------

@router.post("/session/create", response_model=SessionCreateResponse)
async def create_session():
    """Create a new conversation session."""
    try:
        session_manager = get_session_manager()
        session = await session_manager.create_session(
            min_signals=settings.MIN_SIGNALS_THRESHOLD,
            min_turns=settings.MIN_CLARIFICATION_TURNS,
            max_turns=settings.MAX_CLARIFICATION_TURNS
        )

        welcome_message = "Namaste. I'm here to listen and understand what you're going through. Please share what's on your mind, and I'll do my best to offer guidance from the wisdom of Sanātana Dharma."

        return SessionCreateResponse(
            session_id=session.session_id,
            phase=ConversationPhaseEnum(session.phase.value),
            message=welcome_message
        )
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/session/{session_id}", response_model=SessionStateResponse)
async def get_session_state(session_id: str):
    """Get current session state."""
    try:
        session_manager = get_session_manager()
        session = await session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
            
        return SessionStateResponse(
            session_id=session.session_id,
            phase=ConversationPhaseEnum(session.phase.value),
            turn_count=session.turn_count,
            signals_collected=session.get_signals_summary(),
            created_at=session.created_at.isoformat()
        )
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session explicitly."""
    session_manager = get_session_manager()
    await session_manager.delete_session(session_id)
    return {"message": "Session deleted"}

# ----------------------------------------------------------------------------
# MAIN CONVERSATIONAL ENDPOINT
# ----------------------------------------------------------------------------

@router.post("/conversation", response_model=ConversationalResponse)
async def conversational_query(query: ConversationalQuery, user: dict = Depends(get_current_user)):
    """Main conversational endpoint with empathetic companion flow."""
    if not rag_pipeline or not rag_pipeline.available:
        raise HTTPException(status_code=500, detail="RAG pipeline not available")

    session_manager = get_session_manager()
    companion_engine = get_companion_engine()
    context_synthesizer = get_context_synthesizer()
    safety_validator = get_safety_validator()
    response_composer = get_response_composer()

    # Get or create session
    if query.session_id:
        session = await session_manager.get_session(query.session_id)
        if session and user and session.memory.user_id and session.memory.user_id != user.get('id'):
            session = None
            
        if not session and user:
            # Try to restore from persistent history if session expired
            storage = get_conversation_storage()
            conv = storage.get_conversation(user["id"], query.session_id)
            if conv:
                logger.info(f"Restoring expired session {query.session_id} from persistent history")
                session = await session_manager.create_session(
                    min_signals=settings.MIN_SIGNALS_THRESHOLD,
                    min_turns=settings.MIN_CLARIFICATION_TURNS,
                    max_turns=settings.MAX_CLARIFICATION_TURNS
                )
                session.session_id = query.session_id # Keep the same ID
                session.conversation_history = conv.get("messages", [])
                session.is_returning_user = True
                memory_snapshot = conv.get("memory")
                await companion_engine.reconstruct_memory(session, session.conversation_history, snapshot=memory_snapshot)
                session.memory.is_returning_user = True
                await session_manager.update_session(session)

        if not session:
            session = await session_manager.create_session(
                min_signals=settings.MIN_SIGNALS_THRESHOLD,
                min_turns=settings.MIN_CLARIFICATION_TURNS,
                max_turns=settings.MAX_CLARIFICATION_TURNS
            )
            # If the frontend provided an ID but it wasn't in DB either, 
            # we still use it to maintain frontend continuity
            if query.session_id:
                session.session_id = query.session_id
    else:
        session = await session_manager.create_session(
            min_signals=settings.MIN_SIGNALS_THRESHOLD,
            min_turns=settings.MIN_CLARIFICATION_TURNS,
            max_turns=settings.MAX_CLARIFICATION_TURNS
        )

    await _populate_session_with_user_context(session, user, query.user_profile)

    # Safety check
    is_crisis, crisis_response = await safety_validator.check_crisis_signals(session, query.message)
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

    session.add_message('user', query.message)
    session.turn_count += 1

    # Skip speculative RAG for trivial messages (greetings, short phrases)
    # — the engine will do its own targeted RAG if/when needed.
    msg_lower = query.message.strip().lower()
    _trivial = {"hi", "hey", "hello", "namaste", "pranam", "ok", "okay",
                "thanks", "thank you", "bye", "hii", "hiii", "yes", "no"}
    skip_speculative_rag = msg_lower in _trivial or len(query.message.split()) < 3

    if skip_speculative_rag:
        engine_result = await companion_engine.process_message(session, query.message)
        speculative_docs = []
    else:
        # Engine + RAG in parallel
        engine_task = companion_engine.process_message(session, query.message)
        rag_task = rag_pipeline.search(query=query.message, language=query.language, top_k=5)
        engine_result, speculative_docs = await asyncio.gather(engine_task, rag_task)

    companion_response, is_ready_for_wisdom, context_docs_used, turn_topics, recommended_products, active_phase = engine_result

    if is_ready_for_wisdom:
        session.phase = ConversationPhase.GUIDANCE
        session.dharmic_query = context_synthesizer.synthesize_from_memory(session)
        dharmic_query = session.dharmic_query

        retrieved_docs = speculative_docs if speculative_docs else []
        if not retrieved_docs and dharmic_query.query_type != QueryType.PANCHANG:
            retrieved_docs = await rag_pipeline.search(
                query=dharmic_query.build_search_query(),
                scripture_filter=dharmic_query.allowed_scriptures,
                language=query.language,
                top_k=5
            )

        reduce_scripture = safety_validator.should_reduce_scripture_density(session)
        response_text = await response_composer.compose_with_memory(
            dharmic_query=dharmic_query,
            memory=session.memory,
            retrieved_verses=retrieved_docs,
            conversation_history=session.conversation_history,
            reduce_scripture=reduce_scripture,
            phase=ConversationPhase.GUIDANCE,
            original_query=query.message,
            user_id=session.memory.user_id,
        )
        response_text = await safety_validator.validate_response(response_text)
        
        # Professional help check
        needs_help, help_type = safety_validator.check_needs_professional_help(session, query.message)
        if needs_help:
            response_text = safety_validator.append_professional_help(response_text, help_type, False)

        session.add_message('assistant', response_text)
        session.memory.readiness_for_wisdom = 0.3
        await session_manager.update_session(session)

        return ConversationalResponse(
            session_id=session.session_id,
            phase=ConversationPhaseEnum.guidance,
            response=response_text,
            signals_collected=session.get_signals_summary(),
            turn_count=session.turn_count,
            is_complete=True,
            recommended_products=recommended_products,
            flow_metadata=FlowMetadata(detected_domain=session.memory.story.life_area, emotional_state=session.memory.story.emotional_state, topics=turn_topics, readiness_score=round(session.memory.readiness_for_wisdom, 2))
        )
    else:
        session.add_message('assistant', companion_response)
        await session_manager.update_session(session)
        return ConversationalResponse(
            session_id=session.session_id, phase=ConversationPhaseEnum.listening, response=companion_response,
            signals_collected=session.get_signals_summary(), turn_count=session.turn_count, is_complete=False,
            recommended_products=recommended_products,
            flow_metadata=FlowMetadata(detected_domain=session.memory.story.life_area, emotional_state=session.memory.story.emotional_state, topics=turn_topics, readiness_score=round(session.memory.readiness_for_wisdom, 2))
        )

# ----------------------------------------------------------------------------
# STREAMING CONVERSATIONAL ENDPOINT (SSE)
# ----------------------------------------------------------------------------

@router.post("/conversation/stream")
async def conversational_query_stream(query: ConversationalQuery, user: dict = Depends(get_current_user)):
    """Streaming conversational endpoint — SSE token-by-token responses."""
    if not rag_pipeline or not rag_pipeline.available:
        raise HTTPException(status_code=500, detail="RAG pipeline not available")

    session_manager = get_session_manager()
    companion_engine = get_companion_engine()
    context_synthesizer = get_context_synthesizer()
    safety_validator = get_safety_validator()
    response_composer = get_response_composer()

    # --- Session get/create (identical to non-streaming endpoint) ---
    if query.session_id:
        session = await session_manager.get_session(query.session_id)
        if session and user and session.memory.user_id and session.memory.user_id != user.get('id'):
            session = None

        if not session and user:
            storage = get_conversation_storage()
            conv = storage.get_conversation(user["id"], query.session_id)
            if conv:
                logger.info(f"Restoring expired session {query.session_id} from persistent history")
                session = await session_manager.create_session(
                    min_signals=settings.MIN_SIGNALS_THRESHOLD,
                    min_turns=settings.MIN_CLARIFICATION_TURNS,
                    max_turns=settings.MAX_CLARIFICATION_TURNS
                )
                session.session_id = query.session_id
                session.conversation_history = conv.get("messages", [])
                session.is_returning_user = True
                memory_snapshot = conv.get("memory")
                await companion_engine.reconstruct_memory(session, session.conversation_history, snapshot=memory_snapshot)
                session.memory.is_returning_user = True
                await session_manager.update_session(session)

        if not session:
            session = await session_manager.create_session(
                min_signals=settings.MIN_SIGNALS_THRESHOLD,
                min_turns=settings.MIN_CLARIFICATION_TURNS,
                max_turns=settings.MAX_CLARIFICATION_TURNS
            )
            if query.session_id:
                session.session_id = query.session_id
    else:
        session = await session_manager.create_session(
            min_signals=settings.MIN_SIGNALS_THRESHOLD,
            min_turns=settings.MIN_CLARIFICATION_TURNS,
            max_turns=settings.MAX_CLARIFICATION_TURNS
        )

    await _populate_session_with_user_context(session, user, query.user_profile)

    async def event_generator():
        yield ": connected\n\n"  # SSE comment — flushes HTTP response immediately
        try:
            # --- Safety check ---
            is_crisis, crisis_response = await safety_validator.check_crisis_signals(session, query.message)
            if is_crisis:
                session.add_message('user', query.message)
                session.add_message('assistant', crisis_response)
                await session_manager.update_session(session)
                yield f"event: metadata\ndata: {json.dumps({'session_id': session.session_id, 'phase': session.phase.value, 'turn_count': session.turn_count, 'signals_collected': session.get_signals_summary()})}\n\n"
                yield f"event: token\ndata: {json.dumps({'text': crisis_response})}\n\n"
                yield f"event: done\ndata: {json.dumps({'full_response': crisis_response, 'recommended_products': [], 'flow_metadata': {'detected_domain': None, 'emotional_state': None, 'topics': [], 'readiness_score': 0}})}\n\n"
                return

            session.add_message('user', query.message)
            session.turn_count += 1

            # --- Speculative RAG (parallel with preamble for non-trivial messages) ---
            msg_lower = query.message.strip().lower()
            _trivial = {"hi", "hey", "hello", "namaste", "pranam", "ok", "okay",
                        "thanks", "thank you", "bye", "hii", "hiii", "yes", "no"}
            skip_speculative_rag = msg_lower in _trivial or len(query.message.split()) < 3

            if skip_speculative_rag:
                meta = await companion_engine.process_message_preamble(session, query.message)
                speculative_docs = []
            else:
                preamble_task = companion_engine.process_message_preamble(session, query.message)
                rag_task = rag_pipeline.search(query=query.message, language=query.language, top_k=5)
                meta, speculative_docs = await asyncio.gather(preamble_task, rag_task)

            is_ready = meta["is_ready_for_wisdom"]
            context_docs = meta["context_docs"]
            turn_topics = meta["turn_topics"]
            recommended_products = meta["recommended_products"]
            active_phase = meta["active_phase"]

            # --- Yield metadata event ---
            yield f"event: metadata\ndata: {json.dumps({'session_id': session.session_id, 'phase': 'guidance' if is_ready else active_phase.value, 'turn_count': session.turn_count, 'signals_collected': session.get_signals_summary()})}\n\n"

            full_text_parts: list[str] = []

            if is_ready:
                # --- Guidance phase: stream via response_composer ---
                session.phase = ConversationPhase.GUIDANCE
                session.dharmic_query = context_synthesizer.synthesize_from_memory(session)
                dharmic_query = session.dharmic_query

                retrieved_docs = speculative_docs if speculative_docs else []
                if not retrieved_docs and dharmic_query.query_type != QueryType.PANCHANG:
                    retrieved_docs = await rag_pipeline.search(
                        query=dharmic_query.build_search_query(),
                        scripture_filter=dharmic_query.allowed_scriptures,
                        language=query.language,
                        top_k=5
                    )

                reduce_scripture = safety_validator.should_reduce_scripture_density(session)

                async for token in response_composer.compose_stream(
                    dharmic_query=dharmic_query,
                    memory=session.memory,
                    retrieved_verses=retrieved_docs,
                    conversation_history=session.conversation_history,
                    reduce_scripture=reduce_scripture,
                    phase=ConversationPhase.GUIDANCE,
                    original_query=query.message,
                    user_id=session.memory.user_id,
                ):
                    full_text_parts.append(token)
                    yield f"event: token\ndata: {json.dumps({'text': token})}\n\n"
            else:
                # --- Listening phase: stream via LLM service ---
                if companion_engine.available:
                    async for token in companion_engine.llm.generate_response_stream(
                        query=query.message,
                        context_docs=meta["context_docs"],
                        conversation_history=session.conversation_history,
                        user_profile=meta["user_profile"],
                        phase=meta["active_phase"],
                        memory_context=session.memory,
                    ):
                        full_text_parts.append(token)
                        yield f"event: token\ndata: {json.dumps({'text': token})}\n\n"
                else:
                    full_text_parts.append("I'm here with you. Could you tell me a little more about what feels most heavy right now?")
                    yield f"event: token\ndata: {json.dumps({'text': full_text})}\n\n"

            # --- Post-processing ---
            from llm.service import clean_response
            full_text = "".join(full_text_parts)
            cleaned_text = await asyncio.to_thread(clean_response, full_text)
            final_text = await safety_validator.validate_response(cleaned_text)

            needs_help, help_type = safety_validator.check_needs_professional_help(session, query.message)
            if needs_help:
                final_text = safety_validator.append_professional_help(final_text, help_type, False)

            session.add_message('assistant', final_text)
            if is_ready:
                session.memory.readiness_for_wisdom = 0.3
            await session_manager.update_session(session)

            flow_meta = {
                "detected_domain": session.memory.story.life_area,
                "emotional_state": session.memory.story.emotional_state,
                "topics": turn_topics,
                "readiness_score": round(session.memory.readiness_for_wisdom, 2),
            }

            yield f"event: done\ndata: {json.dumps({'full_response': final_text, 'recommended_products': recommended_products, 'flow_metadata': flow_meta})}\n\n"

        except Exception as e:
            logger.exception(f"Error in SSE stream: {e}")
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

# ----------------------------------------------------------------------------
# FEEDBACK ENDPOINT
# ----------------------------------------------------------------------------

@router.post("/feedback")
async def submit_feedback(request: FeedbackRequest, user: Optional[dict] = Depends(get_current_user)):
    """Store like/dislike feedback for a specific response."""
    if request.feedback not in ("like", "dislike"):
        raise HTTPException(status_code=400, detail="Feedback must be 'like' or 'dislike'")
    try:
        from services.auth_service import get_mongo_client
        from datetime import datetime
        db = get_mongo_client()
        if db is None:
            raise HTTPException(status_code=500, detail="Database not available")
        import hashlib
        response_hash = hashlib.md5(request.response_text.encode()).hexdigest()
        db.feedback.update_one(
            {
                "session_id": request.session_id,
                "message_index": request.message_index,
                "response_hash": response_hash,
                "user_id": user.get("id") if user else None,
            },
            {"$set": {
                "feedback": request.feedback,
                "updated_at": datetime.utcnow(),
            }, "$setOnInsert": {
                "session_id": request.session_id,
                "message_index": request.message_index,
                "response_text": request.response_text,
                "response_hash": response_hash,
                "user_id": user.get("id") if user else None,
                "created_at": datetime.utcnow(),
            }},
            upsert=True,
        )
        return {"message": "Feedback saved", "feedback": request.feedback}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------------------------------------------------------
# USER HISTORY ENDPOINTS
# ----------------------------------------------------------------------------

@router.get("/user/conversations")
async def get_user_conversations(user: dict = Depends(get_current_user)):
    if not user: raise HTTPException(status_code=401)
    storage = get_conversation_storage()
    return {"conversations": storage.get_conversations_list(user["id"])}

@router.get("/user/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, user: dict = Depends(get_current_user)):
    if not user: raise HTTPException(status_code=401)
    storage = get_conversation_storage()
    conv = storage.get_conversation(user["id"], conversation_id)
    if not conv: raise HTTPException(status_code=404)
    return conv

@router.post("/user/conversations")
async def save_conversation(request: SaveConversationRequest, user: dict = Depends(get_current_user)):
    if not user: raise HTTPException(status_code=401)
    
    # 1. Get memory snapshot if active session exists
    session_manager = get_session_manager()
    session = await session_manager.get_session(request.conversation_id)
    memory_snapshot = None
    if session:
        memory_snapshot = session.memory.to_dict()
        
        # 2. Update global user profile with discovered facts from UserStory
        try:
            auth_service = get_auth_service()
            story = session.memory.story
            profile_updates = {}
            
            # Persist only high-confidence/stable fields
            if story.profession: profile_updates["profession"] = story.profession
            if story.gender: profile_updates["gender"] = story.gender
            if story.rashi: profile_updates["rashi"] = story.rashi
            if story.gotra: profile_updates["gotra"] = story.gotra
            if story.nakshatra: profile_updates["nakshatra"] = story.nakshatra
            if story.preferred_deity: profile_updates["preferred_deity"] = story.preferred_deity
            
            if profile_updates:
                auth_service.update_user_profile(user["id"], profile_updates)
                logger.info(f"Updated global profile for user {user['id']} with {list(profile_updates.keys())}")
        except Exception as e:
            logger.error(f"Failed to update global profile during save: {e}")

    # 3. Save conversation with memory snapshot
    storage = get_conversation_storage()
    conv_id = storage.save_conversation(
        user_id=user["id"], 
        conversation_id=request.conversation_id, 
        title=request.title, 
        messages=request.messages,
        memory=memory_snapshot
    )
    
    return {"message": "Saved", "conversation_id": conv_id}

@router.delete("/user/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, user: dict = Depends(get_current_user)):
    if not user: raise HTTPException(status_code= status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        storage = get_conversation_storage()
        deleted = storage.delete_conversation(user["id"], conversation_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
        return {"message": "Conversation deleted", "conversation_id": conversation_id}
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
