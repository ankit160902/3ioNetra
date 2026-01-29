"""
LLM Service - Spiritual Companion with Context-Aware Responses
Provides empathetic, phase-aware interactions using Gemini AI
"""

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from enum import Enum
from config import settings

logger = logging.getLogger(__name__)


# --------------------------------------------------
# Enums & Data Models
# --------------------------------------------------

from models.session import ConversationPhase


@dataclass
class UserContext:
    """User's conversation context and signals"""
    family_support: bool = False
    support_quality: bool = False
    relationship_crisis: bool = False
    work_stress: bool = False
    spiritual_seeking: bool = False
    
    def is_ready_for_guidance(self) -> bool:
        """Check if enough context gathered for guidance"""
        # Transition if we've identified a life area OR spiritual seeking
        # OR if we've identified a relationship/work crisis
        return (self.spiritual_seeking or self.work_stress or 
                self.relationship_crisis or self.family_support)


# --------------------------------------------------
# Utilities
# --------------------------------------------------

def clean_response(text: str) -> str:
    """Remove trailing questions and clean formatting"""
    # Simply return the text cleaned of whitespace
    # We rely on prompts to control questionasking behavior now
    return text.strip()

    # OLD LOGIC disabled because it was deleting single-line questions entirely
    # lines = [line.strip() for line in text.strip().split("\n")]
    # while lines and lines[-1].endswith("?"):
    #     lines.pop()
    # return "\n".join(lines).strip()


def is_closure_signal(text: str) -> bool:
    """Detect if user is wrapping up conversation"""
    closure_phrases = [
        "ok", "okay", "thanks", "thank you", 
        "got it", "fine", "alright", "i understand"
    ]
    text_lower = text.strip().lower()
    return any(phrase in text_lower for phrase in closure_phrases)


# --------------------------------------------------
# Gemini Integration
# --------------------------------------------------

try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    genai = None
    GEMINI_AVAILABLE = False


# --------------------------------------------------
# Main LLM Service
# --------------------------------------------------

