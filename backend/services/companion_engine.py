import logging
import random
from typing import Tuple, Optional, TYPE_CHECKING, Dict

from models.session import SessionState, ConversationPhase, SignalType
from models.memory_context import ConversationMemory
from llm.service import get_llm_service
from services.panchang_service import get_panchang_service
from services.intent_agent import get_intent_agent
from services.memory_service import get_memory_service
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

    def __init__(self, rag_pipeline: Optional["RAGPipeline"] = None) -> None:
        self.llm = get_llm_service()
        self.rag_pipeline = rag_pipeline
        self.panchang = get_panchang_service()
        self.intent_agent = get_intent_agent()
        self.memory_service = get_memory_service(rag_pipeline)
        self.product_service = get_product_service()
        self.available = self.llm.available
        logger.info(f"CompanionEngine initialized (LLM available={self.available})")

    def set_rag_pipeline(self, rag_pipeline: "RAGPipeline") -> None:
        self.rag_pipeline = rag_pipeline
        self.memory_service.set_rag_pipeline(rag_pipeline)
        logger.info("RAG pipeline connected to CompanionEngine")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process_message(
        self,
        session: SessionState,
        message: str,
    ) -> Tuple[str, bool, List[Dict], List[str], List[Dict]]:
        """
        Returns:
            (assistant_text, is_ready_for_wisdom, context_docs_used, turn_topics, recommended_products)
        """
        turn_topics = self._update_memory(session.memory, session, message)

        # 🚀 LLM-based Intent & Context Analysis
        # We perform this here to get high-fidelity signals for this turn
        analysis = await self.intent_agent.analyze_intent(message, session.memory.get_memory_summary())
        
        # 1. Update session signals from LLM analysis
        if analysis.get("life_domain") and analysis["life_domain"] != "unknown":
            session.memory.story.life_area = analysis["life_domain"]
            session.add_signal(SignalType.LIFE_DOMAIN, analysis["life_domain"], 0.95)
            
        if analysis.get("emotion") and analysis["emotion"] != "neutral":
            session.memory.story.emotional_state = analysis["emotion"]
            session.add_signal(SignalType.EMOTION, analysis["emotion"], 0.9)

        # 2. Store in Long-Term Memory if it's a significant shared experience
        # (Using a simple heuristic: long message or high urgency)
        if len(message) > 100 or analysis.get("urgency") in ["high", "crisis"]:
            if hasattr(session, "user_id") and session.user_id:
                # We store in background (implicitly async)
                import asyncio
                asyncio.create_task(self.memory_service.store_memory(session.user_id, message))

        # 3. Retrieve relevant long-term memories to enhance the prompt
        past_memories = []
        if hasattr(session, "user_id") and session.user_id:
            past_memories = await self.memory_service.retrieve_relevant_memories(session.user_id, message)

        is_ready = self._assess_readiness(session) or analysis.get("intent") == "SEEKING_GUIDANCE"

        # ------------------------------------------------------------------
        # Ready for wisdom → return short acknowledgement only
        # ------------------------------------------------------------------
        if is_ready:
            acknowledgements = [
                "Thank you for sharing. Let me reflect on this through the lens of Dharma.",
                "I appreciate your honesty. I'm looking into the scriptures for guidance.",
                "I hear you deeply. Please give me a moment to gather wisdom for your situation.",
                "Namaste. Your words have touched me. I am seeking the right dharmic path for you."
            ]
            import random
            
            # Fetch products if product inquiry detected
            products = []
            is_product_inquiry = "Product Inquiry" in turn_topics or analysis.get("intent") == "PRODUCT_SEARCH"
            
            if is_product_inquiry:
                products = await self.product_service.search_products(message)
            
            # Fallback to recommended products only in guidance phase if no specific ones found
            if not products:
                products = await self.product_service.get_recommended_products()

            return random.choice(acknowledgements), True, [], turn_topics, products

        # ------------------------------------------------------------------
        # Not ready → generate empathetic follow-up
        # ------------------------------------------------------------------
        if self.available:
            context_docs = []

            if self.rag_pipeline and self.rag_pipeline.available:
                try:
                    # Skip RAG for panchang queries to avoid irrelevant verses
                    panchang_keywords = ["panchang", "tithi", "nakshatra", "muhurat", "today's day", "calendar"]
                    if any(k in message.lower() for k in panchang_keywords):
                        logger.info("Skipping RAG for Panchang-related query in listening phase")
                        context_docs = []
                    else:
                        search_query = self._build_listening_query(message, session.memory)
                        context_docs = await self.rag_pipeline.search(
                            query=search_query,
                            scripture_filter=None,
                            language="en",
                            top_k=3,
                        )
                except Exception as e:
                    logger.warning(f"Listening-phase RAG failed: {e}")

            # Build user profile and inject past memories
            user_profile = self._build_user_profile(session.memory, session)
            if past_memories:
                user_profile["past_memories"] = past_memories

            reply = await self.llm.generate_response(
                query=message,
                context_docs=context_docs,
                conversation_history=session.conversation_history,
                user_profile=user_profile,
                phase=ConversationPhase.CLARIFICATION,
                memory_context=session.memory,
            )

            # Check for products in listening phase ONLY if explicitly a product inquiry
            products = []
            is_product_inquiry = "Product Inquiry" in turn_topics or analysis.get("intent") == "PRODUCT_SEARCH"

            if is_product_inquiry:
                products = await self.product_service.search_products(message)

            return reply, False, context_docs, turn_topics, products

        # Fallback (no LLM)
        return (
            "I’m here with you. Could you tell me a little more about what feels most heavy right now?",
            False,
            [],
            turn_topics,
            []
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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

        return profile

    def _build_listening_query(
        self, message: str, memory: ConversationMemory
    ) -> str:
        summary = memory.get_memory_summary()
        return summary if summary else message[:150]

    async def reconstruct_memory(self, session: SessionState, history: list) -> None:
        """Reconstruct high-level memory from historical messages"""
        if not history:
            return
            
        logger.info(f"Reconstructing deep memory from {len(history)} past messages...")
        
        # Process messages in order to rebuild the story
        for msg in history:
            if msg.get("role") == "user":
                self._update_memory(session.memory, session, msg.get("content", ""))
            
        logger.info(f"Memory reconstruction complete. Story concern: {session.memory.story.primary_concern[:50]}...")

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
            
        # 1. EMOTIONAL STATES (Expanded)
        emotions = {
            "Sadness & Grief": ["sad", "low", "lonely", "depressed", "hurt", "grief", "despair", "mourning", "loss", "crying", "tears", "heavy", "hopeless"],
            "Anxiety & Fear": ["anxious", "anxiety", "worried", "stressed", "overwhelmed", "panic", "fear", "scared", "nervous", "tension", "uneasy", "restless"],
            "Anger & Frustration": ["angry", "frustrated", "irritated", "furious", "mad", "stupid", "annoying", "rage", "resentment", "hate"],
            "Confusion & Doubt": ["confused", "lost", "doubt", "uncertain", "directionless", "stuck", "don't know", "unsure", "clarity"],
            "Gratitude & Peace": ["happy", "grateful", "peace", "calm", "content", "blessed", "thankful", "joy", "serene", "better"],
        }
        
        is_negated = "not " in text or "don't " in text or "dont " in text or "no " in text

        for label, keywords in emotions.items():
            if has_word(keywords, text) and not is_negated:
                memory.story.emotional_state = label
                session.add_signal(SignalType.EMOTION, label, 0.85)
                if label not in turn_topics:
                    turn_topics.append(label)
                if label not in memory.story.detected_topics:
                    memory.story.detected_topics.append(label)

        # 2. LIFE DOMAINS (Drastically Expanded)
        domains = {
            "Career & Finance": ["work", "job", "office", "career", "boss", "colleague", "promotion", "salary", "money", "finance", "debt", "business", "startup", "interview", "hiring"],
            "Relationships": ["relationship", "partner", "marriage", "wife", "husband", "dating", "boyfriend", "girlfriend", "breakup", "divorce", "love", "crush", "ex"],
            "Family": ["family", "parents", "children", "mother", "father", "son", "daughter", "sister", "brother", "kids", "mom", "dad", "grandparents", "home"],
            "Physical Health": ["diet", "health", "digestion", "tired", "sleep", "body", "pain", "disease", "symptom", "weight", "exercise", "energy", "fatigue", "sick"],
            "Ayurveda & Wellness": ["ayurveda", "dosha", "pitta", "kapha", "vata", "herbs", "remedy", "cleanse", "routine", "dinacharya", "oil", "massage"],
            "Yoga Practice": ["yoga", "asana", "posture", "flexibility", "strength", "surya", "namaskar", "hatha", "vinyasa"],
            "Meditation & Mind": ["meditation", "focus", "mind", "concentration", "mindfulness", "dhyana", "awareness", "stillness", "thoughts", "distraction", "mental"],
            "Spiritual Growth": ["dharma", "karma", "god", "soul", "spirit", "enlightenment", "purpose", "meaning", "faith", "prayer", "devotion", "bhakti", "divine", "sacred", "scripture", "gita"],
            "Panchang & Astrology": ["panchang", "tithi", "nakshatra", "muhurat", "shubh", "calendar", "festival", "vedic astrology", "jyotish"],
            "Self-Improvement": ["discipline", "growth", "learning", "habits", "productivity", "goals", "confidence", "motivation", "success", "failure", "study"],
        }

        found_domain = False
        for label, keywords in domains.items():
            if has_word(keywords, text):
                memory.story.life_area = label
                session.add_signal(SignalType.LIFE_DOMAIN, label, 0.9)
                found_domain = True
                if label not in turn_topics:
                    turn_topics.append(label)
                if label not in memory.story.detected_topics:
                    memory.story.detected_topics.append(label)
        
        # Fallback if no specific domain found but text is substantial
        if not found_domain and len(text.split()) > 5:
             # Just leave detected domain as is, or set to "General Life" if empty
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
        buy_keywords = ["buy", "purchase", "order", "price", "cost", "shop", "store", "where can i", "how much", "available"]
        product_items = ["rudraksha", "mala", "diya", "incense", "dhoop", "havan", "idol", "thali", "book", "yantra", "murti", "gangajal"]
        
        is_explicit_product_inquiry = False
        if has_word(buy_keywords, text) or (has_word(product_items, text) and ("?" in text or "want" in text or "need" in text)):
            is_explicit_product_inquiry = True

        if is_explicit_product_inquiry:
            session.add_signal(SignalType.INTENT, "Product Inquiry", 0.9)
            if "Product Inquiry" not in turn_topics:
                turn_topics.append("Product Inquiry")
            # Boost readiness as user is asking for specific items
            memory.readiness_for_wisdom = min(1.0, memory.readiness_for_wisdom + 0.3)

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
