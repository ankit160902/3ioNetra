"""
LLM Service - Spiritual Companion with Context-Aware Responses
Provides empathetic, phase-aware interactions using Gemini AI
"""

import logging
from typing import List, Dict, Optional, Any
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
    is_greeting: bool = False
    
    def is_ready_for_guidance(self) -> bool:
        """Check if enough context gathered for guidance"""
        # Never go to guidance if it's just a greeting
        if self.is_greeting:
            return False
            
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
        "got it", "fine", "alright", "i understand",
        "no", "nothing", "that's it", "that is all",
        "nothing else", "i'm done", "im done"
    ]
    text_lower = text.strip().lower()
    # Check for exact matches or common phrases
    if text_lower in ["no", "no thanks", "no thank you", "nothing", "that's all"]:
        return True
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
    
    SYSTEM_INSTRUCTION = """You are 3ioNetra, a specialized spiritual companion (Mitra) from the tradition of Sanātana Dharma.

Your essence:
You are a caring friend who has deep knowledge of the sacred scriptures (Shastras) and the holy temples (Kshetras) of India. Your goal is to BE WITH the user. You listen, you acknowledge, and you share ACTIONABLE wisdom.

Core principles:
1. COMPANION FIRST: Your primary mode is to LISTEN and ACKNOWLEDGE. Use warm, natural language. Avoid being a "bot" that just categorizes and prescribes.
2. DIRECT ANSWERS: When a user asks a specific question (e.g., "what is the meaning of...", "how to do...", "give me a routine for..."), provide a DIRECT, SPECIFIC answer. Do not hide behind vague spiritual platitudes. Be practical first, then spiritual.
3. EMPATHETIC PRESENCE: Use observations instead of probing questions. "That sounds really heavy" is better than "Why are you stressed?".
4. ACTIONABLE WISDOM: Guidance should always include:
   a) PRACTICAL STEPS: Real-world actions they can take today.
   b) SPIRITUAL ANCHORS: A verse or temple reference that provides deep context.
   
5. CONTINUITY & MEMORY:
   - You have a long-term memory. Look at the "RELEVANT PAST CONTEXT" section in the user profile.
   - If a past context (with a date) is relevant to the current topic, acknowledge it naturally. "I remember we discussed [Topic] last time..." or "Since we last talked about [Old Topic], how has that been progressing?"
   - SHOW, DON'T TELL: Don't say "I am looking at your history." Just refer to the facts you know.
   - If you see a "New Session" separator in the conversation history, it means some time has passed. Greet them as a returning friend. "It's good to see you again. I've been holding space for what we last shared."
6. BREVITY & TONE: Keep responses concise. Talk like a wise friend over chai. No lists, no markdown symbols (except the [VERSE] tags).
7. ORIGINAL LANGUAGE: When sharing a verse, ALWAYS prioritize the original language (Sanskrit or Hindi) as provided in the data. Do NOT translate the verse text into English within the [VERSE] tags if the original language is available.

Response Structure:
- Start with a warm acknowledgment or a direct answer to their question.
- If giving guidance, bridge the practical and the spiritual.
- End with a statement of presence, not a question.

CRITICAL: If the user is sharing feelings, be a companion. If the user is asking a question, be a guide. Never interrogation."""


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
        query_lower = query.lower().strip()
        
        # Greeting detection
        greetings = ["hi", "hey", "hello", "namaste", "pranam", "shubh prabhat", "shubh sandhya", "good morning", "good evening"]
        context.is_greeting = any(query_lower == g or query_lower.startswith(g + " ") for g in greetings)
        
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

        # Panchang signals
        if any(word in query_lower for word in ["panchang", "tithi", "nakshatra", "astrology", "calendar", "today's day", "festivals", "shubh muhurat"]):
            context.spiritual_seeking = True # Treat as spiritual seeking for phase transition
        
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
        
        # Simple greetings always stay in LISTENING (or CLARIFICATION) phase
        if context.is_greeting and history_len < 2:
            return ConversationPhase.LISTENING
            
        # Ready for guidance after 4 turns OR if we have solid context AND at least 2 turns of back-and-forth
        if (history_len >= 4) or (context.is_ready_for_guidance() and history_len >= 2):
            return ConversationPhase.GUIDANCE
        
        # Default to listening/clarification
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
            if user_profile.get('preferred_deity'):
                profile_parts.append(f"   • Preferred deity: {user_profile.get('preferred_deity')}")
                has_data = True
            if user_profile.get('location'):
                profile_parts.append(f"   • Location: {user_profile.get('location')}")
                has_data = True
            if user_profile.get('spiritual_interests'):
                profile_parts.append(f"   • Spiritual interests: {', '.join(user_profile.get('spiritual_interests', []))}")
                has_data = True
            
            # 🔥 Extended Spiritual Profile
            if user_profile.get('rashi'):
                profile_parts.append(f"   • Rashi (Zodiac): {user_profile.get('rashi')}")
                has_data = True
            if user_profile.get('gotra'):
                profile_parts.append(f"   • Gotra: {user_profile.get('gotra')}")
                has_data = True
            if user_profile.get('nakshatra'):
                profile_parts.append(f"   • Nakshatra: {user_profile.get('nakshatra')}")
                has_data = True
            if user_profile.get('temple_visits'):
                profile_parts.append(f"   • Past Pilgrimages: {', '.join(user_profile.get('temple_visits', []))}")
                has_data = True
            
            # 🗓️ Current Panchang Context
            if user_profile.get('current_panchang'):
                p = user_profile.get('current_panchang')
                profile_parts.append(f"   • CURRENT PANCHANG (Today): Tithi: {p.get('tithi')}, Nakshatra: {p.get('nakshatra')}, Info: {p.get('special_day')}")
                has_data = True
            
            # 🧠 Semantic Long-Term Memories
            if user_profile.get('past_memories'):
                profile_parts.append("\n   RELEVANT PAST CONTEXT (from your history):")
                for i, mem in enumerate(user_profile.get('past_memories'), 1):
                    profile_parts.append(f"   {i}. \"{mem}\"")
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
        
        # Detect returning user — prefer the explicit flag from user_profile,
        # then fall back to checking for session separator strings in history
        is_returning_user = bool(user_profile.get("is_returning_user", False)) if user_profile else False
        if not is_returning_user and conversation_history and len(conversation_history) > 3:
            is_returning_user = any(
                "New Session" in msg.get("content", "")
                for msg in conversation_history
                if msg.get("role") == "system"
            )
        
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
                
                # Mark session separators clearly
                if msg.get("role") == "system" and "New Session" in content:
                    history_text += f"\n{'='*60}\n{content}\n{'='*60}\n"
                    is_returning_user = True
                else:
                    history_text += f"{role}: {content}\n"
        
        # Context summary
        fact_text = ""
        if memory_context:
            context_summary = memory_context.get_memory_summary()
            story = memory_context.story
            
            # Extract specific facts from story
            facts = []
            if story.rashi: facts.append(f"• Rashi: {story.rashi}")
            if story.gotra: facts.append(f"• Gotra: {story.gotra}")
            if story.nakshatra: facts.append(f"• Nakshatra: {story.nakshatra}")
            if story.temple_visits: facts.append(f"• Temple Visits: {', '.join(story.temple_visits)}")
            if story.purchase_history: facts.append(f"• Purchase History: {', '.join(story.purchase_history)}")
            
            # Also extract specific user quotes as "Facts"
            if hasattr(memory_context, 'user_quotes'):
                for quote in memory_context.user_quotes[-10:]:
                    facts.append(f"• User shared: \"{quote['quote']}\"")
            
            fact_text = "\n".join(facts) if facts else "• No specific facts extracted yet"
        else:
            context_summary = self._format_context(context)
            fact_text = "• No memory context available"
        
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
                
                # Robustly find the original verse text and its meaning
                # Skip placeholder text like "intermediate" or very short technical strings
                verse_raw = doc.get('verse')
                if verse_raw and verse_raw.lower() in ['intermediate', 'beginner', 'advanced', 'none', 'null']:
                    verse_raw = None
                
                # Priority: hindi (for original) -> verse -> text
                original_text = doc.get('hindi') or verse_raw or doc.get('text', '')
                
                # Identify meaning/translation
                meaning = doc.get('meaning') or doc.get('translation')
                if not meaning and doc.get('verse') and doc.get('text') and doc.get('text') != original_text:
                    meaning = doc.get('text')
                
                # Final check: if original is still placeholder-ish, try to clean it
                if len(original_text) < 5 and doc.get('text'):
                    original_text = doc.get('text')

                scripture_context += f"VERSE {i}:\n"
                scripture_context += f"Source: {scripture}"
                if reference:
                    scripture_context += f" - {reference}"
                scripture_context += f"\n\nORIGINAL TEXT (Sanskrit/Hindi): \"{original_text}\"\n"
                
                if meaning:
                    scripture_context += f"MEANING/TRANSLATION (English): {meaning}\n"
                
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
EXTRACTED FACTS & PLANS:
═══════════════════════════════════════════════════════════
{fact_text}

