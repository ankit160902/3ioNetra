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

class ConversationPhase(str, Enum):
    """Phases of spiritual conversation"""
    LISTENING = "listening"          # Understanding user's situation
    GUIDANCE = "guidance"            # Providing spiritual wisdom
    CLOSURE = "closure"              # Wrapping up, holding space


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
        return self.family_support and self.support_quality


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
    
    SYSTEM_INSTRUCTION = """You are a compassionate Sanātani spiritual companion.

Your approach:
- Listen deeply, speak less
- Remember what was shared before
- Never reopen completed topics
- Repetition from user = confirmation, not confusion
- Closure signals = hold space, reduce pressure
- Ask minimal questions, prioritize understanding
- Offer wisdom when context is clear

When scripture wisdom is provided to you:
- Weave it naturally into your response - don't recite it verbatim
- Connect the timeless teaching to their specific situation
- Make the ancient wisdom feel relevant and accessible
- Use simple language to explain profound concepts
- Let the wisdom guide your response, not dominate it

You are NOT:
- A therapist conducting sessions
- An interviewer asking structured questions
- A scripture teacher giving lectures
- A bot reciting verses mechanically

You ARE:
- A calm, grounded presence
- A bridge to timeless wisdom from sacred scriptures
- A companion who listens and understands
- Someone who helps people see their struggles through a dharmic lens
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
        
        # Spiritual seeking signals
        if any(word in query_lower for word in ["peace", "purpose", "meaning", "dharma", "karma", "meditation"]):
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

    def _detect_phase(self, query: str, context: UserContext) -> ConversationPhase:
        """Determine which conversation phase we're in"""
        # Closure signals take priority
        if is_closure_signal(query):
            return ConversationPhase.CLOSURE
        
        # Ready for guidance if sufficient context gathered
        if context.is_ready_for_guidance():
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
        context_docs: Optional[List[Dict]] = None
    ) -> str:
        """Build context-aware prompt for Gemini"""
        
        # Format conversation history (last 6 messages)
        history_text = ""
        if conversation_history:
            recent_history = conversation_history[-6:]
            for msg in recent_history:
                role = "User" if msg["role"] == "user" else "You"
                content = msg.get("content", "")
                history_text += f"{role}: {content}\n"
        
        # Context summary
        context_summary = self._format_context(context)
        
        # Phase-specific instructions
        phase_instructions = self._get_phase_instructions(phase)
        
        # Format scripture context from RAG if available
        scripture_context = ""
        if context_docs and len(context_docs) > 0:
            scripture_context = "\nRelevant Spiritual Wisdom from Scriptures:\n"
            for i, doc in enumerate(context_docs[:3], 1):  # Use top 3 most relevant
                scripture = doc.get('scripture', 'Scripture')
                reference = doc.get('reference', '')
                text = doc.get('text', '')
                
                scripture_context += f"\n{i}. From {scripture}"
                if reference:
                    scripture_context += f" ({reference})"
                scripture_context += f":\n\"{text}\"\n"
            
            scripture_context += "\nUse this wisdom thoughtfully to guide your response when appropriate.\n"
        
        # Build final prompt
        prompt = f"""
Previous conversation:
{history_text}

Context you understand about the user:
{context_summary}
{scripture_context}

User's current message:
{query}

Your response approach for this phase ({phase.value}):
{phase_instructions}

Respond now:
"""
        
        return prompt.strip()

    def _format_context(self, context: UserContext) -> str:
        """Format context into readable summary"""
        signals = []
        if context.relationship_crisis:
            signals.append("• Experiencing relationship challenges")
        if context.family_support:
            signals.append("• Has family in their life")
        if context.support_quality:
            signals.append("• Values emotional support and understanding")
        if context.work_stress:
            signals.append("• Dealing with work-related stress")
        if context.spiritual_seeking:
            signals.append("• Seeking spiritual wisdom or peace")
        
        return "\n".join(signals) if signals else "• Still gathering context"

    def _get_phase_instructions(self, phase: ConversationPhase) -> str:
        """Get instructions for current conversation phase"""
        
        if phase == ConversationPhase.LISTENING:
            return """
- Listen with empathy and validate their feelings
- If scripture wisdom is provided, let it subtly inform your empathy (don't quote directly)
- Ask AT MOST ONE clarifying question if critical context is missing
- Do NOT give advice or spiritual wisdom yet - just be present
- Keep response warm and conversational
- Focus on understanding, not solving
"""
        
        elif phase == ConversationPhase.GUIDANCE:
            return """
- Acknowledge what they've shared with compassion
- Name their emotional reality calmly and clearly
- CRITICAL: You MUST explicitly reference the provided scripture wisdom in your response
- Don't just quote the verse - EXPLAIN IT in simple English and CONNECT it to their specific struggle
- Example: "As the Bhagavad Gita says [quote], which means for your situation that..."
- Translate the Sanskrit concepts (like 'sthitaprajna' or 'karma') into their daily reality
- Offer ONE practical spiritual practice derived from this wisdom
- NO additional questions - provide clarity and wisdom instead
"""
        
        else:  # CLOSURE
            return """
- Reassure them they've been heard
- Reduce any pressure or expectations
- Hold space for silence - they don't need to say more
- Offer gentle closing words of support
- NO questions whatsoever
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
        user_id: str = "default_user"
    ) -> str:
        """
        Generate context-aware spiritual companion response.
        
        Args:
            query: User's current message
            context_docs: Retrieved scripture documents (optional)
            language: Response language (default: "en")
            conversation_history: Previous messages in conversation
            user_id: User identifier for context
            
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
            
            # Detect conversation phase
            phase = self._detect_phase(query, context)
            
            logger.info(f"Phase: {phase.value} | Context: family_support={context.family_support}, "
                       f"support_quality={context.support_quality} | RAG docs: {len(context_docs) if context_docs else 0}")
            
            # Build prompt WITH scripture context from RAG
            prompt = self._build_prompt(query, conversation_history, phase, context, context_docs)
            
            # Generate response from Gemini
            response = self.client.models.generate_content(
               model="gemini-2.0-flash",
               contents=prompt,
            )

            
            if not response or not response.text:
                logger.error("Empty response from Gemini")
                return "I'm here with you. You don't have to carry this alone."

            cleaned_response = clean_response(response.text)
            return cleaned_response
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return "I'm here with you. You don't have to carry this alone."


# --------------------------------------------------
# Singleton Instance
# --------------------------------------------------

_llm_service = None

def get_llm_service(api_key: Optional[str] = None) -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService(api_key)
    return _llm_service
