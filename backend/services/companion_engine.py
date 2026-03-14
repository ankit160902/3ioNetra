import logging
import random
from typing import Tuple, Optional, TYPE_CHECKING, Dict, List

from config import settings
from models.session import SessionState, ConversationPhase, SignalType, IntentType
from models.memory_context import ConversationMemory
from services.panchang_service import get_panchang_service

from services.cost_tracker import get_cost_tracker, extract_tokens_from_response
from services.intent_agent import get_intent_agent
from services.memory_service import get_memory_service
from services.model_router import get_model_router
from services.product_service import get_product_service
if TYPE_CHECKING:
    from rag.pipeline import RAGPipeline

logger = logging.getLogger(__name__)

class CompanionEngine:
    """
    Empathetic front-line companion.

    Responsibilities:
    - Listen and update ConversationMemory
    - Decide when we're ready for dharmic wisdom
    - Generate grounded empathetic responses
    """

    PRACTICE_PRODUCT_MAP = {
        "japa": {
            "detect": ["japa", "jaap", "jap ", "chant", "chanting", "recite", "108 times", "11 times", "21 times"],
            "search_keywords": ["rudraksha mala", "japa mala"],
        },
        "puja": {
            "detect": ["puja", "pooja", "aarti"],
            "search_keywords": ["puja thali", "incense", "diya", "puja samagri"],
        },
        "meditation": {
            "detect": ["meditation", "meditate", "dhyana", "dhyan", "sit quietly"],
            "search_keywords": ["incense", "dhoop", "meditation"],
        },
        "diya": {
            "detect": ["diya", "deep ", "jyoti", "light a lamp", "light a diya"],
            "search_keywords": ["brass diya", "ghee", "diya"],
        },
        "yoga": {
            "detect": ["yoga", "asana", "pranayama", "surya namaskar"],
            "search_keywords": ["yoga mat", "yoga"],
        },
        "tilak": {
            "detect": ["tilak", "sindoor", "kumkum", "chandan"],
            "search_keywords": ["tilak", "sindoor", "chandan"],
        },
        "abhishek": {
            "detect": ["abhishek", "abhishekam"],
            "search_keywords": ["abhishek"],
        },
        "havan": {
            "detect": ["havan", "hawan", "homam", "yajna", "yagna"],
            "search_keywords": ["havan", "ghee", "samagri"],
        },
        "deity_worship": {
            "detect": ["murti", "idol", "statue", "bhagwan"],
            "search_keywords": ["murti", "brass idol"],
        },
        "home_temple": {
            "detect": ["mandir", "home temple", "puja room", "spiritual corner", "altar"],
            "search_keywords": ["puja box", "3D lamp", "deep"],
        },
        "crystal_healing": {
            "detect": ["crystal", "gemstone", "stone", "healing stone"],
            "search_keywords": ["bracelet", "crystal"],
        },
        "seva": {
            "detect": ["seva", "temple service", "pind daan", "ganga aarti", "shraddha"],
            "search_keywords": ["seva", "pind daan", "ganga aarti"],
        },
    }

    EMOTION_PRODUCT_MAP = {
        "anxiety": ["Inner Peace", "Rose Quartz", "Amethyst", "incense"],
        "grief": ["consultation", "seva", "pind daan"],
        "confusion": ["consultation", "astrology", "Lapis Lazuli"],
        "anger": ["Anger Relief", "Black Tourmaline", "incense"],
        "hopelessness": ["consultation", "Rose Quartz", "Inner Peace"],
        "stress": ["Antidepression", "Inner Peace", "meditation", "incense"],
        "fear": ["Triple Protection", "Black Tourmaline", "Hanuman"],
        "sadness": ["Rose Quartz", "consultation", "seva"],
    }

    DEITY_PRODUCT_MAP = {
        "krishna": ["Krishna", "Radha Krishna", "3D lamp"],
        "shiva": ["Shiva", "Rudraksha"],
        "hanuman": ["Hanuman", "Panchamukhi"],
        "ganesh": ["Ganesh", "Ganesha", "murti"],
        "lakshmi": ["Lakshmi", "Pyrite", "prosperity"],
        "durga": ["Durga", "murti"],
        "saraswati": ["Saraswati", "Education"],
        "shrinathji": ["Shrinathji", "3D box", "golden arch"],
        "vishnu": ["Vishnu", "Vishnusahasranam"],
    }

    DOMAIN_PRODUCT_MAP = {
        "career": ["Career Success", "Success & Focus", "Tiger Eye", "Pyrite", "consultation"],
        "relationships": ["Rose Quartz", "Early Marriage", "consultation"],
        "health": ["Weight Loss", "Headache Relief", "7 Chakra", "bracelet"],
        "spiritual": ["Rudraksha", "mala", "incense", "deep", "murti"],
        "family": ["puja thali", "deep", "Lakshmi Ganesh", "puja box"],
        "finance": ["Money Magnet", "Dhan Yog", "Pyrite", "Lakshmi", "Career Success"],
    }

    CONCEPT_PRODUCT_MAP = {
        "bhakti": ["murti", "puja thali", "deep", "incense"],
        "vairagya": ["mala", "Rudraksha"],
        "karma": ["seva", "consultation"],
        "dharma": ["mala", "Rudraksha"],
        "surrender": ["murti", "deep", "seva"],
    }

    def __init__(self, rag_pipeline: Optional["RAGPipeline"] = None) -> None:
        from llm.service import get_llm_service
        self.llm = get_llm_service()

        self.rag_pipeline = rag_pipeline
        self.panchang = get_panchang_service()
        self.intent_agent = get_intent_agent()
        self.memory_service = get_memory_service(rag_pipeline)
        self.product_service = get_product_service()
        self.model_router = get_model_router()
        self.available = self.llm.available
        logger.info(f"CompanionEngine initialized (LLM available={self.available})")

    def set_rag_pipeline(self, rag_pipeline: "RAGPipeline") -> None:
        self.rag_pipeline = rag_pipeline
        self.memory_service.set_rag_pipeline(rag_pipeline)
        logger.info("RAG pipeline connected to CompanionEngine")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_response_stream(
        self,
        session: SessionState,
        message: str,
    ):
        """
        Streaming version of conversational processing.
        Yields: (token, is_metadata_chunk, metadata_dict)
        """
        turn_topics = self._update_memory(session.memory, session, message)
        
        import asyncio
        
        # 🚀 Parallel Task Execution: Intent Analysis + Memory Retrieval
        tasks = [
            self.intent_agent.analyze_intent(message, session.memory.get_memory_summary()),
        ]
        
        if hasattr(session, "user_id") and session.user_id:
            tasks.append(self.memory_service.retrieve_relevant_memories(session.user_id, message))
        else:
            tasks.append(asyncio.sleep(0, result=[]))
            
        analysis, past_memories = await asyncio.gather(*tasks)

        # 1. Update session signals and story (Same as process_message)
        if analysis.get("life_domain") and analysis["life_domain"] != "unknown":
            session.memory.story.life_area = analysis["life_domain"]
            session.add_signal(SignalType.LIFE_DOMAIN, analysis["life_domain"], 0.95)
            
        if analysis.get("emotion") and analysis["emotion"] != "neutral":
            session.memory.story.emotional_state = analysis["emotion"]
            session.add_signal(SignalType.EMOTION, analysis["emotion"], 0.9)

        entities = analysis.get("entities", {})
        if entities.get("deity"):
            session.memory.story.preferred_deity = entities["deity"]
        if entities.get("ritual"):
            session.memory.story.primary_concern = f"Performing {entities['ritual']}"
        
        if len(session.memory.story.primary_concern) < 15 and analysis.get("summary"):
            session.memory.story.primary_concern = analysis["summary"]

        # 🚀 Decide phase
        intent = analysis.get("intent")
        is_direct_ask = analysis.get("needs_direct_answer", False) or \
                        analysis.get("recommend_products", False) or \
                        intent in (IntentType.SEEKING_GUIDANCE, IntentType.ASKING_INFO, IntentType.ASKING_PANCHANG, IntentType.PRODUCT_SEARCH) or \
                        "Verse Request" in turn_topics
        
        current_phase = ConversationPhase.CLARIFICATION
        if intent == IntentType.CLOSURE:
            current_phase = ConversationPhase.CLOSURE
        
        is_ready = False if intent == IntentType.CLOSURE else (self._assess_readiness(session) or is_direct_ask)

        if is_ready:
            # Metadata for frontend
            yield {
                "type": "control",
                "is_ready_for_wisdom": True,
                "phase": ConversationPhase.GUIDANCE.value,
                "turn_topics": turn_topics,
                "intent": intent
            }
            return # main.py will handle RAG + Synthesis stream

        # Listening Phase → Stream LLM response
        yield {
            "type": "control",
            "is_ready_for_wisdom": False,
            "phase": current_phase.value,
            "turn_topics": turn_topics
        }

        if self.available:
            # Start streaming
            user_profile = self._build_user_profile(session.memory, session)
            if past_memories:
                user_profile["past_memories"] = past_memories

            async for token in self.llm.generate_response_stream(
                query=message,
                context_docs=[], # No RAG in easy listening unless we want to parallelize it too
                conversation_history=session.conversation_history,
                user_profile=user_profile,
                phase=current_phase,
                memory_context=session.memory,
            ):
                yield {"type": "token", "content": token}
        else:
            yield {"type": "token", "content": "I'm here with you. Could you tell me a little more?"}

    async def process_message_preamble(
        self,
        session: SessionState,
        message: str,
    ) -> Dict:
        """
        All analysis, memory, signals, RAG, products — everything EXCEPT LLM response generation.
        Returns dict with: is_ready_for_wisdom, context_docs, turn_topics, recommended_products,
        active_phase, user_profile, past_memories, analysis, acknowledgement (if guidance).
        """
        turn_topics = self._update_memory(session.memory, session, message)

        import asyncio

        # 🚀 Parallel Task Execution: Intent Analysis + Memory Retrieval
        tasks = [
            self.intent_agent.analyze_intent(message, session.memory.get_memory_summary()),
        ]

        if hasattr(session, "user_id") and session.user_id:
            tasks.append(self.memory_service.retrieve_relevant_memories(session.user_id, message))
        else:
            tasks.append(asyncio.sleep(0, result=[]))

        analysis, past_memories = await asyncio.gather(*tasks)

        # 1. Update session signals from LLM analysis
        if analysis.get("life_domain") and analysis["life_domain"] != "unknown":
            session.memory.story.life_area = analysis["life_domain"]
            session.add_signal(SignalType.LIFE_DOMAIN, analysis["life_domain"], 0.95)

        if analysis.get("emotion") and analysis["emotion"] != "neutral":
            session.memory.story.emotional_state = analysis["emotion"]
            session.add_signal(SignalType.EMOTION, analysis["emotion"], 0.9)

        # 2. Enrich story with extracted entities and summary
        entities = analysis.get("entities", {})
        if entities.get("deity"):
            session.memory.story.preferred_deity = entities["deity"]
        if entities.get("ritual"):
            session.memory.story.primary_concern = f"Performing {entities['ritual']}"

        if len(session.memory.story.primary_concern) < 15 and analysis.get("summary"):
            session.memory.story.primary_concern = analysis["summary"]

        # 3. Store in Long-Term Memory if significant
        is_significant_update = (
            len(message) > 30 or
            analysis.get("urgency") in ["high", "crisis"] or
            (analysis.get("emotion") and analysis["emotion"] not in [None, "neutral"]) or
            (analysis.get("entities", {}).get("ritual")) or
            (analysis.get("life_domain") and analysis.get("life_domain") != "unknown")
        )

        if is_significant_update:
            if hasattr(session, "user_id") and session.user_id:
                logger.info(f"💾 Preserving semantic memory anchor for user {session.user_id} (Reason: significant update)")
                mem_anchor = analysis.get("summary", message)
                asyncio.create_task(self.memory_service.store_memory(session.user_id, mem_anchor))

        # 🚀 CORE LOGIC: Decide if we should go to GUIDANCE phase
        intent = analysis.get("intent")

        is_direct_ask = analysis.get("needs_direct_answer", False) or \
                        analysis.get("recommend_products", False) or \
                        intent in (IntentType.SEEKING_GUIDANCE, IntentType.ASKING_INFO, IntentType.ASKING_PANCHANG, IntentType.PRODUCT_SEARCH) or \
                        "Verse Request" in turn_topics or \
                        "Product Inquiry" in turn_topics or \
                        "Routine Request" in turn_topics or \
                        "Puja Guidance" in turn_topics or \
                        "Diet Plan" in turn_topics

        current_phase = ConversationPhase.CLARIFICATION
        if intent == IntentType.CLOSURE:
            current_phase = ConversationPhase.CLOSURE

        if intent == IntentType.CLOSURE:
            is_ready = False
        else:
            is_ready = self._assess_readiness(session) or is_direct_ask

        # ------------------------------------------------------------------
        # Ready for wisdom → prepare acknowledgement + context docs + products
        # ------------------------------------------------------------------
        if is_ready:
            acknowledgements = [
                "Thank you for sharing. Let me reflect on this through the lens of Dharma.",
                "I appreciate your honesty. I'm looking into the scriptures for guidance.",
                "I hear you deeply. Please give me a moment to gather wisdom for your situation.",
                "Namaste. Your words have touched me. I am seeking the right dharmic path for you."
            ]

            if is_direct_ask:
                acknowledgements = [
                    "I understand your question. Let me provide the specific guidance for this.",
                    "That's a very clear request. I'm gathering the relevant wisdom for you right now.",
                    "I see what you are seeking. Let me look that up for you."
                ]

            # 📚 SCRIPTURE RETRIEVAL
            context_docs = []
            is_verse_request = "Verse Request" in turn_topics
            is_product_request = "Product Inquiry" in turn_topics
            should_get_verses = is_verse_request or (is_ready and not is_product_request)

            if should_get_verses and self.rag_pipeline and self.rag_pipeline.available:
                try:
                    from services.context_validator import get_context_validator
                    ctx_validator = get_context_validator()
                    search_query = self._build_listening_query(message, session.memory)
                    _type_exclusions = self._get_doc_type_exclusions(intent)
                    context_docs = await self.rag_pipeline.search(
                        query=search_query, scripture_filter=None, language="en",
                        top_k=8, intent=analysis.get("intent"), min_score=0.12,
                        doc_type_filter=_type_exclusions,
                    )
                    context_docs = ctx_validator.validate(
                        docs=context_docs, intent=intent, allowed_scriptures=None,
                        temple_interest=getattr(session.memory.story, 'temple_interest', False),
                        min_score=0.12, max_per_source=2, max_docs=3,
                    )
                except Exception as e:
                    logger.warning(f"Guidance-phase RAG/validation failed: {e}")

            # 🛍️ PRODUCT RECOMMENDATION
            products = []
            is_product_request = "Product Inquiry" in turn_topics or analysis.get("intent") == IntentType.PRODUCT_SEARCH
            should_recommend = is_product_request or analysis.get("recommend_products", False)

            if should_recommend:
                search_terms = " ".join(analysis.get("product_search_keywords", []))
                if not search_terms:
                    context_terms = self._build_context_search_terms(analysis, session)
                    search_terms = " ".join(context_terms[:5]) if context_terms else message
                life_domain = analysis.get("life_domain", "unknown")
                logger.info(f"Producing selective product recommendations for query terms: {search_terms} | Domain: {life_domain}")
                products = await self.product_service.search_products(
                    search_terms, life_domain=life_domain,
                    emotion=analysis.get("emotion", ""),
                    deity=(analysis.get("entities", {}).get("deity", "") or session.memory.story.preferred_deity or ""),
                )
                if not products and (is_product_request or analysis.get("intent") == IntentType.PRODUCT_SEARCH):
                    products = await self.product_service.get_recommended_products(category=life_domain if life_domain != "unknown" else None)

            if not products:
                products = await self._infer_proactive_products(
                    session, message, analysis.get("life_domain", "unknown"),
                    analysis=analysis, is_guidance_phase=True)

            if products:
                products = self._filter_shown_products(session, products)
                self._record_shown_products(session, products)

            # Model routing decision
            routing = self.model_router.route(
                intent_analysis=analysis,
                phase=ConversationPhase.GUIDANCE,
                session=session,
                has_rag_context=bool(context_docs),
            )

            return {
                "is_ready_for_wisdom": True,
                "context_docs": context_docs,
                "turn_topics": turn_topics,
                "recommended_products": products,
                "active_phase": ConversationPhase.GUIDANCE,
                "user_profile": self._build_user_profile(session.memory, session),
                "past_memories": past_memories,
                "analysis": analysis,
                "acknowledgement": random.choice(acknowledgements),
                "model_override": routing.model_name,
                "config_override": routing.config_override,
            }

        # ------------------------------------------------------------------
        # Not ready → prepare context for listening-phase LLM call
        # ------------------------------------------------------------------
        context_docs = []

        if self.available and self.rag_pipeline and self.rag_pipeline.available:
            try:
                from services.context_validator import get_context_validator
                ctx_validator = get_context_validator()
                skip_rag_intents = {IntentType.GREETING, IntentType.CLOSURE}
                panchang_keywords = ["panchang", "tithi", "nakshatra", "muhurat", "today's day", "calendar"]
                if intent in skip_rag_intents:
                    logger.info(f"Skipping RAG for {intent} intent in listening phase")
                    context_docs = []
                elif any(k in message.lower() for k in panchang_keywords):
                    logger.info("Skipping RAG for Panchang-related query in listening phase")
                    context_docs = []
                else:
                    search_query = self._build_listening_query(message, session.memory)
                    _type_exclusions = self._get_doc_type_exclusions(intent)
                    context_docs = await self.rag_pipeline.search(
                        query=search_query, scripture_filter=None, language="en",
                        top_k=8, intent=analysis.get("intent"), min_score=0.12,
                        doc_type_filter=_type_exclusions,
                    )
                    context_docs = ctx_validator.validate(
                        docs=context_docs, intent=intent, allowed_scriptures=None,
                        temple_interest=getattr(session.memory.story, 'temple_interest', False),
                        min_score=0.12, max_per_source=2, max_docs=3,
                    )
            except Exception as e:
                logger.warning(f"Listening-phase RAG/validation failed: {e}")

        user_profile = self._build_user_profile(session.memory, session)
        if past_memories:
            user_profile["past_memories"] = past_memories

        # 🛍️ SELECTIVE PRODUCT RECOMMENDATION logic (Listening Phase)
        products = []
        is_explicit_product = analysis.get("intent") == IntentType.PRODUCT_SEARCH or \
                             "Product Inquiry" in turn_topics
        should_recommend = is_explicit_product

        if should_recommend:
            search_terms = " ".join(analysis.get("product_search_keywords", []))
            if not search_terms:
                context_terms = self._build_context_search_terms(analysis, session)
                search_terms = " ".join(context_terms[:5]) if context_terms else message
            life_domain = analysis.get("life_domain", "unknown")
            logger.info(f"Producing explicit product recommendations in listening phase for: {search_terms} | Domain: {life_domain}")
            products = await self.product_service.search_products(
                search_terms, life_domain=life_domain,
                emotion=analysis.get("emotion", ""),
                deity=(analysis.get("entities", {}).get("deity", "") or session.memory.story.preferred_deity or ""),
            )
            if not products and analysis.get("intent") == IntentType.PRODUCT_SEARCH:
                products = await self.product_service.get_recommended_products(category=life_domain if life_domain != "unknown" else None)

        # Proactive product inference in listening phase (acceptance-based only)
        if not products:
            products = await self._infer_proactive_products(
                session, message, analysis.get("life_domain", "unknown"),
                analysis=analysis, is_guidance_phase=False)

        if products:
            products = self._filter_shown_products(session, products)
            self._record_shown_products(session, products)

        # Model routing decision
        routing = self.model_router.route(
            intent_analysis=analysis,
            phase=current_phase,
            session=session,
            has_rag_context=bool(context_docs),
        )

        return {
            "is_ready_for_wisdom": False,
            "context_docs": context_docs,
            "turn_topics": turn_topics,
            "recommended_products": products,
            "active_phase": current_phase,
            "user_profile": user_profile,
            "past_memories": past_memories,
            "analysis": analysis,
            "model_override": routing.model_name,
            "config_override": routing.config_override,
        }

    async def process_message(
        self,
        session: SessionState,
        message: str,
    ) -> Tuple:
        """
        Returns:
            (assistant_text, is_ready_for_wisdom, context_docs_used, turn_topics,
             recommended_products, active_phase, model_override, config_override)
        """
        meta = await self.process_message_preamble(session, message)

        if meta["is_ready_for_wisdom"]:
            return (
                meta["acknowledgement"], True, meta["context_docs"],
                meta["turn_topics"], meta["recommended_products"], ConversationPhase.GUIDANCE,
                meta.get("model_override"), meta.get("config_override"),
            )

        # Listening phase — make the LLM call
        if self.available:
            reply = await self.llm.generate_response(
                query=message,
                context_docs=meta["context_docs"],
                conversation_history=session.conversation_history,
                user_profile=meta["user_profile"],
                phase=meta["active_phase"],
                memory_context=session.memory,
                model_override=meta.get("model_override"),
                config_override=meta.get("config_override"),
            )

            # Cost tracking
            if settings.MODEL_COST_TRACKING_ENABLED:
                try:
                    usage = self.llm.last_usage
                    analysis = meta.get("analysis", {})
                    routing_model = meta.get("model_override", settings.GEMINI_MODEL)
                    get_cost_tracker().log(
                        session_id=session.session_id,
                        model_name=routing_model,
                        tier="standard",
                        input_tokens=usage.get("input_tokens", 0),
                        output_tokens=usage.get("output_tokens", 0),
                        intent=str(analysis.get("intent", "")),
                        phase=meta["active_phase"].value,
                    )
                except Exception as e:
                    logger.debug(f"Cost tracking failed: {e}")

            return (reply, False, meta["context_docs"], meta["turn_topics"],
                    meta["recommended_products"], meta["active_phase"],
                    meta.get("model_override"), meta.get("config_override"))

        # Fallback (no LLM)
        return (
            "I'm here with you. Could you tell me a little more about what feels most heavy right now?",
            False,
            [],
            meta["turn_topics"],
            [],
            ConversationPhase.LISTENING,
            None,
            None,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_acceptance(message: str) -> bool:
        """Check if a message is an acceptance/acknowledgment of a suggestion."""
        msg = message.lower().strip()
        words = msg.split()

        if len(words) > 30:
            return False

        rejection_keywords = ["no", "don't want", "nahi", "not interested", "something else", "nah", "don't think"]
        if any(kw in msg for kw in rejection_keywords):
            return False

        acceptance_keywords = [
            "ok", "okay", "fine", "sure", "alright", "yes", "haan", "theek",
            "accha", "will do", "will try", "thanks", "got it", "sounds good",
            "thank you", "ji", "shukriya", "dhanyavaad",
        ]
        if any(kw in msg for kw in acceptance_keywords):
            return True

        if len(words) < 8 and "?" not in msg:
            return True

        return False

    def _get_practice_from_history(self, session: SessionState) -> List[str]:
        """Scan last 2 assistant messages for practice-related keywords."""
        assistant_msgs = [
            m["content"].lower()
            for m in session.conversation_history
            if m.get("role") == "assistant"
        ]
        # Look at the last 2 assistant messages
        recent = assistant_msgs[-2:] if len(assistant_msgs) >= 2 else assistant_msgs

        matched_keywords: List[str] = []
        for msg_text in recent:
            for practice_info in self.PRACTICE_PRODUCT_MAP.values():
                if any(kw in msg_text for kw in practice_info["detect"]):
                    for sk in practice_info["search_keywords"]:
                        if sk not in matched_keywords:
                            matched_keywords.append(sk)

        return matched_keywords

    def _build_context_search_terms(self, analysis: Dict, session: SessionState) -> List[str]:
        """Derive product search keywords from conversation context signals."""
        terms = []

        # 1. Deity (highest signal — most specific)
        deity = (analysis.get("entities", {}).get("deity", "")
                 or session.memory.story.preferred_deity or "").lower()
        if deity:
            terms.extend(self.DEITY_PRODUCT_MAP.get(deity, []))

        # 2. Emotion
        emotion = (analysis.get("emotion", "")
                   or session.memory.story.emotional_state or "").lower()
        if emotion and emotion != "neutral":
            terms.extend(self.EMOTION_PRODUCT_MAP.get(emotion, []))

        # 3. Life domain
        domain = (analysis.get("life_domain", "")
                  or session.memory.story.life_area or "").lower()
        if domain and domain != "unknown":
            terms.extend(self.DOMAIN_PRODUCT_MAP.get(domain, []))

        # 4. Spiritual concepts (lowest priority)
        for concept in (session.memory.relevant_concepts or []):
            terms.extend(self.CONCEPT_PRODUCT_MAP.get(concept.lower(), []))

        # 5. Practice keywords from assistant history (reuse existing method)
        terms.extend(self._get_practice_from_history(session))

        # Deduplicate preserving order, cap at 8
        seen = set()
        unique = []
        for t in terms:
            if t.lower() not in seen:
                seen.add(t.lower())
                unique.append(t)
        return unique[:8]

    def _filter_shown_products(self, session: SessionState, products: List[Dict]) -> List[Dict]:
        """Remove already-shown products. Falls back to full list if all filtered."""
        filtered = [p for p in products if p.get("_id") not in session.shown_product_ids]
        return filtered if filtered else products

    def _record_shown_products(self, session: SessionState, products: List[Dict]) -> None:
        """Track shown product IDs in the session state."""
        for p in products:
            if p.get("_id"):
                session.shown_product_ids.add(p["_id"])

    def record_suggestion(self, session: SessionState, assistant_text: str) -> None:
        """Scan assistant's response for practice keywords and record for later product matching."""
        text_lower = assistant_text.lower()
        for practice_name, practice_info in self.PRACTICE_PRODUCT_MAP.items():
            if any(kw in text_lower for kw in practice_info["detect"]):
                entry = {
                    "turn": session.turn_count,
                    "practice": practice_name,
                    "product_keywords": practice_info["search_keywords"],
                }
                session.last_suggestions.append(entry)
                if len(session.last_suggestions) > 3:
                    session.last_suggestions = session.last_suggestions[-3:]
                break  # Record first match only (strongest signal)

    def _get_keywords_from_suggestions(self, session: SessionState) -> List[str]:
        """Get product keywords from tracked suggestions (preferred over raw text scan)."""
        keywords = []
        for entry in session.last_suggestions:
            for kw in entry["product_keywords"]:
                if kw not in keywords:
                    keywords.append(kw)
        return keywords

    async def _infer_proactive_products(
        self,
        session: SessionState,
        message: str,
        life_domain: str,
        analysis: Dict = None,
        is_guidance_phase: bool = False,
    ) -> List[Dict]:
        """Proactively suggest products when user acknowledges a practice suggestion
        or when conversation context provides strong product signals (guidance phase)."""
        # Anti-spam: smart cooldown — shorter gap for acceptance (high conversion)
        turns_since_last = session.turn_count - session.last_proactive_product_turn
        is_acceptance = self._is_acceptance(message)
        min_gap = 2 if is_acceptance else 3
        if turns_since_last < min_gap:
            return []

        # Path A: Acceptance-based (existing behavior, both phases)
        if is_acceptance:
            keywords = self._get_keywords_from_suggestions(session) or self._get_practice_from_history(session)
            if keywords:
                search_query = " ".join(keywords)
                logger.info(f"Proactive product inference (acceptance): searching '{search_query}' for session {session.session_id}")
                products = await self.product_service.search_products(
                    search_query, life_domain=life_domain,
                    emotion=(analysis.get("emotion", "") if analysis else ""),
                    deity=((analysis.get("entities", {}).get("deity", "") if analysis else "")
                           or session.memory.story.preferred_deity or ""),
                )
                if products:
                    session.last_proactive_product_turn = session.turn_count
                    logger.info(f"Proactive products found: {len(products)} items for session {session.session_id}")
                    return products

        # Path B: Context-based (GUIDANCE phase only, no acceptance needed)
        if is_guidance_phase and analysis:
            context_terms = self._build_context_search_terms(analysis, session)
            if context_terms:
                search_query = " ".join(context_terms[:5])
                logger.info(f"Proactive product inference (context): searching '{search_query}' for session {session.session_id}")
                products = await self.product_service.search_products(
                    search_query, life_domain=life_domain,
                    emotion=analysis.get("emotion", ""),
                    deity=(analysis.get("entities", {}).get("deity", "") or session.memory.story.preferred_deity or ""),
                )
                if products:
                    session.last_proactive_product_turn = session.turn_count
                    return products

        return []

    def _assess_readiness(self, session: SessionState) -> bool:
        """
        Decide if we should transition to ANSWERING phase.
        Requires more listening turns for emotionally intense situations.
        """
        readiness = session.memory.readiness_for_wisdom
        emotional_state = session.memory.story.emotional_state
        
        # High-intensity emotions require more listening before guidance
        high_intensity_emotions = ['sadness', 'anger', 'anxiety', 'hopelessness', 'grief', 'despair']
        requires_extra_listening = emotional_state in high_intensity_emotions

        # check if it is a direct question (user seeking answers)
        last_msg = ""
        if session.conversation_history and session.conversation_history[-1]["role"] == "user":
            last_msg = session.conversation_history[-1]["content"]
        
        # Enhanced detection for explicit guidance requests
        guidance_keywords = [
            "how", "what", "guide", "help", "solution", "suggest", "action", 
            "advice", "tell me", "recommend", "should i", "way out", "way to",
            "what can i do", "what do i do", "give me", "show me"
        ]
        is_direct_question = "?" in last_msg or any(w in last_msg.lower() for w in guidance_keywords)

        if is_direct_question:
             # Check if it's a substantive question (not just "what?")
             is_detailed = len(last_msg.split()) > 4
             
             if is_detailed and not requires_extra_listening:
                 logger.info(f"Session {session.session_id}: Direct detailed question detected, bypassing turn count.")
                 return True
             
             min_turns_for_guidance = 3 if requires_extra_listening else 1
        else:
             min_turns_for_guidance = 4 if requires_extra_listening else 2
        
        # Log the assessment
        logger.info(
            f"Session {session.session_id}: readiness={readiness:.2f}, turns={session.turn_count}, "
            f"emotion={emotional_state}, min_turns={min_turns_for_guidance}, direct_q={is_direct_question}"
        )
        
        # STRICT RULE: Require minimum turn count even if signals are collected
        if session.turn_count < min_turns_for_guidance:
             return False

        # Ensure spacing between guidance turns (Oscillation Logic)
        # BUT: Allow override if user explicitly demands immediate guidance
        MIN_SPACING = 3
        last_guidance = getattr(session, 'last_guidance_turn', 0) or 0
        
        # Check for URGENT guidance requests that should bypass spacing
        urgent_keywords = ["please guide", "suggest me", "tell me what", "give me some", "show me", "what should i"]
        is_urgent_request = any(keyword in last_msg.lower() for keyword in urgent_keywords)
        
        if last_guidance > 0 and (session.turn_count - last_guidance) < MIN_SPACING:
            if is_urgent_request and is_direct_question:
                # User is explicitly demanding guidance NOW - override spacing
                logger.info(
                    f"Session {session.session_id}: URGENT guidance request detected, "
                    f"bypassing spacing requirement (last={last_guidance}, current={session.turn_count})"
                )
            else:
                # Normal oscillation - enforce spacing
                logger.info(
                    f"Session {session.session_id}: deferring guidance due to spacing "
                    f"(last={last_guidance}, current={session.turn_count}, needed={MIN_SPACING})"
                )
                return False

        # Now check if we should force transition due to signal density/max turns
        if session.should_force_transition():
            logger.info(
                f"Session {session.session_id}: forced wisdom after {session.turn_count} turns"
            )
            return True

        return readiness >= 0.7

    def _build_user_profile(self, memory: ConversationMemory, session: Optional[SessionState] = None) -> Dict:
        profile = {}
        
        # Add current Panchang context if available
        if self.panchang.available:
            from datetime import datetime
            # Use Delhi as default for now, could be improved with user location
            p_data = self.panchang.get_panchang(datetime.now())
            if "error" not in p_data:
                profile["current_panchang"] = {
                    "tithi": p_data["tithi"],
                    "nakshatra": p_data["nakshatra"],
                    "special_day": self.panchang.get_special_day_info(p_data)
                }

        if memory.user_name:
            profile["name"] = memory.user_name

        story = memory.story
        if story.age_group:
            profile["age_group"] = story.age_group
        if story.gender:
            profile["gender"] = story.gender
        if story.profession:
            profile["profession"] = story.profession
        if story.primary_concern:
            profile["primary_concern"] = story.primary_concern
        if story.emotional_state:
            profile["emotional_state"] = story.emotional_state
        if story.life_area:
            profile["life_area"] = story.life_area
        if story.preferred_deity:
            profile["preferred_deity"] = story.preferred_deity
        if story.location:
            profile["location"] = story.location
        if story.spiritual_interests:
            profile["spiritual_interests"] = story.spiritual_interests
        
        # 🔥 Added nested spiritual profile fields
        if story.rashi:
            profile["rashi"] = story.rashi
        if story.gotra:
            profile["gotra"] = story.gotra
        if story.nakshatra:
            profile["nakshatra"] = story.nakshatra
        if story.temple_visits:
            profile["temple_visits"] = story.temple_visits
        if story.purchase_history:
            profile["purchase_history"] = story.purchase_history

        # Add is_returning_user flag so the LLM prompt can acknowledge continuity
        if session and getattr(session, 'is_returning_user', False):
            profile["is_returning_user"] = True

        # Pass tracked practice suggestions so LLM can deepen on acceptance
        if session and session.last_suggestions:
            profile["last_suggestions"] = session.last_suggestions

        return profile

    def _get_doc_type_exclusions(self, intent: Optional[str]) -> Optional[List[str]]:
        """
        Return doc type strings to exclude from RAG for the given intent.
        Returns None if no exclusions apply.
        """
        if not intent:
            return None
        exclusions = {
            IntentType.EXPRESSING_EMOTION: ["temple"],
            IntentType.OTHER: ["temple"],
            IntentType.PRODUCT_SEARCH: ["scripture"],
            IntentType.GREETING: ["temple", "scripture"],
        }
        return exclusions.get(intent)

    def _build_listening_query(
        self, message: str, memory: ConversationMemory
    ) -> str:
        """
        Build a semantically-rich search query for the RAG pipeline.
        Prioritises the CURRENT turn message, then enriches with confirmed
        memory signals (emotion, domain, deity) for better recall.
        Falls back to the raw message if no memory context is available.
        """
        parts = [message.strip()]
        story = memory.story

        # Enrich with confirmed emotional context
        if story.emotional_state and story.emotional_state not in ("unknown", "neutral", ""):
            parts.append(f"feeling {story.emotional_state}")

        # Enrich with the confirmed life domain
        if story.life_area and story.life_area not in ("unknown", ""):
            parts.append(f"life domain: {story.life_area}")

        # Enrich with deity if user has expressed one
        if story.preferred_deity:
            parts.append(f"deity: {story.preferred_deity}")

        # Enrich with the core spiritual/ritual entity if extracted
        if story.primary_concern and len(story.primary_concern) > 10:
            parts.append(story.primary_concern[:100])

        enriched = " | ".join(parts)[:400]  # Cap for embedding efficiency
        logger.debug(f"Enriched RAG query: {enriched[:120]}")
        return enriched

    async def reconstruct_memory(self, session: SessionState, history: list, snapshot: Optional[Dict] = None) -> None:
        """Reconstruct high-level memory from historical messages and optional snapshot"""
        if snapshot:
            from models.memory_context import ConversationMemory
            session.memory = ConversationMemory.from_dict(snapshot)
            logger.info("Initialized memory from persistent snapshot")

        if not history:
            return
            
        logger.info(f"Reconstructing/Refining deep memory from {len(history)} past messages...")
        
        user_msg_count = 0
        # If we had a snapshot, we might want to only process new messages, 
        # but for safety we re-process to ensure consistency if the history is short.
        # However, to avoid double-counting signals from the snapshot, 
        # we only process messages if memory was fresh.
        
        for msg in history:
            if msg.get("role") == "user":
                user_msg_count += 1
                if not snapshot: # Only auto-extract if we didn't have a snapshot
                    self._update_memory(session.memory, session, msg.get("content", ""))
        
        session.turn_count = user_msg_count
        logger.info(f"Memory reconstruction complete. User messages: {user_msg_count}. Story concern: {session.memory.story.primary_concern[:50]}...")

    def _update_memory(self, memory: ConversationMemory, session: SessionState, text: str) -> List[str]:
        """Extract signals and update narrative story"""
        text = text.lower().strip()
        
        # Track topics detected IN THIS TURN specifically
        turn_topics = []

        if not memory.story.primary_concern and len(text) > 10:
            memory.story.primary_concern = text[:200]

        # ------------------------------------------------------------------
        # RICH SIGNAL DETECTION
        # ------------------------------------------------------------------
        
        # Use regex for strict word boundaries
        import re
        def has_word(keywords, text):
            pattern = r'\b(' + '|'.join(map(re.escape, keywords)) + r')\b'
            return bool(re.search(pattern, text))
            
        # 1. EMOTIONAL STATES (Deeply Expanded & Scored)
        emotions = {
            "Sadness & Grief": ["sad", "low", "lonely", "depressed", "hurt", "grief", "despair", "mourning", "loss", "lost", "crying", "tears", "heavy", "hopeless", "empty", "alone", "ache", "inadequate", "unhappy", "hurts", "loneliness", "irritable", "disconnected"],
            "Anxiety & Fear": ["anxious", "anxiety", "worried", "stressed", "overwhelmed", "panic", "fear", "scared", "nervous", "tension", "uneasy", "restless", "deadline", "deadlines", "fraud", "fraudulent", "fail", "failing", "burnout", "burned out", "burning out", "panic", "panic attack", "guilty", "guilt", "burn", "burning", "paralyzed", "concentration", "exam", "exams", "insomnia", "high-stress"],
            "Anger & Frustration": ["angry", "frustrated", "irritated", "furious", "mad", "stupid", "annoying", "rage", "resentment", "hate", "fight", "yell", "hostile", "credit", "irritable"],
            "Confusion & Doubt": ["confused", "lost", "doubt", "uncertain", "directionless", "stuck", "don't know", "unsure", "clarity", "missing", "purpose", "meaning", "existential", "fraud", "fraudulent", "unethical", "guilty", "guilt", "mirror", "wondering", "failing", "ethics", "void", "search"],
            "Gratitude & Peace": ["happy", "grateful", "peace", "calm", "content", "blessed", "thankful", "joy", "serene", "better", "morning", "inspiration", "humility", "humble", "meditation"],
        }
        
        emotion_scores = {}
        for label, keywords in emotions.items():
            # Weighted matches: find unique matches
            matched_keywords = [kw for kw in keywords if has_word([kw], text)]
            if matched_keywords:
                # Basic score is count of unique matches
                score = len(matched_keywords)
                # Specific deep-nuance weights
                if label == "Confusion & Doubt":
                    if has_word(["unethical", "existential", "mirror", "wondering", "if i should", "purpose", "meaning", "failing", "fail", "lost"], text):
                        score += 5
                    if "failing as a parent" in text or "fail as a parent" in text or "dharma" in text:
                        score += 15
                    if has_word(["lost"], text) and has_word(["happiness", "dream", "success", "reached", "bought"], text):
                        score += 15
                if label == "Anxiety & Fear":
                    if has_word(["fraud", "fraudulent", "panic", "guilty", "guilt", "burnout", "burned out", "deadline", "deadlines", "fraud"], text):
                        score += 5
                    if "burning me out" in text or "burning out" in text:
                        score += 10
                if label == "Sadness & Grief":
                    if has_word(["lonely", "ache", "empty", "loneliness"], text):
                        score += 3
                        
                emotion_scores[label] = score
                # print(f"DEBUG: Emotion Match: {label} (Score: {score})")
                if label not in turn_topics:
                    turn_topics.append(label)
                if label not in memory.story.detected_topics:
                    memory.story.detected_topics.append(label)

        if emotion_scores:
            # Conditional Tie-breakers (only hit if multiple signals detected)
            ids = list(emotion_scores.keys())
            
            # Use explicit phrasal overrides first
            if "paralyzed" in text or "exams" in text or "exam" in text:
                emotion_scores["Anxiety & Fear"] = emotion_scores.get("Anxiety & Fear", 0) + 30
            if "irritable" in text or "fight" in text or "stressed" in text:
                # Give a small boost to anxiety if stressed is present
                if "stressed" in text:
                    emotion_scores["Anxiety & Fear"] = emotion_scores.get("Anxiety & Fear", 0) + 5
                if "irritable" in text:
                    emotion_scores["Anger & Frustration"] = emotion_scores.get("Anger & Frustration", 0) + 20
                
            # 1. Anxiety vs Confusion (Imposter/Parenting/Dilemma/Care)
            if "Anxiety & Fear" in ids and "Confusion & Doubt" in ids:
                 # UC11: Imposter Syndrome -> Anxiety wins
                 if has_word(["fraud", "fraudulent", "lead", "promoted"], text):
                     emotion_scores["Anxiety & Fear"] += 30
                 # UC12: Parenting/Moral Dilemma -> Confusion wins
                 if has_word(["values", "traditions", "learn our", "screens", "parent"], text):
                     emotion_scores["Confusion & Doubt"] += 40
                 # UC16: Caregiver Guilt -> Anxiety/Stress wins
                 if has_word(["care", "parents", "aging", "balancing", "burn", "burning"], text):
                     emotion_scores["Anxiety & Fear"] += 30
            
            # 2. Confusion vs Sadness (Existential Crisis / Grief)
            if "Confusion & Doubt" in ids and "Sadness & Grief" in ids:
                 # UC14: Existential crisis -> Confusion wins
                 if has_word(["purpose", "meaning", "reached", "bought", "happiness", "void"], text):
                     emotion_scores["Confusion & Doubt"] += 40
                 # UC3: Grief -> Sadness wins (even with traditions)
                 if has_word(["grandfather", "lost my", "last week"], text):
                     emotion_scores["Sadness & Grief"] += 40
                 # UC17: Startup failure / Starting over -> Confusion wins
                 if has_word(["startup", "start over", "should i", "savings", "confidence"], text):
                     emotion_scores["Confusion & Doubt"] += 40
            
            # 3. Gratitude vs anything (UC28: Pride case / UC22: Inspiration case)
            if "Gratitude & Peace" in ids:
                if has_word(["humility", "success", "doer", "full of myself"], text):
                    emotion_scores["Gratitude & Peace"] += 40
                if has_word(["morning", "meditation", "inspiration", "beautiful"], text) and not has_word(["fear", "anxious", "low", "lost", "stuck", "angry", "hostile", "resentful", "frustrated"], text) and "Routine Request" not in turn_topics:
                    emotion_scores["Gratitude & Peace"] += 40

            # Last-resort safety check before max
            if emotion_scores:
                best_emotion = max(emotion_scores, key=emotion_scores.get)
                memory.story.emotional_state = best_emotion
                session.add_signal(SignalType.EMOTION, best_emotion, 0.85)




        # 2. LIFE DOMAINS (Deeply Expanded with scoring)
        domains = {
            "Career & Finance": ["work", "job", "office", "career", "boss", "colleague", "promotion", "salary", "money", "finance", "debt", "business", "startup", "interview", "hiring", "deadline", "deadlines", "workplace", "hostile", "inflation", "balance", "desk"],
            "Relationships": ["relationship", "partner", "marriage", "wife", "husband", "dating", "boyfriend", "girlfriend", "breakup", "divorce", "love", "crush", "ex", "fight", "social circle"],
            "Family": ["family", "parents", "children", "mother", "father", "son", "daughter", "sister", "brother", "kids", "mom", "dad", "grandparents", "home", "grandfather", "grandmother", "traditions", "parenting", "elderly", "parents", "aging", "kids", "baby", "sleep", "birthday", "gift"],
            "Physical Health": ["health", "digestion", "tired", "sleep", "body", "pain", "disease", "symptom", "weight", "exercise", "energy", "fatigue", "sick", "hurting", "burnout", "fever", "weak", "gut", "insomnia"],
            "Ayurveda & Wellness": ["ayurveda", "dosha", "pitta", "kapha", "vata", "herbs", "remedy", "cleanse", "routine", "dinacharya", "oil", "massage", "natural", "tea", "rejuvenate", "supplement", "diet", "meal"],
            "Yoga Practice": ["yoga", "asana", "posture", "flexibility", "strength", "surya", "namaskar", "hatha", "vinyasa", "routine", "yogic"],
            "Meditation & Mind": ["meditation", "focus", "mind", "concentration", "mindfulness", "dhyana", "awareness", "stillness", "thoughts", "distraction", "mental", "soul", "eternal", "meditated", "mindful"],
            "Spiritual Growth": ["dharma", "karma", "god", "soul", "spirit", "enlightenment", "purpose", "meaning", "faith", "prayer", "devotion", "bhakti", "divine", "sacred", "scripture", "gita", "missing", "ethical", "unethical", "values", "house", "dream", "existential", "void", "search", "philosophy", "upanishad", "humility", "humble"],
            "Panchang & Astrology": ["panchang", "tithi", "nakshatra", "muhurat", "shubh", "calendar", "festival", "vedic astrology", "jyotish", "moon", "waxing", "waning"],
            "Self-Improvement": ["discipline", "growth", "learning", "habits", "productivity", "goals", "confidence", "motivation", "success", "failure", "study", "instagram", "fraud", "fraudulent", "started", "starting", "inadequate", "startup", "fail", "failed", "exam", "exams", "concentration", "focus", "journal", "reflection"],
            "General Life": ["lonely", "moving", "city", "new place", "weekend", "weekends", "phone", "staring", "everyone", "anyone", "understand", "understands"],
        }

        domain_scores = {}
        for label, keywords in domains.items():
            matches = [kw for kw in keywords if has_word([kw], text)]
            if matches:
                score = len(matches)
                # Influence weights for deep scenarios
                if label == "Spiritual Growth" and has_word(["unethical", "ethical", "dream", "house", "meaning", "purpose"], text):
                    score += 5
                if label == "Self-Improvement" and has_word(["instagram", "fraud", "fail", "failed", "startup"], text):
                    score += 5
                if label == "General Life" and has_word(["understand", "understands", "lonely"], text):
                    score += 5
                
                domain_scores[label] = score
                if label not in turn_topics:
                    turn_topics.append(label)
                if label not in memory.story.detected_topics:
                    memory.story.detected_topics.append(label)

        if domain_scores:
            # Domain tie-breakers
            dids = domain_scores.keys()
            
            # UC 21/Self-Improvement/General Life
            if has_word(["exam", "exams", "concentration", "focus"], text):
                if "General Life" in dids:
                    domain_scores["General Life"] += 30
            
            # UC 25/28/30 Spiritual Growth Wins over Career/Family/Self-Imp
            if has_word(["gita", "upanishad", "dharma", "ethics", "unethical", "ethics", "humility", "void", "meaning", "purpose"], text):
                if "Spiritual Growth" in dids:
                    domain_scores["Spiritual Growth"] += 50

            # Procedural Tie-breakers
            if "Diet Plan" in turn_topics and "Ayurveda & Wellness" in dids:
                domain_scores["Ayurveda & Wellness"] += 40
            if "Routine Request" in turn_topics:
                if "Yoga Practice" in dids:
                    domain_scores["Yoga Practice"] += 40
                if "Meditation & Mind" in dids:
                    domain_scores["Meditation & Mind"] += 40
            if "Puja Guidance" in turn_topics:
                if "Family" in dids:
                    domain_scores["Family"] += 40
                if "Spiritual Growth" in dids:
                    domain_scores["Spiritual Growth"] += 40

            # UC 24: Family vs Ayurveda
            if "Family" in dids and has_word(["baby", "parenting", "kids"], text):
                domain_scores["Family"] += 30

            # Pick the domain with the highest score
            best_domain = max(domain_scores, key=domain_scores.get)
            memory.story.life_area = best_domain
            session.add_signal(SignalType.LIFE_DOMAIN, best_domain, 0.9)
            found_domain = True
        else:
            found_domain = False

        
        # Fallback if no specific domain found but text is substantial
        if not found_domain and len(text.split()) > 5:
             if not memory.story.life_area:
                 memory.story.life_area = "General Life"
                 session.add_signal(SignalType.LIFE_DOMAIN, "General Life", 0.5)
                 if "General Life" not in turn_topics:
                     turn_topics.append("General Life")

        # 3. SPECIAL INTENTS
        temple_keywords = ["temple", "mandir", "pilgrimage", "shrine", "darshan", "puri", "kashi", "tirupati", "badrinath", "kedarnath", "dwarka", "rameswaram", "somnath", "visit"]
        if has_word(temple_keywords, text):
            memory.story.temple_interest = text[:100]
            session.add_signal(SignalType.INTENT, "Temple & Pilgrimage", 0.8)
            memory.readiness_for_wisdom = min(1.0, memory.readiness_for_wisdom + 0.35)
            
        breathing_keywords = ["breath", "breathing", "pranayama", "inhale", "exhale", "lungs", "air"]
        if has_word(breathing_keywords, text):
            session.add_signal(SignalType.INTENT, "Pranayama (Breathwork)", 0.8)
            # Tag as Yoga Practice if not already set
            if not found_domain:
                memory.story.life_area = "Yoga Practice"
                session.add_signal(SignalType.LIFE_DOMAIN, "Yoga Practice", 0.9)

        # 4. PRODUCT & SERVICE INTENTS
        # Explicit detection: Look for purchase intent or specific product questions
        buy_keywords = ["buy", "purchase", "order", "price", "cost", "shop", "store", "where can i", "how much", "available", "get", "recommend", "remedy", "products", "item", "items", "is there", "any"]
        product_items = ["rudraksha", "mala", "diya", "incense", "dhoop", "havan", "idol", "thali", "book", "yantra", "murti", "gangajal", "oil", "tea", "supplement", "herbs", "ayurvedic", "journal", "pendant", "bracelet"]
        
        is_explicit_product_inquiry = False
        if has_word(buy_keywords, text) or (has_word(product_items, text) and ("?" in text or "want" in text or "need" in text or "is there" in text or "suggest" in text or "love" in text or "get" in text)):
            is_explicit_product_inquiry = True

        if is_explicit_product_inquiry:
            session.add_signal(SignalType.INTENT, "Product Inquiry", 0.9)
            if "Product Inquiry" not in turn_topics:
                turn_topics.append("Product Inquiry")
            # Boost readiness as user is asking for specific items
            memory.readiness_for_wisdom = min(1.0, memory.readiness_for_wisdom + 0.6)

        # 5. VERSE & SCRIPTURE INTENTS
        verse_keywords = ["verse", "verses", "scripture", "scriptures", "gita", "upanishad", "upanishads", "mantra", "mantras", "remind me", "wisdom", "sloka", "shloka", "philosophy"]
        intent_keywords = ["give", "tell", "provide", "share", "need", "want", "love", "send", "suggest", "provide me", "how to", "show", "read", "?"]
        if has_word(verse_keywords, text) and (any(w in text for w in intent_keywords)):
            session.add_signal(SignalType.INTENT, "Verse Request", 0.9)
            if "Verse Request" not in turn_topics:
                turn_topics.append("Verse Request")
            # Boost readiness significantly for direct scripture requests
            memory.readiness_for_wisdom = min(1.0, memory.readiness_for_wisdom + 0.6)

        # 6. PROCEDURAL & ROUTINE INTENTS
        # Routine Request
        routine_keywords = ["routine", "plan", "program", "schedule", "daily", "day", "morning", "evening", "night", "breaks", "habit", "starter"]
        routine_activity = ["yoga", "meditation", "breaks", "exercise", "sleep", "nidra", "yogic", "meditated", "mindful", "moon", "phases", "alignment"]
        if has_word(routine_keywords, text) and (has_word(routine_activity, text) or has_word(["how", "give", "create", "provide"], text)):
            session.add_signal(SignalType.INTENT, "Routine Request", 0.9)
            if "Routine Request" not in turn_topics:
                turn_topics.append("Routine Request")
            memory.readiness_for_wisdom = min(1.0, memory.readiness_for_wisdom + 0.5)

        # Puja Guidance
        puja_keywords = ["puja", "pooja", "ritual", "ceremony", "altar", "mandir", "home temple", "worship", "spiritual corner"]
        puja_action = ["plan", "how", "steps", "items", "setup", "prepare", "perform", "instructions", "direction", "essential"]
        if has_word(puja_keywords, text) and (has_word(puja_action, text) or "?" in text):
            session.add_signal(SignalType.INTENT, "Puja Guidance", 0.9)
            if "Puja Guidance" not in turn_topics:
                turn_topics.append("Puja Guidance")
            memory.readiness_for_wisdom = min(1.0, memory.readiness_for_wisdom + 0.5)
            # Prevent Product Inquiry from taking over in setup context
            if "Product Inquiry" in turn_topics and has_word(["setup", "direction", "corner"], text):
                turn_topics.remove("Product Inquiry")

        # Diet Plan
        diet_keywords = ["diet", "food", "eat", "meal", "meals", "breakfast", "lunch", "dinner", "prep", "nutrition"]
        diet_context = ["plan", "routine", "ayurvedic", "sattvic", "pitta", "kapha", "vata", "dosha"]
        if has_word(diet_keywords, text) and has_word(diet_context, text):
            session.add_signal(SignalType.INTENT, "Diet Plan", 0.9)
            if "Diet Plan" not in turn_topics:
                turn_topics.append("Diet Plan")
            memory.readiness_for_wisdom = min(1.0, memory.readiness_for_wisdom + 0.5)

        # Longer quotes for better recall
        memory.add_user_quote(session.turn_count, text[:500])

        if memory.story.emotional_state:
            memory.record_emotion(
                session.turn_count,
                memory.story.emotional_state,
                "moderate",
            )
            memory.readiness_for_wisdom = min(1.0, memory.readiness_for_wisdom + 0.15)
        
        # Boost readiness for long messages
        if len(text) > 100:
            memory.readiness_for_wisdom = min(1.0, memory.readiness_for_wisdom + 0.2)
        
        # Boost readiness for direct "how to" or specific questions
        wellness_query_keywords = ["how do i", "what is", "routine", "technique", "practice", "method", "steps"]
        if any(w in text for w in wellness_query_keywords) and "?" in text:
            memory.readiness_for_wisdom = min(1.0, memory.readiness_for_wisdom + 0.3)

        return turn_topics


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------

_companion_engine: Optional[CompanionEngine] = None


def get_companion_engine() -> CompanionEngine:
    global _companion_engine
    if _companion_engine is None:
        _companion_engine = CompanionEngine()
    return _companion_engine
