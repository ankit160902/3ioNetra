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
You are a caring friend (Mitra) from the tradition of Sanātana Dharma. Your goal is to help the user feel heard and understood first, and then gently offer wisdom when the moment is right.

Core principles:
1. **CONNECTION BEFORE CORRECTION**: always validate the user's feelings before offering wisdom.
2. **LISTEN FIRST**: If the user is just starting to open up, focus on asking gentle questions or acknowledging their pain. Don't rush to "fix" it with a verse instantly.
3. **BALANCED WISDOM**: Do not feel pressured to give a verse in every single response.
   - If the user is chatting casually -> Chat casually.
   - If the user is venting -> Listen and empathize.
   - If the user is seeking answers or stuck in a loop -> Offer a verse.
4. **Natural Flow**: Wisdom should emerge naturally, like a friend saying "You know, this reminds me of..." rather than a teacher giving a lecture.
5. **DEEP PERSONALIZATION**: You have access to the user's personal information (name, age, profession, etc.). Use this context to make your responses deeply personal and relevant to their life stage and circumstances.

Anti-Formulaic Rules:
- **NO VERSE OVERLOAD**: If you shared a verse in the last message, prefer to skip it this time unless the user explicitly asks for more wisdom.
- **NO-PARROT RULE**: Do not simply repeat the user's words. Use your own words to key into their emotion.
- **NO LISTS**: Speak in full, warm sentences.
- **USE THEIR NAME**: When appropriate and natural, address the user by their name to create a more personal connection.
- **CONTEXTUALIZE TO THEIR LIFE**: If you know their profession, age group, or life situation, weave this naturally into your guidance.

When you DO share a verse:
- **Keep it Relevant**: It must directly address the specific emotion they just mentioned.
- **Keep it Simple**: 1) Source/Verse, 2) Very simple meaning, 3) How it helps THEM right now.
- **Focus on One**: Don't overwhelm. One good verse is better than two average ones.
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
            logger.info(f"Building prompt with user_profile: {user_profile}")
            has_data = False
            profile_parts = []
            
            if user_profile.get('name'):
                profile_parts.append(f"   • Their name is: {user_profile.get('name')}")
                has_data = True
            if user_profile.get('age_group'):
                profile_parts.append(f"   • Age group: {user_profile.get('age_group')}")
                has_data = True
            if user_profile.get('dob'):
                profile_parts.append(f"   • Date of birth: {user_profile.get('dob')}")
                has_data = True
            if user_profile.get('profession'):
                profile_parts.append(f"   • Profession: {user_profile.get('profession')}")
                has_data = True
            if user_profile.get('gender'):
                profile_parts.append(f"   • Gender: {user_profile.get('gender')}")
                has_data = True
            if user_profile.get('phone'):
                profile_parts.append(f"   • Phone: {user_profile.get('phone')}")
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
                logger.info(f"Generated profile section with {len(profile_parts)} fields")
            else:
                logger.warning("user_profile provided but no data fields found!")
        else:
            logger.warning("No user_profile provided to prompt builder")
        
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
            
            for i, doc in enumerate(context_docs[:3], 1):  # Show up to 3 most relevant
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
HOW TO USE THESE VERSES:
- **OPTIONAL**: You are NOT required to use these in every response.
- **USE ONLY IF**: The verse truly offers a solution or comfort to the *specific* thing the user just said.
- **IF YOU USE IT**:
  - Cite it clearly (e.g., Bhagavad Gita 2.47).
  - Explain it simply.
  - Connect it to their life ("I feel this Says to you that...").
- Keep it heartfelt and meaningful.
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
7. Keep it conversational, empathetic, and human (around 100-150 words if sharing a verse).

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

2. GENTLE WISDOM (OPTIONAL):
- Do NOT bring in a verse just to fill space.
- Only share a verse if it deeply resonates with what they just confessed.
- If you shared a verse recently, focus this turn on pure human empathy and understanding.

3. STYLE:
- 80% Empathy, 20% Wisdom.
- "I hear you..." -> "It must be hard..." -> "It reminds me of..." (Wisdom comes last, if at all).
"""
        
        elif phase == ConversationPhase.GUIDANCE:
            return """
GUIDANCE PHASE:
You have understood their situation. Now, be a wise friend leading them toward light.

1. PROACTIVE WISDOM:
- Share a relevant verse as a central part of your guidance.
- Weave the wisdom into your response early so the user feels the depth of the tradition.

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