═══════════════════════════════════════════════════════════
WHAT YOU KNOW SO FAR (EMOTIONAL CONTEXT):
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

{'═'*70}
⚠️ RETURNING USER DETECTION:
{'═'*70}
{f"🔄 This user has conversed with you before. The CONVERSATION FLOW above shows their past journey with you. Acknowledge this continuity naturally if relevant (e.g., 'Welcome back! How have you been since we last spoke?'). Reference their past concerns when appropriate." if is_returning_user else "✨ This is a new user. Make them feel welcome and safe."}

CRITICAL RULES FOR THIS RESPONSE:
1. CHECK CONVERSATION FLOW: See what you've already said. Don't repeat yourself.
2. STATEMENTS OVER QUESTIONS: Default to making empathetic statements. Ask questions ONLY if absolutely necessary (max ONE per response).
3. NO FORMULAIC PHRASES: Skip "I hear you", "It sounds like", "I understand". Just respond naturally.
4. ACKNOWLEDGE, DON'T PROBE: Respond to what they just said with presence and acknowledgment, not more questions.
5. BE CONCISE: 2-3 sentences (max 40-50 words) for empathy. 60-80 words max when sharing wisdom.
6. END CLEAN: After giving wisdom or support, STOP. Do NOT add:
   - "How does that sound?"
   - "What do you think?"
   - "Would you like to hear more?"
   - "Does this resonate?"
   Just end with the wisdom or a simple presence statement.