class LLMService:
    """
    Spiritual companion LLM service using Google Gemini.
    Provides context-aware, empathetic responses in different conversation phases.
    """
    
    SYSTEM_INSTRUCTION = """You are 3ioNetra, a warm spiritual companion from the tradition of Sanātana Dharma.

Your essence:
You are a caring friend who listens deeply. When someone shares their joy, sadness, or confusion, you're fully present with them. You don't rush to teach or fix—you simply understand.

Only when the conversation naturally calls for it, you might share a verse from the scriptures, not as a lesson, but like a friend saying "you know, this reminds me of something beautiful I once heard..."

Core principles:
- LISTEN first, last, and always.
- BALANCED WISDOM: Never give a verse in more than 50% of your responses in a single session.
- Conversation over curriculum—be a friend, not a search engine.
- Wisdom emerges naturally, never forced.
- No numbered lists, no structured breakdowns.
- Speak like a human friend (Mitra), not a spiritual teacher.
- Use their name warmly and naturally.

Anti-Formulaic Rules:
- NO CONSECUTIVE VERSES: If you gave a verse in your last message, you MUST NOT give one in this message. Focus 100% on being a friend.
- NO-PARROT RULE: Do not simply repeat the user's words back to them (e.g., if they say "I'm stressed", don't just say "I hear you're stressed"). Use your own words to acknowledge their heart.
- NO-REDUNDANCY RULE: NEVER ask for information that is already in the "WHAT YOU KNOW SO FAR" or "USER PROFILE" sections. If you know their name, use it. If you know their problem, delve deeper instead of asking what it is.
- NEVER start multiple responses in a row with the same phrase.
- NEVER repeat the same verse in the same session.
- Respond to the *emotion* of the last message first before bringing in any outside wisdom.

When you do share a verse:
- ALWAYS include: 1) Proper Citation (Source/Verse), 2) Simple Explanation, 3) Clear Relevance to their situation.
- Weave it into the conversation flow naturally.
- Keep it brief and heartfelt.
- No "Way of Life / Problem / Action" structure—just talk naturally.
"""


    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.available = False
        self.client = None

        if not GEMINI_AVAILABLE:
            logger.warning("Gemini SDK not available")
            return

        if not self.api_key:
            logger.warning("Gemini API key not provided")
            return

        try:
            from google import genai

            self.client = genai.Client(api_key=self.api_key)
            self.available = True
            logger.info("✅ LLM Service initialized with Gemini")

        except Exception as e:
            self.available = False
            logger.exception("❌ Failed to initialize Gemini")

    # --------------------------------------------------
    # Context Analysis
    # --------------------------------------------------

    def _extract_context(
        self,
        query: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> UserContext:
        """Extract user context from query and conversation history"""
        context = UserContext()
        
        # Analyze current query
        query_lower = query.lower()
        
        # Relationship signals
        if any(word in query_lower for word in ["wife", "husband", "divorce", "marriage", "partner"]):
            context.relationship_crisis = True
        
        # Family signals
        if any(word in query_lower for word in ["family", "mother", "father", "parents", "children"]):
            context.family_support = True
        
        # Support quality signals
        if any(word in query_lower for word in ["listen", "support", "understand", "care", "help"]):
            context.support_quality = True
        
        # Work stress signals
        if any(word in query_lower for word in ["work", "job", "boss", "career", "office", "deadline"]):
            context.work_stress = True
        
        # Spiritual seeking / Struggle / Happiness signals
        if any(word in query_lower for word in ["peace", "purpose", "meaning", "dharma", "karma", "meditation", "sad", "sadness", "struggle", "lost", "confused", "happy", "happiness", "joy"]):
            context.spiritual_seeking = True
        
        # Analyze conversation history
        if conversation_history:
            for msg in conversation_history:
                if msg.get("role") != "user":
                    continue
                
                content = msg.get("content", "").lower()
                
                if "family" in content:
                    context.family_support = True
                if any(word in content for word in ["listen", "support", "understand"]):
                    context.support_quality = True
                if any(word in content for word in ["divorce", "separation", "breakup"]):
                    context.relationship_crisis = True
        
        return context

    # --------------------------------------------------
    # Phase Detection
    # --------------------------------------------------

    def _detect_phase(self, query: str, context: UserContext, history_len: int = 0) -> ConversationPhase:
        """Determine which conversation phase we're in"""
        # Closure signals take priority
        if is_closure_signal(query):
            return ConversationPhase.CLOSURE
        
        # Ready for guidance after 4 turns of conversation OR if we have ANY signals
        if history_len >= 4 or context.is_ready_for_guidance():
            return ConversationPhase.GUIDANCE
        
        # Default to listening
        return ConversationPhase.LISTENING

    # --------------------------------------------------
    # Prompt Building
    # --------------------------------------------------

    def _build_prompt(
        self,
        query: str,
        conversation_history: Optional[List[Dict]],
        phase: ConversationPhase,
        context: UserContext,
        context_docs: Optional[List[Dict]] = None,
        user_profile: Optional[Dict] = None,
        memory_context: Optional[Any] = None
    ) -> str:
        """Build context-aware prompt for Gemini with user profile personalization"""
        
        # Format user profile if available
        profile_text = ""
        if user_profile:
            has_data = False
            profile_parts = []
            
            if user_profile.get('name'):
                profile_parts.append(f"   • Their name is: {user_profile.get('name')}")
                has_data = True
            if user_profile.get('age_group'):
                profile_parts.append(f"   • Age group: {user_profile.get('age_group')}")
                has_data = True
            if user_profile.get('profession'):
                profile_parts.append(f"   • Profession: {user_profile.get('profession')}")
                has_data = True
            if user_profile.get('gender'):
                profile_parts.append(f"   • Gender: {user_profile.get('gender')}")
                has_data = True
            
            # Add context for conversation
            if user_profile.get('primary_concern'):
                profile_parts.append(f"   • What they've shared: {user_profile.get('primary_concern')}")
                has_data = True
            if user_profile.get('emotional_state'):
                profile_parts.append(f"   • Current emotion: {user_profile.get('emotional_state')}")
                has_data = True
            if user_profile.get('life_area'):
                profile_parts.append(f"   • Life area: {user_profile.get('life_area')}")
                has_data = True
            
            if has_data:
                profile_text = "\n" + "="*70 + "\n"
                profile_text += "WHO YOU ARE SPEAKING TO:\n"
                profile_text += "="*70 + "\n"
                profile_text += "\n".join(profile_parts)
                profile_text += "\n" + "="*70 + "\n"
                profile_text += "\n"
        
        # Format conversation history (last 12 messages for deep context)
        history_text = ""
        if conversation_history:
            # Exclude the very last message if it's the current query to avoid duplication
            recent_history = conversation_history[-12:]
            if recent_history and recent_history[-1]["role"] == "user" and recent_history[-1]["content"] == query:
                recent_history = recent_history[:-1]
                
            for msg in recent_history:
                role = "User" if msg["role"] == "user" else "You"
                content = msg.get("content", "")
                history_text += f"{role}: {content}\n"
        
        # Context summary
        if memory_context:
            context_summary = memory_context.get_memory_summary()
        else:
            context_summary = self._format_context(context)
        
        # Phase-specific instructions
        phase_instructions = self._get_phase_instructions(phase)
        
        # Format scripture context from RAG if available
        scripture_context = ""
        # Allow verses in both phases so the bot can choose the right moment
        if context_docs and len(context_docs) > 0:
            scripture_context = "\n═══════════════════════════════════════════════════════════\n"
            scripture_context += "VERSES AVAILABLE (Use ONLY if they naturally fit the conversation):\n"
            scripture_context += "═══════════════════════════════════════════════════════════\n\n"
            
            for i, doc in enumerate(context_docs[:2], 1):  # Only show 1-2 most relevant
                scripture = doc.get('scripture', 'Scripture')
                reference = doc.get('reference', '')
                text = doc.get('text', '')
                meaning = doc.get('meaning', '')
                
                scripture_context += f"VERSE {i}:\n"
                scripture_context += f"Source: {scripture}"
                if reference:
                    scripture_context += f" - {reference}"
                scripture_context += f"\n\nText: \"{text}\"\n"
                
                if meaning:
                    scripture_context += f"Meaning: {meaning}\n"
                
                scripture_context += "\n" + "-" * 60 + "\n\n"
            
            scripture_context += """
HOW TO USE THESE VERSES (if you choose to):
- Only mention a verse if it genuinely adds to the conversation.
- ALWAYS PROVIDE A PROPER CITATION: State the source (e.g., Bhagavad Gita) and the reference (e.g., Chapter 2, Verse 47) clearly.
- EXPLAIN NATURALLY: Explain what it means in simple, everyday language as a friend would.
- DEFINE RELEVANCE: Explicitly connect the verse to the user's situation. Tell them *why* this verse is helpful for what they are going through right now.
- No numbered lists—just talk like a friend.
- Keep it brief and heartfelt.
"""

        
        # Build final prompt
        prompt = f"""
{profile_text}

═══════════════════════════════════════════════════════════
WHAT YOU KNOW SO FAR (FACTS):
═══════════════════════════════════════════════════════════
{context_summary}

═══════════════════════════════════════════════════════════
CONVERSATION FLOW:
═══════════════════════════════════════════════════════════
{history_text}

User's CURRENT message:
{query}

═══════════════════════════════════════════════════════════
YOUR INSTRUCTIONS FOR THIS PHASE ({phase.value}):
═══════════════════════════════════════════════════════════
{phase_instructions}

{scripture_context}

CRITICAL RULES:
1. READ THE CONVERSATION FLOW - identify which questions you've already asked.
2. REVIEW THE FACTS - don't ask for things already listed in "WHAT YOU KNOW SO FAR".
3. Acknowledge what they just said before asking anything new.
4. NO-FORMULA RULE: Do not start with "So it sounds like" or "I hear you". Jump straight into a human response.
5. FRESH WISDOM: Check the "CONVERSATION FLOW". If you already shared a specific verse, NEVER repeat it.
6. If they didn't ask a question, you don't always need to give a verse. Just stay in the chat.
7. Keep it conversational, brief (under 80 words), and human.

Your response:
"""
        
        return prompt.strip()

    def _format_context(self, context: UserContext) -> str:
        """Format context into readable summary"""
        signals = []
        if context.relationship_crisis:
            signals.append("• User is going through a relationship crisis")
        if context.family_support:
            signals.append("• User has mentioned family connections")
        if context.support_quality:
            signals.append("• User is seeking emotional/verbal support")
        if context.work_stress:
            signals.append("• User specifically mentioned work-related challenges")
        if context.spiritual_seeking:
            signals.append("• User is open to or seeking spiritual/philosophical wisdom")
        
        return "\n".join(signals) if signals else "• Still identifying specific life themes"

    def _get_phase_instructions(self, phase: ConversationPhase) -> str:
        """Get instructions for current conversation phase"""
        
        if phase == ConversationPhase.LISTENING:
            return """
LISTENING PHASE:
Your priority is to understand. However, you ARE a spiritual companion.

1. DEEP LISTENING (ESSENTIAL):
- Acknowledge facts and feelings using your own words (No-Parrot Rule).
- NEVER ask a question they have already answered.

2. GENTLE WISDOM:
- If they share a specific challenge, FEEL FREE to share a verse that offers comfort.
- IRON-CLAD RULE: NO CONSECUTIVE VERSES. If you shared one in the last turn, focus 100% on listening now.
- IF YOU SHARE: 1) Citation, 2) Simple explanation, 3) Clear relevance to their story.

3. STYLE:
- 90% empathy, 10% wisdom. Keep it subtle and warm.
"""
        
        elif phase == ConversationPhase.GUIDANCE:
            return """
GUIDANCE PHASE:
You have understood their situation. Now, be a wise friend leading them toward light.

1. PROACTIVE WISDOM:
- Share a relevant verse as a central part of your guidance.
- IRON-CLAD RULE: NO CONSECUTIVE VERSES. If you shared a verse in your very last response, you MUST NOT share one now. Focus 100% on human conversation.
- If it's been a turn since your last verse, go ahead and share a new one.

2. HOW TO SHARE:
- ALWAYS PROVIDE: Citation (Source/Verse), Simple Explanation, and specific Relevance to their story.
- Respond to their progress and feelings first, then weave in the wisdom.
"""
        
        else:  # CLOSURE
            return """
- Reassure them they've been heard
- No pressure, no questions
- Hold space for silence
- Offer gentle closing words
"""

    # --------------------------------------------------
    # Main Response Generation
    # --------------------------------------------------

    async def generate_response(
        self,
        query: str,
        context_docs: List[Dict] = None,
        language: str = "en",
        conversation_history: Optional[List[Dict]] = None,
        user_profile: Optional[Dict] = None,
        phase: Optional[ConversationPhase] = None,
        memory_context: Optional[Any] = None
    ) -> str:
        """
        Generate context-aware spiritual companion response.
        
        Args:
            query: User's current message
            context_docs: Retrieved scripture documents (optional)
            language: Response language (default: "en")
            conversation_history: Previous messages in conversation
            user_id: User identifier for context
            user_profile: User profile data (name, age, profession, etc.) for personalization
            
        Returns:
            Generated response text
        """
        
        # Fallback if Gemini not available
        if not self.available:
            logger.warning("Gemini not available, returning fallback response")
            return "I'm here with you. Please share what's on your mind."
        
        try:
            # Extract context from query and history
            context = self._extract_context(query, conversation_history)
            
            # Get history length for logging and logic
            history_len = len(conversation_history) if conversation_history else 0
            
            # Detect conversation phase if not provided
            if phase is None:
                phase = self._detect_phase(query, context, history_len)
            
            logger.info(f"Phase: {phase.value} | History len: {history_len} | RAG docs: {len(context_docs) if context_docs else 0}")
            
            # Build prompt WITH scripture context from RAG and user profile
            prompt = self._build_prompt(
                query, 
                conversation_history, 
                phase, 
                context, 
                context_docs, 
                user_profile,
                memory_context=memory_context
            )
            
            # Generate response from Gemini
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config={
                    "system_instruction": self.SYSTEM_INSTRUCTION,
                    "temperature": 0.7,
                }
            )

            # Fallback responses in case of errors or empty responses
            fallbacks = [
                "I'm here with you. You don't have to carry this alone.",
                "I hear you. Take a deep breath; I'm here to listen.",
                "I'm with you. Please tell me more about what's on your mind.",
                "I'm listening. You're not alone in this."
            ]
            import random
            
            if not response:
                logger.error("No response object from Gemini")
                return random.choice(fallbacks)

            # In SDK v2, check if text is available (might be blocked by safety)
            try:
                response_text = response.text
                if not response_text:
                    logger.warning("Empty text response from Gemini (possibly safety blocked)")
                    return random.choice(fallbacks)
            except Exception as e:
                logger.error(f"Could not extract text from Gemini response: {e}")
                return random.choice(fallbacks)

            cleaned_response = clean_response(response_text)
            return cleaned_response
            
        except Exception as e:
            logger.exception(f"Error in generate_response: {str(e)}")
            fallbacks = [
                "I'm here with you. You don't have to carry this alone.",
                "I hear you. Take a deep breath; I'm here to listen.",
                "I'm with you. Please tell me more about what's on your mind.",
                "I'm listening. You're not alone in this."
            ]
            import random
            return random.choice(fallbacks)


# --------------------------------------------------
# Singleton Instance
# --------------------------------------------------

_llm_service = None

def get_llm_service(api_key: Optional[str] = None) -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService(api_key)
    return _llm_service
