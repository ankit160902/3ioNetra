"""
Companion Engine - The heart of empathetic conversation
Listens deeply, builds memory, and responds with genuine understanding
"""
from typing import Tuple, Optional, List, Dict
import logging
import json

from models.session import SessionState, SignalType
from models.memory_context import ConversationMemory

logger = logging.getLogger(__name__)

# Try to import Gemini
try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-generativeai not available")


# Mapping emotions to dharmic concepts for memory building
EMOTION_TO_CONCEPTS = {
    'anxiety': ['vairagya', 'surrender', 'present_moment', 'shraddha'],
    'sadness': ['impermanence', 'acceptance', 'karma', 'compassion'],
    'anger': ['kshama', 'ahimsa', 'viveka', 'shanti'],
    'confusion': ['viveka', 'dharma', 'guidance', 'clarity'],
    'fear': ['abhaya', 'shraddha', 'surrender', 'courage'],
    'hopelessness': ['shraddha', 'karma', 'divine_plan', 'hope'],
    'frustration': ['patience', 'acceptance', 'karma', 'perseverance'],
    'guilt': ['prayaschitta', 'forgiveness', 'dharma', 'redemption'],
    'loneliness': ['connection', 'seva', 'bhakti', 'sangha'],
    'stress': ['shanti', 'balance', 'present_moment', 'pranayama'],
    'overwhelm': ['surrender', 'one_step', 'simplicity', 'breath'],
    'grief': ['impermanence', 'acceptance', 'eternal_soul', 'compassion'],
}

# Life areas to relevant concepts
LIFE_AREA_TO_CONCEPTS = {
    'work': ['karma_yoga', 'nishkama_karma', 'svadharma', 'excellence'],
    'family': ['dharma', 'duty', 'love', 'patience', 'forgiveness'],
    'relationships': ['love', 'attachment', 'boundaries', 'communication'],
    'health': ['body_temple', 'balance', 'healing', 'acceptance'],
    'spiritual': ['sadhana', 'devotion', 'self_inquiry', 'surrender'],
    'financial': ['artha', 'contentment', 'effort', 'trust'],
    'career': ['svadharma', 'purpose', 'growth', 'patience'],
}