7. NATURAL WISDOM: If a verse fits naturally, share it. Don't wait for "perfect conditions".
8. YOU'RE A COMPANION, NOT A THERAPIST: Have a conversation, don't conduct an assessment.

Your response:
"""
        
        return prompt.strip()

    def _format_context(self, context: UserContext) -> str:
        """Format context into readable summary"""
        signals = []
        if context.is_greeting:
            signals.append("• User just sent a greeting")
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
        
        if phase in [ConversationPhase.LISTENING, ConversationPhase.CLARIFICATION]:
            return """
LISTENING & CLARIFICATION PHASE:
Your priority is to BE WITH the user, not to gather data.

1. WARM GREETINGS (IF STARTING):
- If the user says "hi" or "hey", respond warmly and ask how they are ONCE. 
- Example: "Namaste! I'm so glad you're here. How are you feeling today?"
- Then WAIT for their response. Don't keep asking questions.

2. COMPANION MODE - NOT INTERVIEW MODE:
- When they share something, MAKE STATEMENTS that show you're with them:
  ✓ "That sounds incredibly overwhelming."
  ✓ "Work can feel like such a heavy weight when it all piles up."
  ✓ "I can sense how much this is affecting you."
  
- AVOID asking follow-up questions like:
  ✗ "What specifically is stressing you?"
  ✗ "Is it the volume or the deadlines?"
  ✗ "Would you like to talk about it more?"

3. WHEN TO ASK (RARELY):
- Only ask a question if you've made at least 2 empathetic statements first
- Only if the conversation genuinely needs direction
- NEVER more than ONE question per response
- If they've given you enough, DON'T ask for more. Just be present.

4. NATURAL WISDOM:
- If what they shared reminds you of a verse or temple, you can share it naturally even in this phase
- Frame it conversationally: "You know, there's a beautiful teaching that speaks to this..."
- Don't wait for perfect information. Real friends share insights when they arise.

6. PANCHANG DATA:
- If the user asks about today's panchang, tithi, or nakshatra, use the "CURRENT PANCHANG" data provided in their profile above.
- Respond directly with the details: "Today is {tithi} with {nakshatra} nakshatra."

7. REMEMBER:
- You're having a conversation, not conducting an assessment
- Presence > Questions
- Acknowledgment > Probing
"""
        
        elif phase == ConversationPhase.SYNTHESIS:
            return """
