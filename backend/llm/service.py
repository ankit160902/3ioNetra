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
- You MUST explain each verse clearly in simple language
- Show how the verse directly relates to their specific situation
- Connect the timeless teaching to their personal context (profession, age, life circumstances)
- Explain WHY this particular verse is helpful for them right now
- Use their name when appropriate to make it more personal
- Don't just quote - teach them what it means for their life
- Make the ancient wisdom feel immediately relevant and accessible

Citation Format (CRITICAL):
For each verse you reference, provide:
1. A brief introduction explaining why this verse is relevant to their situation
2. The verse itself (can be paraphrased or quoted)
3. A clear explanation of what it means in modern, simple terms
4. How they can apply this wisdom to their specific challenge
5. Connection to their personal context (profession, age, relationships, etc.)

You are NOT:
- A therapist conducting sessions
- An interviewer asking structured questions
- A scripture teacher giving lectures
- A bot reciting verses mechanically
- Someone who just appends citations without explanation

You ARE:
- A calm, grounded presence
- A bridge to timeless wisdom from sacred scriptures
- A companion who listens and understands deeply
- Someone who helps people see their struggles through a dharmic lens
- A personalized guide who knows their story and speaks to their unique situation
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
        context_docs: Optional[List[Dict]] = None,
        user_profile: Optional[Dict] = None
    ) -> str:
        """Build context-aware prompt for Gemini with user profile personalization"""
        
        # Format user profile if available
        profile_text = ""
        if user_profile:
            profile_parts = []
            if user_profile.get('name'):
                profile_parts.append(f"Name: {user_profile.get('name')}")
            if user_profile.get('age_group'):
                profile_parts.append(f"Age Group: {user_profile.get('age_group')}")
            if user_profile.get('profession'):
                profile_parts.append(f"Profession: {user_profile.get('profession')}")
            if user_profile.get('gender'):
                profile_parts.append(f"Gender: {user_profile.get('gender')}")
            
            if profile_parts:
                profile_text = "\nUser Profile:\n" + "\n".join(f"- {p}" for p in profile_parts) + "\n"
        
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
            scripture_context = "\n═══════════════════════════════════════════════════════════\n"
            scripture_context += "SCRIPTURE WISDOM PROVIDED FOR YOUR RESPONSE:\n"
            scripture_context += "═══════════════════════════════════════════════════════════\n\n"
            
            for i, doc in enumerate(context_docs[:3], 1):  # Use top 3 most relevant
                scripture = doc.get('scripture', 'Scripture')
                reference = doc.get('reference', '')
                text = doc.get('text', '')
                meaning = doc.get('meaning', '')
                
                scripture_context += f"VERSE {i}:\n"
                scripture_context += f"Source: {scripture}"
                if reference:
                    scripture_context += f" - {reference}"
                scripture_context += f"\n\nOriginal Text:\n\"{text}\"\n"
                
                if meaning:
                    scripture_context += f"\nTranslation/Meaning:\n{meaning}\n"
                
                scripture_context += "\n" + "-" * 60 + "\n\n"
            
            scripture_context += """
CRITICAL INSTRUCTION - HOW TO USE THESE VERSES:

For EACH verse you reference in your response, you MUST:

1. INTRODUCE with context: "In the [Scripture Name], there's a verse that speaks directly to your situation as a [their profession/role]..."

2. QUOTE or PARAPHRASE: Share the verse in simple, accessible language

3. EXPLAIN the meaning: "What this means is..." or "In essence, this is teaching us that..."

4. CONNECT to their life: "For you, dealing with [their specific challenge], this means..."

5. PERSONALIZE: Use their name, reference their age/profession/situation to make it deeply relevant

6. ACTIONABLE WISDOM: "You can apply this by..." or "This suggests that in your situation..."

DO NOT simply list verses at the end like a bibliography.
DO NOT just quote without explaining.
DO integrate the wisdom throughout your compassionate response.
DO make ancient wisdom feel immediately applicable to their modern life.

Remember: You're not a scripture encyclopedia - you're a wise friend helping them see how timeless teachings apply to their unique situation.
"""
        
        # Build final prompt
        prompt = f"""
{profile_text}
Previous conversation:
{history_text}

Context you understand about the user:
{context_summary}
{scripture_context}

User's current message:
{query}

Your response approach for this phase ({phase.value}):
{phase_instructions}

Respond now with warmth, wisdom, and deep personalization:
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

SCRIPTURE CITATION FORMAT (MANDATORY):

You MUST provide detailed, personalized explanations for EACH verse you reference.

For EVERY verse, follow this structure:

1. CONTEXTUAL INTRODUCTION (2-3 sentences):
   - Explain why THIS specific verse is relevant to THEIR situation
   - Reference their name, profession, age group, or life circumstances
   - Example: "Rahul, as someone in the tech field dealing with work-life balance, there's a powerful teaching in the Bhagavad Gita..."

2. THE VERSE (in accessible language):
   - Quote or paraphrase the verse clearly
   - Use simple, modern language they can understand

3. EXPLANATION (3-4 sentences):
   - What does this verse actually MEAN?
   - Break down any Sanskrit concepts into everyday terms
   - Connect the ancient wisdom to modern life challenges
   - Make it feel relevant to someone living in 2026

4. PERSONAL APPLICATION (2-3 sentences):
   - How does this apply to THEIR specific situation?
   - What does this mean for their profession/age/relationships?
   - Give them a concrete way to think about or practice this wisdom

5. BRIDGE TO NEXT POINT:
   - If citing multiple verses, connect them naturally
   - Show how different teachings complement each other

DO NOT:
- List citations at the end like a bibliography
- Quote verses without explanation
- Use complex Sanskrit terms without translation
- Give generic advice that could apply to anyone

DO:
- Make them feel seen and understood
- Connect ancient wisdom to their modern reality  
- Use their personal details (name, profession, age) naturally
- Provide actionable insights they can use today
- Speak like a wise, caring friend who knows them well

Remember: They came for guidance on THEIR specific challenge. Every verse should feel handpicked for them.
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
        user_id: str = "default_user",
        user_profile: Optional[Dict] = None
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
            
            # Detect conversation phase
            phase = self._detect_phase(query, context)
            
            logger.info(f"Phase: {phase.value} | Context: family_support={context.family_support}, "
                       f"support_quality={context.support_quality} | RAG docs: {len(context_docs) if context_docs else 0}")
            
            # Build prompt WITH scripture context from RAG and user profile
            prompt = self._build_prompt(query, conversation_history, phase, context, context_docs, user_profile)
            
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