class CompanionEngine:
    """
    The companion that listens, understands, and builds memory.
    This is the core intelligence that makes conversations feel personal.
    """

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.model = None
        self.available = False

        if api_key and GEMINI_AVAILABLE:
            try:
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
                self.available = True
                logger.info("CompanionEngine initialized with Gemini")
            except Exception as e:
                logger.error(f"Failed to init CompanionEngine: {e}")
        else:
            logger.info("CompanionEngine using template responses")

    async def process_message(
        self,
        session: SessionState,
        user_message: str
    ) -> Tuple[str, bool]:
        """
        Process user message as a companion would:
        1. Listen and understand
        2. Update memory context
        3. Decide if more understanding is needed
        4. Generate empathetic response

        Returns:
            (response_text, is_ready_for_wisdom)
        """
        memory = session.memory
        turn = session.turn_count

        # Step 1: Analyze the message and update memory
        await self._analyze_and_remember(session, user_message, turn)

        # Step 2: Check if we have enough understanding
        is_ready = self._assess_readiness(session)

        if is_ready:
            logger.info(f"Session {session.session_id}: Ready for wisdom (readiness={memory.readiness_for_wisdom:.2f})")
            return "", True

        # Step 3: Generate empathetic follow-up
        response = await self._generate_companion_response(session, user_message)

        return response, False

    async def _analyze_and_remember(
        self,
        session: SessionState,
        message: str,
        turn: int
    ) -> None:
        """Deeply analyze the message and update memory context"""
        memory = session.memory

        if not self.available or not self.model:
            # Fallback: basic analysis
            self._basic_analysis(memory, message, turn)
            return

        try:
            # Build context of what we already know
            existing_context = memory.get_memory_summary() if turn > 1 else "This is the user's first message."

            prompt = f"""You are a compassionate companion analyzing a user's message to understand their situation deeply.

EXISTING UNDERSTANDING:
{existing_context}

USER'S NEW MESSAGE (Turn {turn}):
"{message}"

Analyze this message and extract insights. Return JSON:
{{
    "primary_concern": "main issue in simple words (if newly revealed or clarified)",
    "emotional_state": "their current emotion (anxiety, sadness, anger, confusion, fear, grief, frustration, etc.)",
    "emotional_intensity": "low/moderate/high",
    "trigger_event": "what caused this (if mentioned)",
    "duration": "how long they've dealt with this (if mentioned)",
    "life_area": "work/family/relationships/health/spiritual/financial/career (if clear)",
    "significant_quote": "most meaningful phrase from their message (verbatim)",
    "quote_significance": "why this quote matters",
    "underlying_fear": "what they might be afraid of (infer carefully)",
    "unmet_need": "what they seem to be seeking (comfort/understanding/guidance/validation/etc.)",
    "observation": "one insightful observation about the user",
    "topics_mentioned": ["list", "of", "topics"],
    "understanding_update": "2-3 sentence summary of what we now understand about this person",
    "user_age_group": "infer from context if possible: teen/young_adult/middle_aged/senior (leave empty if unclear)",
    "user_profession": "infer if mentioned: student/professional/business/parent/homemaker/retired/etc (leave empty if unclear)",
    "user_life_situation": "infer if mentioned: single/married/parent/caregiver/divorced/etc (leave empty if unclear)",
    "user_life_stage": "infer if clear: education/early_career/mid_career/family_raising/retirement (leave empty if unclear)",
    "user_gender": "only if user explicitly mentions or clearly implies (leave empty if unclear)"
}}

Only include fields that are clearly present or can be reasonably inferred. Be empathetic and insightful.
For demographics (age_group, profession, life_situation, life_stage, gender), only populate if the user has clearly mentioned or strongly implied it."""

            response = await self.model.generate_content_async(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.4,
                    max_output_tokens=500,
                )
            )

            # Parse response
            text = response.text.strip()
            if text.startswith('```'):
                lines = text.split('\n')
                text = '\n'.join(lines[1:-1])
                if text.startswith('json'):
                    text = text[4:].strip()

            analysis = json.loads(text)

            # Update memory with analysis
            self._update_memory_from_analysis(memory, analysis, turn)

            logger.info(f"Memory updated for session, understanding: {memory.current_understanding[:100]}...")

        except Exception as e:
            logger.warning(f"LLM analysis failed, using basic: {e}")
            self._basic_analysis(memory, message, turn)

    def _update_memory_from_analysis(
        self,
        memory: ConversationMemory,
        analysis: Dict,
        turn: int
    ) -> None:
        """Update memory context from LLM analysis"""
        story = memory.story

        # Update story fields
        if analysis.get('primary_concern'):
            story.primary_concern = analysis['primary_concern']
        if analysis.get('emotional_state'):
            story.emotional_state = analysis['emotional_state']
            # Add relevant dharmic concepts
            emotion = analysis['emotional_state'].lower()
            for concept in EMOTION_TO_CONCEPTS.get(emotion, []):
                memory.add_relevant_concept(concept)

        if analysis.get('trigger_event'):
            story.trigger_event = analysis['trigger_event']
        if analysis.get('duration'):
            story.duration = analysis['duration']
        if analysis.get('life_area'):
            story.life_area = analysis['life_area']
            # Add life-area specific concepts
            for concept in LIFE_AREA_TO_CONCEPTS.get(analysis['life_area'], []):
                memory.add_relevant_concept(concept)

        # Store significant quote
        if analysis.get('significant_quote'):
            memory.add_user_quote(
                turn=turn,
                quote=analysis['significant_quote'],
                significance=analysis.get('quote_significance', '')
            )

        # Update deeper understanding
        if analysis.get('underlying_fear') and analysis['underlying_fear'] not in story.underlying_fears:
            story.underlying_fears.append(analysis['underlying_fear'])
        if analysis.get('unmet_need') and analysis['unmet_need'] not in story.unmet_needs:
            story.unmet_needs.append(analysis['unmet_need'])

        # Add observation
        if analysis.get('observation'):
            memory.add_observation(analysis['observation'])

        # Track topics
        for topic in analysis.get('topics_mentioned', []):
            memory.add_topic(topic)

        # Record emotion in arc
        if analysis.get('emotional_state'):
            memory.record_emotion(
                turn=turn,
                emotion=analysis['emotional_state'],
                intensity=analysis.get('emotional_intensity', 'moderate')
            )

        # Update current understanding
        if analysis.get('understanding_update'):
            memory.current_understanding = analysis['understanding_update']

        # Update demographic info (only if provided and not already set)
        if analysis.get('user_age_group') and not story.age_group:
            story.age_group = analysis['user_age_group']
        if analysis.get('user_profession') and not story.profession:
            story.profession = analysis['user_profession']
        if analysis.get('user_life_situation') and not story.life_situation:
            story.life_situation = analysis['user_life_situation']
        if analysis.get('user_life_stage') and not story.life_stage:
            story.life_stage = analysis['user_life_stage']
        if analysis.get('user_gender') and not story.gender:
            story.gender = analysis['user_gender']

        # Calculate readiness (more signals = more ready)
        self._calculate_readiness(memory)

    def _basic_analysis(self, memory: ConversationMemory, message: str, turn: int) -> None:
        """Basic rule-based analysis fallback"""
        message_lower = message.lower()
        story = memory.story

        # Detect emotion - expanded keyword mapping for better detection
        emotions = {
            # Anxiety/Worry
            'anxious': 'anxiety', 'anxiety': 'anxiety', 'worried': 'anxiety', 'worry': 'anxiety',
            'nervous': 'anxiety', 'uneasy': 'anxiety', 'uncertain': 'anxiety', 'unsure': 'anxiety',
            'afraid': 'fear', 'scared': 'fear', 'fear': 'fear', 'terrified': 'fear',
            'frightened': 'fear', 'panic': 'anxiety',
            
            # Sadness
            'sad': 'sadness', 'sadness': 'sadness', 'depressed': 'sadness', 'depression': 'sadness',
            'down': 'sadness', 'low': 'sadness', 'unhappy': 'sadness', 'grief': 'sadness',
            'grieving': 'sadness', 'heartbroken': 'sadness', 'devastated': 'sadness',
            'miserable': 'sadness', 'lost': 'confusion',
            
            # Anger/Frustration
            'angry': 'anger', 'anger': 'anger', 'furious': 'anger', 'rage': 'anger',
            'frustrated': 'frustration', 'frustration': 'frustration', 'irritated': 'frustration',
            'annoyed': 'frustration', 'stuck': 'frustration', 'fed up': 'frustration',
            
            # Confusion
            'confused': 'confusion', 'confusion': 'confusion', 'uncertain': 'confusion',
            'lost': 'confusion', 'don\'t know': 'confusion', 'unclear': 'confusion',
            'questioning': 'confusion',
            
            # Hopelessness
            'hopeless': 'hopelessness', 'hopelessness': 'hopelessness', 'pointless': 'hopelessness',
            'meaningless': 'hopelessness', 'give up': 'hopelessness', 'worthless': 'hopelessness',
            
            # Loneliness
            'lonely': 'loneliness', 'loneliness': 'loneliness', 'alone': 'loneliness',
            'isolated': 'loneliness', 'disconnected': 'loneliness', 'abandoned': 'loneliness',
            
            # Stress/Overwhelm
            'stressed': 'stress', 'stress': 'stress', 'pressure': 'stress',
            'overwhelmed': 'overwhelm', 'overwhelm': 'overwhelm', 'too much': 'overwhelm',
            'drowning': 'overwhelm', 'suffocating': 'overwhelm',
            
            # Grief
            'grief': 'grief', 'grieving': 'grief', 'loss': 'grief', 'lost': 'grief',
        }
        
        detected_emotion = None
        for keyword, emotion in emotions.items():
            if keyword in message_lower:
                detected_emotion = emotion
                break
        
        # If no direct emotion detected, infer from context
        if not detected_emotion:
            # Infer stress/overwhelm from life area conflicts
            if 'overwork' in message_lower or 'too much work' in message_lower or 'working too hard' in message_lower:
                detected_emotion = 'stress'
            # Infer stress from wanting peace but not having it
            elif 'no peace' in message_lower or 'lack of peace' in message_lower:
                detected_emotion = 'stress'
            # Infer overwhelm from not having time/balance
            elif 'no time' in message_lower or 'no break' in message_lower or 'no day off' in message_lower:
                detected_emotion = 'overwhelm'
            # Infer from unmet needs context
            elif ('peace' in message_lower or 'calm' in message_lower) and ('no' in message_lower or 'lack' in message_lower or 'missing' in message_lower):
                detected_emotion = 'stress'
        
        if detected_emotion:
            story.emotional_state = detected_emotion
            memory.record_emotion(turn, detected_emotion)
            for concept in EMOTION_TO_CONCEPTS.get(detected_emotion, []):
                memory.add_relevant_concept(concept)

        # Detect life area - more comprehensive
        areas = {
            # Work/Career
            'work': 'work', 'job': 'work', 'office': 'work', 'workplace': 'work',
            'boss': 'work', 'colleague': 'work', 'colleague': 'work', 'deadline': 'work',
            'project': 'work', 'meeting': 'work', 'performance': 'work',
            'career': 'career', 'promotion': 'career', 'professional': 'career',
            
            # Family
            'family': 'family', 'parent': 'family', 'parents': 'family', 'mother': 'family',
            'father': 'family', 'sibling': 'family', 'brother': 'family', 'sister': 'family',
            'home': 'family', 'household': 'family',
            
            # Relationships
            'relationship': 'relationships', 'relationships': 'relationships', 'partner': 'relationships',
            'marriage': 'relationships', 'married': 'relationships', 'husband': 'relationships',
            'wife': 'relationships', 'girlfriend': 'relationships', 'boyfriend': 'relationships',
            'breakup': 'relationships', 'dating': 'relationships',
            
            # Health
            'health': 'health', 'illness': 'health', 'sick': 'health', 'disease': 'health',
            'pain': 'health', 'suffering': 'health', 'physical': 'health', 'mental': 'health',
            'exercise': 'health', 'fitness': 'health',
            
            # Spiritual
            'spiritual': 'spiritual', 'spirituality': 'spiritual', 'faith': 'spiritual',
            'religion': 'spiritual', 'meditation': 'spiritual', 'prayer': 'spiritual',
            'purpose': 'spiritual', 'meaning': 'spiritual',
            
            # Financial
            'money': 'financial', 'financial': 'financial', 'debt': 'financial',
            'broke': 'financial', 'poor': 'financial', 'wealth': 'financial',
            'poverty': 'financial', 'income': 'financial', 'expense': 'financial',
        }
        
        for keyword, area in areas.items():
            if keyword in message_lower and not story.life_area:
                story.life_area = area
                memory.add_topic(area)
                for concept in LIFE_AREA_TO_CONCEPTS.get(area, []):
                    memory.add_relevant_concept(concept)
                break

        # Store the message as a quote if it's meaningful
        if len(message) > 20:
            memory.add_user_quote(turn, message[:150], "user's expression")

        # Simple understanding
        if not story.primary_concern and len(message) > 10:
            story.primary_concern = message[:200]

        # Try to detect if they mention duration
        duration_keywords = {
            'week': 'for about a week',
            'month': 'for about a month',
            'year': 'for about a year',
            'days': 'for several days',
            'hours': 'for a few hours',
            'long time': 'for a long time',
            'always': 'for as long as I can remember',
            'recently': 'recently',
            'since': 'for a while',
        }
        for keyword, duration in duration_keywords.items():
            if keyword in message_lower and not story.duration:
                story.duration = duration
                break

        # Basic demographic detection
        professions = {
            'student': 'student', 'studying': 'student', 'college': 'student',
            'university': 'student', 'school': 'student', 'exam': 'student',
            'engineer': 'professional', 'developer': 'professional', 'programmer': 'professional',
            'manager': 'professional', 'doctor': 'professional', 'teacher': 'professional',
            'professor': 'professional', 'lawyer': 'professional', 'accountant': 'professional',
            'executive': 'professional', 'analyst': 'professional', 'consultant': 'professional',
            'retired': 'retired', 'retirement': 'retired',
            'business': 'business', 'entrepreneur': 'business', 'owner': 'business',
            'startup': 'business',
            'homemaker': 'homemaker', 'housewife': 'homemaker', 'househusband': 'homemaker',
        }
        for keyword, profession in professions.items():
            if keyword in message_lower and not story.profession:
                story.profession = profession
                break

        life_situations = {
            'married': 'married', 'husband': 'married', 'wife': 'married', 'spouse': 'married',
            'wedding': 'married',
            'single': 'single', 'unmarried': 'single',
            'divorced': 'divorced', 'divorce': 'divorced', 'separation': 'divorced',
            'kid': 'parent', 'kids': 'parent', 'children': 'parent', 'child': 'parent',
            'son': 'parent', 'daughter': 'parent', 'parenting': 'parent',
            'taking care': 'caregiver', 'caregiver': 'caregiver', 'caring for': 'caregiver',
        }
        for keyword, situation in life_situations.items():
            if keyword in message_lower and not story.life_situation:
                story.life_situation = situation
                break

        # Try to identify underlying fears or needs
        if 'afraid' in message_lower or 'fear' in message_lower and not story.underlying_fears:
            story.underlying_fears.append('unknown future')
        
        if 'need' in message_lower or 'want' in message_lower or 'wish' in message_lower:
            if 'help' in message_lower and 'help' not in story.unmet_needs:
                story.unmet_needs.append('support')
            if 'understand' in message_lower and 'understanding' not in story.unmet_needs:
                story.unmet_needs.append('understanding')
            if 'peace' in message_lower and 'peace' not in story.unmet_needs:
                story.unmet_needs.append('peace')
            if 'strength' in message_lower and 'strength' not in story.unmet_needs:
                story.unmet_needs.append('strength')


        self._calculate_readiness(memory)

    def _calculate_readiness(self, memory: ConversationMemory) -> None:
        """
        Calculate how ready we are to offer wisdom.
        We need DEEP understanding, not just surface-level signals.

        Readiness is based on:
        - Understanding WHAT they're going through (primary concern)
        - Understanding HOW they feel (emotional state)
        - Understanding WHY this happened (trigger/cause)
        - Understanding the IMPACT (life area, duration)
        - Understanding their DEEPER needs (fears, what they seek)
        """
        score = 0.0
        story = memory.story

        # ESSENTIAL: Primary concern clearly articulated (0.2)
        if story.primary_concern and len(story.primary_concern) > 30:
            score += 0.2

        # ESSENTIAL: Emotional state identified (0.15)
        if story.emotional_state:
            score += 0.15

        # IMPORTANT: What triggered/caused this (0.15)
        if story.trigger_event:
            score += 0.15

        # IMPORTANT: How long they've been dealing with this (0.1)
        if story.duration:
            score += 0.1

        # CONTEXT: Which area of life is affected (0.1)
        if story.life_area:
            score += 0.1

        # DEPTH: Understanding their fears (0.1)
        if story.underlying_fears:
            score += 0.1

        # DEPTH: Understanding what they need/seek (0.1)
        if story.unmet_needs:
            score += 0.1

        # DEPTH: Rich context from multiple quotes (0.1)
        if len(memory.user_quotes) >= 3:
            score += 0.1

        memory.readiness_for_wisdom = min(score, 1.0)

    def _assess_readiness(self, session: SessionState) -> bool:
        """
        Decide if we have DEEP ENOUGH understanding to offer wisdom.

        The companion should ask as many questions as needed to truly understand.
        We only transition when we have comprehensive understanding.
        
        For demo/POC mode (without LLM), we use very lenient thresholds to prevent
        endless questioning. The goal is empathy and guidance, not information gathering.
        """
        memory = session.memory
        turn = session.turn_count
        story = memory.story

        # Safety: Force transition at max turns (prevent infinite conversation)
        if turn >= session.max_clarification_turns:
            logger.info(f"Session {session.session_id}: Forcing transition at max turns ({turn})")
            return True

        # For demo/POC mode (no LLM): VERY lenient thresholds
        # The goal is to move from listening to wisdom, not to stay in questions forever
        if not self.available:
            # Early transition at turn 3: if we have enough context, provide wisdom
            # This prevents endless question loops
            if turn >= 3:
                # What do we know?
                has_emotional_context = bool(story.emotional_state)
                has_concern = bool(story.primary_concern) and len(story.primary_concern) > 10
                has_life_area = bool(story.life_area)  # Work, family, health, etc.
                has_at_least_one_quote = len(memory.user_quotes) >= 1
                has_unmet_need = bool(story.unmet_needs)  # Peace, understanding, support, etc.
                
                # Criteria for transition at turn 3+:
                # Option A: Have emotional understanding + some concern + (life area or unmet need)
                if has_emotional_context and has_concern and (has_life_area or has_unmet_need):
                    logger.info(
                        f"Session {session.session_id}: Ready for wisdom (DEMO MODE - EARLY) "
                        f"(turn={turn}, emotion='{story.emotional_state}', "
                        f"area='{story.life_area}', concern='{story.primary_concern[:40]}...')"
                    )
                    return True
                
                # Option B: Have clear concern about a life area, even if emotion inference isn't perfect
                if has_concern and has_life_area and has_at_least_one_quote:
                    logger.info(
                        f"Session {session.session_id}: Ready for wisdom (DEMO MODE - CONTEXT) "
                        f"(turn={turn}, area='{story.life_area}', "
                        f"concern='{story.primary_concern[:40]}...')"
                    )
                    return True

        # Original strict requirements for full LLM mode
        # 1. Must have a clear understanding of the primary concern (not just a few words)
        has_clear_concern = bool(story.primary_concern and len(story.primary_concern) > 50)

        # 2. Must know their emotional state
        has_emotion = bool(story.emotional_state)

        # 3. Must understand what triggered this OR which life area is affected
        has_context = bool(story.trigger_event) or bool(story.life_area)

        # 4. Must have some understanding of duration OR underlying fears/needs
        has_depth = bool(story.duration) or bool(story.underlying_fears) or bool(story.unmet_needs)

        # 5. Must have collected enough of their words to understand nuance (at least 3 meaningful exchanges)
        has_enough_context = len(memory.user_quotes) >= 3

        # All conditions must be met (or readiness score must be very high)
        all_essentials = all([has_clear_concern, has_emotion, has_context])
        has_good_depth = has_depth and has_enough_context

        # Need high readiness score (0.8+) AND all essentials AND good depth
        if memory.readiness_for_wisdom >= 0.8 and all_essentials and has_good_depth:
            logger.info(
                f"Session {session.session_id}: Ready for wisdom (FULL MODE) "
                f"(readiness={memory.readiness_for_wisdom:.2f}, turn={turn}, "
                f"concern='{story.primary_concern[:40]}...', emotion='{story.emotional_state}', "
                f"trigger='{story.trigger_event or 'N/A'}', quotes={len(memory.user_quotes)})"
            )
            return True

        # Not ready yet - log what's missing for debugging
        if turn >= 3:
            missing = []
            if not has_clear_concern:
                missing.append("clear_concern")
            if not has_emotion:
                missing.append("emotion")
            if not has_context:
                missing.append("context")
            if not has_depth:
                missing.append("depth")
            if not has_enough_context:
                missing.append(f"quotes({len(memory.user_quotes)}/3)")
            logger.debug(f"Session {session.session_id}: Not ready yet, missing: {missing}, readiness={memory.readiness_for_wisdom:.2f}")

        return False

        # 1. Must have a clear understanding of the primary concern (not just a few words)
        has_clear_concern = bool(story.primary_concern and len(story.primary_concern) > 50)

        # 2. Must know their emotional state
        has_emotion = bool(story.emotional_state)

        # 3. Must understand what triggered this OR which life area is affected
        has_context = bool(story.trigger_event) or bool(story.life_area)

        # 4. Must have some understanding of duration OR underlying fears/needs
        has_depth = bool(story.duration) or bool(story.underlying_fears) or bool(story.unmet_needs)

        # 5. Must have collected enough of their words to understand nuance (at least 3 meaningful exchanges)
        has_enough_context = len(memory.user_quotes) >= 3

        # All conditions must be met (or readiness score must be very high)
        all_essentials = all([has_clear_concern, has_emotion, has_context])
        has_good_depth = has_depth and has_enough_context

        # Need high readiness score (0.8+) AND all essentials AND good depth
        if memory.readiness_for_wisdom >= 0.8 and all_essentials and has_good_depth:
            logger.info(
                f"Session {session.session_id}: Ready for wisdom (FULL MODE) "
                f"(readiness={memory.readiness_for_wisdom:.2f}, turn={turn}, "
                f"concern='{story.primary_concern[:40]}...', emotion='{story.emotional_state}', "
                f"trigger='{story.trigger_event or 'N/A'}', quotes={len(memory.user_quotes)})"
            )
            return True

        # Not ready yet - log what's missing for debugging
        if turn >= 3:
            missing = []
            if not has_clear_concern:
                missing.append("clear_concern")
            if not has_emotion:
                missing.append("emotion")
            if not has_context:
                missing.append("context")
            if not has_depth:
                missing.append("depth")
            if not has_enough_context:
                missing.append(f"quotes({len(memory.user_quotes)}/3)")
            logger.debug(f"Session {session.session_id}: Not ready yet, missing: {missing}, readiness={memory.readiness_for_wisdom:.2f}")

        return False

    async def _generate_companion_response(
        self,
        session: SessionState,
        user_message: str
    ) -> str:
        """Generate an empathetic companion response that continues the conversation"""
        memory = session.memory
        turn = session.turn_count

        if not self.available or not self.model:
            return self._get_template_question(memory, turn)

        try:
            # What have we already asked?
            asked = ", ".join(memory.questions_asked) if memory.questions_asked else "nothing yet"

            # What do we still need to understand?
            needs = self._identify_gaps(memory)

            # Check if we need demographic info (only if not already known from registration)
            story = memory.story
            has_profile = bool(story.profession or story.age_group)
            needs_demographics = not has_profile and (not story.profession or not story.life_situation)
            demographic_instruction = ""
            if needs_demographics and turn >= 2 and 'profession' not in memory.questions_asked:
                demographic_instruction = """
IMPORTANT: To give personalized guidance, we need to understand their life context.
Naturally ask about their work/profession or life situation (e.g., "To better understand your situation, may I ask what you do - are you working, studying, or in another phase of life?")
"""

            # Build personalization context from known profile
            personalization_context = ""
            if story.age_group or story.profession or story.gender:
                profile_parts = []
                if story.profession:
                    profile_parts.append(f"They are a {story.profession}")
                if story.age_group:
                    age_desc = {
                        "teen": "teenager",
                        "young_adult": "young adult (20s-30s)",
                        "middle_aged": "middle-aged (40s-50s)",
                        "senior": "senior (60+)"
                    }.get(story.age_group, story.age_group)
                    profile_parts.append(f"a {age_desc}")
                if story.gender:
                    profile_parts.append(f"{story.gender}")
                personalization_context = f"""
USER PROFILE (from registration - use this to personalize your response):
{', '.join(profile_parts)}

PERSONALIZATION INSTRUCTIONS:
- Address them in a way appropriate for their age and profession
- Use examples and language that resonate with their life stage
- For young adults: reference career growth, finding purpose, modern life challenges
- For middle-aged: reference responsibilities, family, work-life balance, legacy
- For seniors: reference wisdom, acceptance, spiritual maturity, life reflection
- For students: reference studies, future, peer pressure, self-discovery
- For professionals: reference work stress, ambition, career challenges
- DO NOT ask about their profession or age - you already know this!
"""

            # Build user identification context
            user_context = ""
            if memory.user_id:
                user_context = f"""
USER IDENTIFICATION:
- Name: {memory.user_name or 'Friend'}
- User ID: {memory.user_id}
- Member since: {memory.user_created_at or 'recently'}

USE THEIR NAME IN YOUR RESPONSE: Address them as "{memory.user_name}" to show you truly know them.
"""

            prompt = f"""You are a compassionate spiritual companion having a heart-to-heart conversation.

{user_context}
WHAT WE KNOW ABOUT THIS PERSON:
{memory.get_memory_summary()}
{personalization_context}
CONVERSATION TURN: {turn}
QUESTIONS ALREADY EXPLORED: {asked}
WHAT WE STILL NEED TO UNDERSTAND: {needs}

USER JUST SAID: "{user_message}"
{demographic_instruction}
Generate a warm, empathetic response that:
1. FIRST: Acknowledge what they shared (show you truly heard them)
2. THEN: Ask ONE gentle question to understand them better

STYLE GUIDELINES:
- Be warm and genuine, like a caring friend
- Use their name naturally in the conversation (they are {memory.user_name})
- Use simple, conversational language that fits their age and profession
- Show you remember what they said earlier (reference their words)
- Don't be clinical or formal
- Don't offer advice yet - just listen and understand
- Keep response to 2-3 sentences max
- End with a gentle question
- NEVER ask about profession, age, or gender - you already know this from their profile!
- NEVER assume things the user hasn't told you (like family, friends, etc.)

Focus on understanding: {needs}

Example tones:
- "I hear that... Can you tell me more about..."
- "That sounds really difficult... What has that been like for you?"
- "It makes sense you'd feel that way... How long have you been carrying this?"

Return ONLY the response text, no JSON or formatting."""

            response = await self.model.generate_content_async(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=200,
                )
            )

            response_text = response.text.strip()

            # Track what we're asking about
            for need in needs.split(','):
                need = need.strip().lower()
                if need and need not in memory.questions_asked:
                    memory.mark_question_asked(need)
                    break

            return response_text

        except Exception as e:
            logger.warning(f"LLM response generation failed: {e}")
            return self._get_template_question(memory, turn)

    def _identify_gaps(self, memory: ConversationMemory) -> str:
        """Identify what we still need to understand"""
        gaps = []
        story = memory.story

        # Priority order of what to explore
        if not story.emotional_state and 'emotion' not in memory.questions_asked:
            gaps.append("their emotional state")
        if not story.trigger_event and 'trigger' not in memory.questions_asked:
            gaps.append("what triggered this situation")

        # SKIP asking for demographics if already known from user profile (registration)
        # Only ask if not pre-populated from auth
        if not story.profession and 'profession' not in memory.questions_asked:
            gaps.append("their profession or what they do")
        if not story.life_situation and 'life_situation' not in memory.questions_asked:
            gaps.append("their life situation")

        if not story.duration and 'duration' not in memory.questions_asked:
            gaps.append("how long this has been going on")
        if not story.life_area and 'life_area' not in memory.questions_asked:
            gaps.append("which area of life is most affected")
        if not story.underlying_fears and 'fears' not in memory.questions_asked:
            gaps.append("their deeper concerns or fears")
        if not story.unmet_needs and 'needs' not in memory.questions_asked:
            gaps.append("what they're hoping for")
        if not story.support_system and 'support' not in memory.questions_asked:
            gaps.append("their support system")

        return ", ".join(gaps[:2]) if gaps else "their overall wellbeing"

    def _get_template_question(self, memory: ConversationMemory, turn: int) -> str:
        """Fallback template questions - contextual and diverse"""
        story = memory.story

        # Turn 1: Start by understanding emotion
        if turn == 1:
            return "I'm here to listen. What's been weighing on your heart today?"

        # If we know their emotion, acknowledge it and dig deeper
        if story.emotional_state:
            emotion_responses = {
                'anxiety': "I hear that anxiety in your words. What specifically feels uncertain or overwhelming to you right now?",
                'sadness': "That sounds really hard. What's making you feel this way? Tell me more about what's happening.",
                'anger': "I sense your frustration. What situation has brought this anger up for you?",
                'confusion': "It sounds like you're trying to figure something out. Can you walk me through what's confusing you?",
                'fear': "Fear is showing up for you. What are you most afraid might happen?",
                'hopelessness': "I'm here with you. When did this feeling of hopelessness start?",
                'frustration': "That frustration makes sense. What's been the most challenging part of this situation?",
                'grief': "Loss can be so heavy. What or who are you grieving?",
                'loneliness': "Loneliness can be painful. Are you physically alone, or do you feel emotionally isolated?",
                'stress': "You're carrying a lot of stress. What's demanding the most energy from you right now?",
                'overwhelm': "Overwhelm means too much is happening at once. What feels like the biggest pressure?"
            }
            response = emotion_responses.get(story.emotional_state)
            if response:
                return response

        # If we know the life area, ask about impact
        if story.life_area and not story.trigger_event:
            area_responses = {
                'work': "Your work seems to be involved in this. How has this been affecting your performance or how you feel at work?",
                'family': "This seems to involve your family. How is it affecting your relationships with them?",
                'relationships': "So this is about your relationship. How is this impacting how you feel with your partner?",
                'health': "Your health is involved. How is this affecting your physical or mental wellbeing?",
                'spiritual': "There's a spiritual dimension here. How do you feel your faith or spiritual practice fits into this?",
                'financial': "This involves money matters. How long has this financial stress been affecting you?",
                'career': "Your career path seems involved. What would need to change for you to feel better about your career?"
            }
            response = area_responses.get(story.life_area)
            if response:
                return response

        # If we have a concern but not full picture, dig deeper
        if story.primary_concern and not story.duration:
            return f"I understand - {story.primary_concern[:50]}... How long has this been affecting you?"

        # Ask about duration if not known
        if story.duration and not story.underlying_fears:
            return "That's a significant time to carry this. What's the deepest fear underneath this situation?"

        # Ask about underlying needs
        if story.emotional_state and not story.unmet_needs:
            return "What would help you feel better right now? What do you truly need in this moment?"

        # If we have basics, explore deeper
        if story.emotional_state and story.life_area:
            return "I'm beginning to understand your situation. Is there something deeper - a fear, a wish, a past experience - that's connected to all of this?"

        # Default diverse responses for when we're building understanding
        default_responses = [
            "Tell me more about that. What else is happening?",
            "That makes sense. How have you been coping with this?",
            "I'm here to listen to all of it. What else should I know?",
            "Help me understand this better. What's the impact this is having on you?",
            "What does this bring up for you? How does it feel to say it out loud?",
            "I hear you. What's your deepest worry about this situation?",
            "Thank you for sharing that. What would resolution or peace look like for you?",
        ]
        
        # Use different responses based on turn to avoid repetition
        response_index = (turn - 2) % len(default_responses)
        return default_responses[response_index]


# Singleton
_companion_engine: Optional[CompanionEngine] = None


def get_companion_engine(api_key: str = "") -> CompanionEngine:
    """Get or create singleton CompanionEngine"""
    global _companion_engine
    if _companion_engine is None:
        _companion_engine = CompanionEngine(api_key=api_key)
    return _companion_engine