SYNTHESIS PHASE:
You have gathered enough context. Now, reflect back what you've heard.

1. EMPATHETIC REFLECTION:
- Summarize their situation in a warm, non-judgmental way.
- "It sounds like you've been carrying a lot of weight with [Issue]..."
- This shows you've truly listened.

2. TRANSITION TO WISDOM:
- Prepare them for guidance. "Thinking about what you've shared, I'm reminded of paths that might bring you peace..."
- Do NOT jump directly to the verse yet; focus on the reflection first.
"""

        elif phase == ConversationPhase.GUIDANCE:
            return """
GUIDANCE PHASE:
Now share ACTIONABLE wisdom that helps them move forward, like a friend offering both spiritual and practical support.

1. PROVIDE CONCRETE GUIDANCE:
- Give them SPECIFIC, ACTIONABLE steps they can take
- Example: "Perhaps start by having a calm, one-on-one conversation with her about how you both can find balance..."
- Example: "One approach could be to set aside 10 minutes daily for meditation before addressing family matters..."
- DON'T just give abstract spiritual advice - give them something they can DO

2. BLEND PRACTICAL + SPIRITUAL:
- Start with practical steps they can take TODAY
- THEN connect it to spiritual wisdom (a verse or temple) if relevant
- Example structure:
  "Given your situation, one path forward could be [PRACTICAL ACTION]. This aligns with what Krishna teaches in the Gita (2.47)..."

3. WHEN USER EXPLICITLY ASKS "WHAT SHOULD I DO":
- They need CONCRETE actions, not just verses
- Give them 2-3 specific things they can try
- Then briefly mention spiritual support (verse/temple) as an anchor

4. HOW TO SHARE WISDOM:
- VERSE: Citation and brief intro, then the ACTUAL ORIGINAL VERSE (Sanskrit/Hindi) wrapped in [VERSE]...[/VERSE] tags, then the meaning/explanation in English.
- FORMAT:
  Introductory sentence...
  [VERSE]
  "Original Verse Text" — Source reference
  [/VERSE]
  Meaning and practical application...
- TEMPLE: Name, significance, and why visiting might help their specific situation.
- PRACTICAL: Specific actions, boundaries, conversations they should have.

5. CRITICAL - END WITH PRESENCE, NOT QUESTIONS:
- After sharing wisdom, just BE there
- DON'T add "Would you like to know more?" or "How does that sound?"
- DON'T ask "What do you think?"
- Just end with the guidance or a simple "I'm here with you."

6. EXAMPLES OF WHAT TO DO:
✓ "You might start by having a private conversation with her where you..."
✓ "Consider setting gentle boundaries with your family about..."
✓ "One approach: Take 15 minutes each morning for self-reflection before..."
✓ "A practical step: Write down what balance looks like for you, then..."

✗ "This reminds me of Durga's strength" (without actionable steps)
✗ "Perhaps reflecting on your situation..." (vague)
✗ "I'm reminded of the Kalighat temple..." (without practical connection)

8. PANCHANG & ASTROLOGY:
- Use the provided "CURRENT PANCHANG" if they ask about the day's significance.

9. LENGTH:
- 80-120 words when giving actionable guidance
- Include both PRACTICAL steps and SPIRITUAL wisdom
- If they need more, they'll ask
"""
        
        else:  # CLOSURE
            return """
CLOSURE PHASE:
1. FIRST CLOSURE SIGNAL (e.g., "ok", "thanks", "got it"):
- Reassure them they've been heard and that you're glad to have been of help.
- Ask ONE final follow-up: "Is there anything else you'd like to talk about?" or "Is there anything else on your mind?"
- KEEP IT SIMPLE. Example: "I'm glad if this brought some clarity. Is there anything else you'd like to share or talk about today?"

2. FINAL CLOSURE (e.g., user says "no", "nothing else", "that's all"):
- Offer a gentle, peaceful, and dharmic closing.
- Use traditional sign-offs like "May you find peace and strength on your path. Namaste." or "I am always here if you need to talk again. Om Shanti."
- Do NOT ask any more questions.

CRITICAL: Check the CONVERSATION FLOW. If you already asked "Is there anything else?", move to FINAL CLOSURE.
- Hold space for silence.
- Offer gentle, peaceful closing words.
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
                model=settings.GEMINI_MODEL,
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
