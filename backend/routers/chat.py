import hashlib
import json
import logging
import asyncio
import re
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import StreamingResponse

from config import settings
from models.api_schemas import (
    ConversationalQuery, ConversationalResponse,
    SessionCreateResponse, SessionStateResponse,
    TextQuery, TextResponse, SaveConversationRequest,
    FeedbackRequest,
    ConversationPhaseEnum, FlowMetadata
)
from constants import TRIVIAL_MESSAGES
from models.session import SessionState, ConversationPhase, SignalType
from services.session_manager import get_session_manager
from services.companion_engine import get_companion_engine
from services.context_synthesizer import get_context_synthesizer
from services.safety_validator import get_safety_validator
from services.response_composer import get_response_composer
from services.auth_service import get_conversation_storage, get_auth_service
from models.dharmic_query import QueryType
from routers.auth import get_current_user
from routers.dependencies import get_rag_pipeline
from llm.service import clean_response
from services.retrieval_judge import get_retrieval_judge

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])

# ----------------------------------------------------------------------------
# Helper to populate session with auth user and profile data
# ----------------------------------------------------------------------------
async def _populate_session_with_user_context(session: SessionState, user: Optional[dict], user_profile: Optional[any]):
    if user:
        session.memory.user_id = user.get('id')
        session.user_id = user.get('id')  # B0: Also set session-level user_id for semantic memory
        session.memory.user_name = user.get('name')

        # 🧠 CORE MEMORY INHERITANCE: If this is a fresh session (no memory story yet),
        # try to inherit context from the user's recent past sessions.
        if not session.memory.story.primary_concern and not session.is_returning_user:
            try:
                async def _inherit_memory():
                    storage = get_conversation_storage()
                    recent = await storage.get_recent_conversation_summaries(user["id"], limit=5)
                    if recent:
                        from models.memory_context import ConversationMemory
                        latest = recent[0]
                        if latest.get("memory"):
                            session.memory = ConversationMemory.from_dict(latest["memory"])
                        session.is_returning_user = True
                        session.memory.is_returning_user = True
                        session.memory.user_id = user.get('id')
                        session.memory.user_name = user.get('name')

                        journey_parts = []
                        for conv in recent:
                            conv_summary = conv.get("conversation_summary", "")
                            if not conv_summary and conv.get("memory"):
                                mem = ConversationMemory.from_dict(conv["memory"])
                                conv_summary = mem.get_memory_summary()
                            if conv_summary:
                                date = str(conv.get("updated_at", ""))[:10]
                                journey_parts.append(f"[{date}]: {conv_summary}")

                        session.memory.previous_session_summary = " | ".join(journey_parts[:5])
                        logger.info(f"Inherited journey context from {len(recent)} conversations for user {user['id']}")

                await asyncio.wait_for(_inherit_memory(), timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning(f"Memory inheritance timed out for user {user.get('id')}")
            except Exception as e:
                logger.error(f"Failed to inherit memory context: {e}")

        # Pre-populate from permanent user record if not already set (fills gaps or updates)
        if not session.memory.story.profession:
            session.memory.story.profession = user.get('profession', '')
        if not session.memory.story.gender:
            session.memory.story.gender = user.get('gender', '')
        if not session.memory.story.age_group:
            session.memory.story.age_group = user.get('age_group', '')
        if not session.memory.story.rashi:
            session.memory.story.rashi = user.get('rashi', '')
        if not session.memory.story.gotra:
            session.memory.story.gotra = user.get('gotra', '')
        if not session.memory.story.nakshatra:
            session.memory.story.nakshatra = user.get('nakshatra', '')
        if not session.memory.story.preferred_deity:
            session.memory.story.preferred_deity = user.get('preferred_deity', '')
        if not session.memory.story.location:
            session.memory.story.location = user.get('location', '')
        if not session.memory.story.temple_visits:
            session.memory.story.temple_visits = user.get('temple_visits', [])
        if not session.memory.story.purchase_history:
            session.memory.story.purchase_history = user.get('purchase_history', [])
        
    if user_profile:
        # Override with explicit frontend-provided profile if available
        if hasattr(user_profile, 'age_group') and user_profile.age_group:
            session.memory.story.age_group = user_profile.age_group
        if hasattr(user_profile, 'gender') and user_profile.gender:
            session.memory.story.gender = user_profile.gender
        if hasattr(user_profile, 'profession') and user_profile.profession:
            session.memory.story.profession = user_profile.profession
        if hasattr(user_profile, 'preferred_deity') and user_profile.preferred_deity:
            session.memory.story.preferred_deity = user_profile.preferred_deity
        if hasattr(user_profile, 'location') and user_profile.location:
            session.memory.story.location = user_profile.location
        if hasattr(user_profile, 'spiritual_interests') and user_profile.spiritual_interests:
            session.memory.story.spiritual_interests = user_profile.spiritual_interests
        if hasattr(user_profile, 'rashi') and user_profile.rashi:
            session.memory.story.rashi = user_profile.rashi
        if hasattr(user_profile, 'gotra') and user_profile.gotra:
            session.memory.story.gotra = user_profile.gotra
        if hasattr(user_profile, 'nakshatra') and user_profile.nakshatra:
            session.memory.story.nakshatra = user_profile.nakshatra

async def _get_or_create_session(
    query: ConversationalQuery,
    user: Optional[dict],
    session_manager,
    companion_engine,
) -> SessionState:
    """Resolve or create a session from a ConversationalQuery."""
    if query.session_id:
        session = await session_manager.get_session(query.session_id)
        if session and user and session.memory.user_id and session.memory.user_id != user.get('id'):
            session = None

        if not session and user:
            try:
                async def _restore_session():
                    storage = get_conversation_storage()
                    conv = await storage.get_conversation(user["id"], query.session_id)
                    if conv:
                        logger.info(f"Restoring expired session {query.session_id} from persistent history")
                        s = await session_manager.create_session(
                            min_signals=settings.MIN_SIGNALS_THRESHOLD,
                            min_turns=settings.MIN_CLARIFICATION_TURNS,
                            max_turns=settings.MAX_CLARIFICATION_TURNS
                        )
                        s.session_id = query.session_id
                        s.conversation_history = conv.get("messages", [])
                        s.is_returning_user = True
                        memory_snapshot = conv.get("memory")
                        await companion_engine.reconstruct_memory(s, s.conversation_history, snapshot=memory_snapshot)
                        s.memory.is_returning_user = True
                        await session_manager.update_session(s)
                        return s
                    return None

                restored = await asyncio.wait_for(_restore_session(), timeout=15.0)
                if restored:
                    session = restored
            except asyncio.TimeoutError:
                logger.warning(f"Session restoration timed out for session {query.session_id}")
            except Exception as e:
                logger.error(f"Session restoration failed: {e}")

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
    return session

# ----------------------------------------------------------------------------
# STANDALONE QUERY ENDPOINTS
# ----------------------------------------------------------------------------

@router.post("/text/query", response_model=TextResponse)
async def text_query(query: TextQuery):
    """Process standalone text query and return response with citations."""
    pipeline = get_rag_pipeline()
    if not pipeline or not pipeline.available:
        raise HTTPException(status_code=500, detail="RAG pipeline not available")

    try:
        result = await pipeline.query(
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session explicitly."""
    session_manager = get_session_manager()
    await session_manager.delete_session(session_id)
    return {"message": "Session deleted"}

# ----------------------------------------------------------------------------
# Shared helpers for conversational endpoints
# ----------------------------------------------------------------------------

def _init_services():
    """Return the 5 core services used by both conversation endpoints."""
    return (
        get_session_manager(),
        get_companion_engine(),
        get_context_synthesizer(),
        get_safety_validator(),
        get_response_composer(),
    )


async def _preflight(query, user, session_manager, companion_engine, safety_validator):
    """Session create/restore + user context population + crisis check.

    Returns (session, is_crisis, crisis_response).
    """
    session = await _get_or_create_session(query, user, session_manager, companion_engine)
    # Parallelize: user context population and crisis check are independent
    _, (is_crisis, crisis_response) = await asyncio.gather(
        _populate_session_with_user_context(session, user, query.user_profile),
        safety_validator.check_crisis_signals(session, query.message),
    )
    if is_crisis:
        session.add_message('user', query.message)
        # Populate emotion signal for crisis — IntentAgent is skipped in crisis path
        from models.session import Signal
        session.signals_collected[SignalType.EMOTION] = Signal(signal_type=SignalType.EMOTION, value='despair')
        session.add_message('assistant', crisis_response)
        await session_manager.update_session(session)
    return session, is_crisis, crisis_response


async def _run_speculative_rag(session, query, rag_pipeline, companion_engine, streaming=False):
    """Add user message, increment turn, run engine (which handles RAG internally).

    Returns (engine_result_or_meta, speculative_docs).
    Note: Speculative RAG removed — engine already runs enriched RAG via
    _retrieve_and_validate() for both listening and guidance paths. Running
    a second parallel RAG on the raw message was redundant and added 30-80s
    of CPU-bound latency (embedding + reranking) per request.
    """
    session.add_message('user', query.message)
    session.turn_count += 1

    if streaming:
        engine_result = await companion_engine.process_message_preamble(session, query.message)
    else:
        engine_result = await companion_engine.process_message(session, query.message)

    return engine_result, []


async def _build_guidance_context(session, query, speculative_docs, context_synthesizer, rag_pipeline):
    """Synthesise dharmic query. Uses engine's pre-retrieved docs — no fallback RAG search.

    The engine already ran _retrieve_and_validate() with enriched queries + RetrievalJudge.
    Running a second RAG search here added 15-40s of latency for marginal benefit.
    The LLM generates good responses from memory + conversation history even without docs.

    Returns (dharmic_query, retrieved_docs).
    """
    session.phase = ConversationPhase.GUIDANCE
    session.dharmic_query = context_synthesizer.synthesize_from_memory(session)
    dharmic_query = session.dharmic_query

    retrieved_docs = speculative_docs if speculative_docs else []
    return dharmic_query, retrieved_docs


def _make_flow_metadata(session, turn_topics):
    return FlowMetadata(
        detected_domain=session.memory.story.life_area,
        emotional_state=session.memory.story.emotional_state,
        topics=turn_topics,
        readiness_score=round(session.memory.readiness_for_wisdom, 2),
    )


async def _postprocess_and_save(text, session, query_message, safety_validator, session_manager, companion_engine, is_guidance):
    """Validate, append professional help, save to session. Returns final text."""
    # Context-aware cleanup: when user complains about "just a [thing]", strip the substring
    if 'just a' in query_message.lower():
        text = re.sub(r'\bjust as\b', 'equally', text, flags=re.IGNORECASE)
        text = re.sub(r'\bjust a\b', 'merely a', text, flags=re.IGNORECASE)
    final_text = await safety_validator.validate_response(text)
    needs_help, help_type = safety_validator.check_needs_professional_help(session, query_message)
    if needs_help:
        final_text = safety_validator.append_professional_help(final_text, help_type, False)
    session.add_message('assistant', final_text)
    # Record practice suggestions for future product inference
    companion_engine.record_suggestion(session, final_text)
    if is_guidance:
        session.memory.readiness_for_wisdom = settings.READINESS_POST_GUIDANCE
    def _on_save_done(t):
        try:
            exc = t.exception()
        except asyncio.CancelledError:
            return
        if exc:
            logger.error(f"Background session save failed: {exc}")
    task = asyncio.create_task(session_manager.update_session(session))
    task.add_done_callback(_on_save_done)
    return final_text


# ----------------------------------------------------------------------------
# MAIN CONVERSATIONAL ENDPOINT
# ----------------------------------------------------------------------------

@router.post("/conversation", response_model=ConversationalResponse)
async def conversational_query(query: ConversationalQuery, user: dict = Depends(get_current_user)):
    """Main conversational endpoint with empathetic companion flow."""
    rag_pipeline = get_rag_pipeline()
    if not rag_pipeline or not rag_pipeline.available:
        raise HTTPException(status_code=500, detail="RAG pipeline not available")

    session_manager, companion_engine, context_synthesizer, safety_validator, response_composer = _init_services()

    session, is_crisis, crisis_response = await _preflight(
        query, user, session_manager, companion_engine, safety_validator
    )
    if is_crisis:
        return ConversationalResponse(
            session_id=session.session_id,
            phase=ConversationPhaseEnum(session.phase.value),
            response=crisis_response,
            signals_collected=session.get_signals_summary(),
            turn_count=session.turn_count,
            is_complete=False
        )

    engine_result, speculative_docs = await _run_speculative_rag(
        session, query, rag_pipeline, companion_engine, streaming=False
    )
    companion_response, is_ready_for_wisdom, context_docs_used, turn_topics, recommended_products, active_phase, route_model, route_config, past_memories = engine_result

    if is_ready_for_wisdom:
        # Use engine's already-retrieved + validated docs as primary source
        dharmic_query, retrieved_docs = await _build_guidance_context(
            session, query, context_docs_used, context_synthesizer, rag_pipeline
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
            past_memories=past_memories,
            model_override=route_model,
            config_override=route_config,
        )

        # Grounding verification — regenerate if response cites non-existent sources.
        # Design intent: re-generation intentionally reuses the same retrieved_docs
        # so the LLM is forced to constrain its citations to actually-available sources
        # rather than hallucinating references not present in the corpus.
        judge = get_retrieval_judge()
        if judge.available and settings.GROUNDING_ENABLED and retrieved_docs:
            grounding = await judge.verify_grounding(response_text, retrieved_docs)
            if not grounding.grounded and grounding.confidence < settings.GROUNDING_MIN_CONFIDENCE:
                logger.warning(f"Response not grounded: {grounding.issues}")
                grounding_config = {**(route_config or {}), "grounding_instruction": True}
                response_text = await response_composer.compose_with_memory(
                    dharmic_query=dharmic_query,
                    memory=session.memory,
                    retrieved_verses=retrieved_docs,
                    conversation_history=session.conversation_history,
                    reduce_scripture=reduce_scripture,
                    phase=ConversationPhase.GUIDANCE,
                    original_query=query.message,
                    user_id=session.memory.user_id,
                    past_memories=past_memories,
                    model_override=route_model,
                    config_override=grounding_config,
                )

        response_text = await _postprocess_and_save(
            response_text, session, query.message, safety_validator, session_manager, companion_engine, is_guidance=True
        )

        return ConversationalResponse(
            session_id=session.session_id,
            phase=ConversationPhaseEnum.guidance,
            response=response_text,
            signals_collected=session.get_signals_summary(),
            turn_count=session.turn_count,
            is_complete=True,
            recommended_products=recommended_products,
            flow_metadata=_make_flow_metadata(session, turn_topics),
        )
    else:
        companion_response = (await _postprocess_and_save(
            companion_response, session, query.message, safety_validator, session_manager, companion_engine, is_guidance=False
        ))

        return ConversationalResponse(
            session_id=session.session_id, phase=ConversationPhaseEnum.listening, response=companion_response,
            signals_collected=session.get_signals_summary(), turn_count=session.turn_count, is_complete=False,
            recommended_products=recommended_products,
            flow_metadata=_make_flow_metadata(session, turn_topics),
        )

# ----------------------------------------------------------------------------
# STREAMING CONVERSATIONAL ENDPOINT (SSE)
# ----------------------------------------------------------------------------

@router.post("/conversation/stream")
async def conversational_query_stream(query: ConversationalQuery, user: dict = Depends(get_current_user)):
    """Streaming conversational endpoint — SSE token-by-token responses."""
    rag_pipeline = get_rag_pipeline()
    if not rag_pipeline or not rag_pipeline.available:
        raise HTTPException(status_code=500, detail="RAG pipeline not available")

    session_manager, companion_engine, context_synthesizer, safety_validator, response_composer = _init_services()

    async def event_generator():
        yield ": connected\n\n"  # SSE comment — opens connection immediately

        try:
            session, is_crisis, crisis_response = await _preflight(
                query, user, session_manager, companion_engine, safety_validator
            )

            if is_crisis:
                yield f"event: metadata\ndata: {json.dumps({'session_id': session.session_id, 'phase': session.phase.value, 'turn_count': session.turn_count, 'signals_collected': session.get_signals_summary()})}\n\n"
                yield f"event: token\ndata: {json.dumps({'text': crisis_response})}\n\n"
                yield f"event: done\ndata: {json.dumps({'full_response': crisis_response, 'recommended_products': [], 'flow_metadata': {'detected_domain': None, 'emotional_state': None, 'topics': [], 'readiness_score': 0}})}\n\n"
                return

            # Emit thinking indicator IMMEDIATELY — user sees feedback within ~0.5s
            yield f"event: status\ndata: {json.dumps({'stage': 'thinking', 'message': 'Mitra is thinking...'})}\n\n"

            meta, speculative_docs = await _run_speculative_rag(
                session, query, rag_pipeline, companion_engine, streaming=True
            )

            is_ready = meta["is_ready_for_wisdom"]
            turn_topics = meta["turn_topics"]
            recommended_products = meta["recommended_products"]
            active_phase = meta["active_phase"]

            yield f"event: metadata\ndata: {json.dumps({'session_id': session.session_id, 'phase': 'guidance' if is_ready else active_phase.value, 'turn_count': session.turn_count, 'signals_collected': session.get_signals_summary()})}\n\n"

            full_text_parts: list[str] = []

            if is_ready:
                yield f"event: status\ndata: {json.dumps({'stage': 'searching', 'message': 'Searching scriptures...'})}\n\n"
                # Use engine's already-retrieved + validated docs as primary source
                dharmic_query, retrieved_docs = await _build_guidance_context(
                    session, query, meta.get("context_docs", []), context_synthesizer, rag_pipeline
                )
                reduce_scripture = safety_validator.should_reduce_scripture_density(session)

                yield f"event: status\ndata: {json.dumps({'stage': 'composing', 'message': 'Composing guidance...'})}\n\n"
                async for token in response_composer.compose_stream(
                    dharmic_query=dharmic_query,
                    memory=session.memory,
                    retrieved_verses=retrieved_docs,
                    conversation_history=session.conversation_history,
                    reduce_scripture=reduce_scripture,
                    phase=ConversationPhase.GUIDANCE,
                    original_query=query.message,
                    user_id=session.memory.user_id,
                    past_memories=meta.get("past_memories", []),
                    model_override=meta.get("model_override"),
                    config_override=meta.get("config_override"),
                ):
                    full_text_parts.append(token)
                    yield f"event: token\ndata: {json.dumps({'text': token})}\n\n"
            else:
                yield f"event: status\ndata: {json.dumps({'stage': 'listening', 'message': 'Mitra is listening...'})}\n\n"
                if companion_engine.available:
                    async for token in companion_engine.llm.generate_response_stream(
                        query=query.message,
                        context_docs=meta["context_docs"],
                        conversation_history=session.conversation_history,
                        user_profile=meta["user_profile"],
                        phase=meta["active_phase"],
                        memory_context=session.memory,
                        model_override=meta.get("model_override"),
                        config_override=meta.get("config_override"),
                    ):
                        full_text_parts.append(token)
                        yield f"event: token\ndata: {json.dumps({'text': token})}\n\n"
                else:
                    fallback_text = "I'm here with you. Could you tell me a little more about what feels most heavy right now?"
                    full_text_parts.append(fallback_text)
                    yield f"event: token\ndata: {json.dumps({'text': fallback_text})}\n\n"

            full_text = "".join(full_text_parts)
            cleaned_text = clean_response(full_text)
            final_text = await _postprocess_and_save(
                cleaned_text, session, query.message, safety_validator, session_manager, companion_engine, is_guidance=is_ready
            )

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
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
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
        db = get_mongo_client()
        if db is None:
            raise HTTPException(status_code=500, detail="Database not available")
        response_hash = hashlib.sha256(request.response_text.encode()).hexdigest()
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
    if not user:
        raise HTTPException(status_code=401)
    storage = get_conversation_storage()
    return {"conversations": await storage.get_conversations_list(user["id"])}

@router.get("/user/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, user: dict = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    storage = get_conversation_storage()
    conv = await storage.get_conversation(user["id"], conversation_id)
    if not conv:
        raise HTTPException(status_code=404)
    return conv

@router.post("/user/conversations")
async def save_conversation(request: SaveConversationRequest, user: dict = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401)
    
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
            if story.profession:
                profile_updates["profession"] = story.profession
            if story.gender:
                profile_updates["gender"] = story.gender
            if story.rashi:
                profile_updates["rashi"] = story.rashi
            if story.gotra:
                profile_updates["gotra"] = story.gotra
            if story.nakshatra:
                profile_updates["nakshatra"] = story.nakshatra
            if story.preferred_deity:
                profile_updates["preferred_deity"] = story.preferred_deity
            
            if profile_updates:
                auth_service.update_user_profile(user["id"], profile_updates)
                logger.info(f"Updated global profile for user {user['id']} with {list(profile_updates.keys())}")
        except Exception as e:
            logger.error(f"Failed to update global profile during save: {e}")

    # 3. Save conversation with memory snapshot
    storage = get_conversation_storage()
    conv_id = await storage.save_conversation(
        user_id=user["id"],
        conversation_id=request.conversation_id,
        title=request.title,
        messages=request.messages,
        memory=memory_snapshot
    )

    # 4. Generate and store a concise conversation summary (async, non-blocking)
    async def _generate_and_store_summary(conversation_id, messages, memory_snap, uid):
        try:
            from llm.service import get_llm_service
            llm = get_llm_service()
            if not llm or not llm.available:
                return
            from models.memory_context import ConversationMemory
            mem = ConversationMemory.from_dict(memory_snap) if memory_snap else None
            base_summary = mem.get_memory_summary() if mem else ""
            summary_prompt = f"""Summarize this conversation in 1-2 sentences (under 50 words). Include: main concern, emotional state, key guidance given.
Context: {base_summary}
Last 6 messages: {json.dumps(messages[-6:], ensure_ascii=False)[:800]}
Summary:"""
            summary = await llm.generate_quick_response(summary_prompt)
            if summary:
                s = get_conversation_storage()
                await s.update_conversation_field(uid, conversation_id, "conversation_summary", summary.strip()[:300])
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")

    asyncio.create_task(_generate_and_store_summary(request.conversation_id, request.messages, memory_snapshot, user["id"]))

    return {"message": "Saved", "conversation_id": conv_id}

@router.delete("/user/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, user: dict = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        storage = get_conversation_storage()
        deleted = await storage.delete_conversation(user["id"], conversation_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
        return {"message": "Conversation deleted", "conversation_id": conversation_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
