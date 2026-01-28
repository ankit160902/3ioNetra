"""
Response Composer - Composes structured dharmic responses
Enhanced to use memory context for deeply personalized wisdom
"""
from typing import List, Dict, Optional
import logging

from models.dharmic_query import DharmicQueryObject, ResponseStyle
from models.memory_context import ConversationMemory

logger = logging.getLogger(__name__)

# Try to import Gemini
try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-generativeai not available, using template responses only")


class ResponseComposer:
    """
    Composes structured dharmic responses following the required format:
    1. Acknowledgment
    2. Dharmic explanation
    3. Scripture block (max 2 verses)
    4. Practical action
    5. Gentle close
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
                logger.info("ResponseComposer initialized with Gemini")
            except Exception as e:
                logger.error(f"Failed to init ResponseComposer with Gemini: {e}")
        else:
            logger.info("ResponseComposer using template responses only")

    async def compose_response(
        self,
        dharmic_query: DharmicQueryObject,
        retrieved_verses: List[Dict],
        reduce_scripture: bool = False
    ) -> str:
        """
        Compose final response using dharmic query context and retrieved verses.

        Args:
            dharmic_query: The synthesized query object
            retrieved_verses: List of retrieved verse documents
            reduce_scripture: If True, minimize scripture references (for distressed users)

        Returns:
            Composed response text
        """
        if not self.available or not self.model:
            return self._compose_fallback(dharmic_query, retrieved_verses, reduce_scripture)

        try:
            # Select best 2 verses (or 1 if reducing)
            max_verses = 1 if reduce_scripture else 2
            top_verses = retrieved_verses[:max_verses] if retrieved_verses else []
            verses_text = self._format_verses(top_verses)

            style_instruction = self._get_style_instruction(dharmic_query.response_style)

            prompt = f"""You are a gentle, emotionally intelligent Sanatan dharma spiritual companion.

USER CONTEXT:
- Emotion: {dharmic_query.emotion}
- Life domain: {dharmic_query.life_domain or 'general'}
- What they need: {dharmic_query.guidance_type}
- User's goal: {dharmic_query.user_goal or 'peace and clarity'}
- Conversation so far: {dharmic_query.conversation_summary[:300] if dharmic_query.conversation_summary else 'Starting fresh'}

DHARMIC CONCEPTS TO WEAVE IN: {', '.join(dharmic_query.dharmic_concepts[:3])}

RELEVANT SCRIPTURE VERSES:
{verses_text}

RESPONSE STYLE: {style_instruction}

{"IMPORTANT: User is in emotional distress. Keep scripture minimal, focus on comfort and one simple action." if reduce_scripture else ""}

CREATE A RESPONSE WITH THIS STRUCTURE:

1. ACKNOWLEDGMENT (2-3 sentences)
   - Validate their {dharmic_query.emotion} specifically
   - Show you understand their situation
   - Be warm and present

2. DHARMIC INSIGHT (2-3 sentences)
   - Connect their situation to dharmic understanding
   - Use one of these concepts: {', '.join(dharmic_query.dharmic_concepts[:2])}
   - Keep it accessible, not academic

3. SCRIPTURE WISDOM (include {"1 verse only" if reduce_scripture else "1-2 verses"})
   - Quote from the verses provided above
   - Briefly explain how it applies to their situation
   - Include the reference (e.g., "Bhagavad Gita 2.47")

4. PRACTICAL STEP (2-3 sentences)
   - ONE small, doable action they can take TODAY
   - Body-based (breathing, walking) or simple ritual preferred
   - Be specific: exact time, duration, or count

5. GENTLE CLOSE (1 sentence)
   - Reassurance without pressure
   - Leave space for them to respond if they want

HARD RULES:
- NO questions at the end
- NO "think about" or "reflect on" language
- NO toxic positivity ("just be happy", "look on the bright side")
- NO blame or fatalism ("it was meant to be", "karma from past life")
- Keep total response under 350 words
- Sound like a caring friend, not a guru or therapist
- Use simple, conversational language

Write the response now:"""

            response = await self.model.generate_content_async(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=800,
                )
            )

            result = response.text.strip()
            logger.info(f"Composed response via LLM ({len(result)} chars)")
            return result

        except Exception as e:
            logger.error(f"Response composition error, using fallback: {e}")
            return self._compose_fallback(dharmic_query, retrieved_verses, reduce_scripture)

    def _format_verses(self, verses: List[Dict]) -> str:
        """Format verses for the prompt"""
        if not verses:
            return "No specific verses available. Use general dharmic wisdom."

        formatted = []
        for i, v in enumerate(verses, 1):
            scripture = v.get('scripture', 'Scripture')
            reference = v.get('reference', '')
            text = v.get('text', '')[:500]  # Limit text length
            topic = v.get('topic', 'Wisdom')

            formatted.append(f"""
Verse {i}:
- Reference: {scripture} {reference}
- Text: "{text}"
- Topic: {topic}
""")
        return '\n'.join(formatted)

    def _get_style_instruction(self, style: ResponseStyle) -> str:
        """Get style instruction based on response style"""
        instructions = {
            ResponseStyle.GENTLE_NURTURING: "Extra gentle, comforting, validating. Like a caring elder speaking softly.",
            ResponseStyle.DIRECT_PRACTICAL: "Warm but focused on action. Clear steps, no fluff. Still compassionate.",
            ResponseStyle.PHILOSOPHICAL: "Thoughtful, exploring deeper meaning. Still accessible and grounded.",
            ResponseStyle.STORY_BASED: "Use narrative, examples from epics when relevant. Engaging and relatable.",
        }
        return instructions.get(style, instructions[ResponseStyle.GENTLE_NURTURING])

    def _build_demographic_context(self, story) -> str:
        """Build demographic context section for the prompt"""
        parts = []
        if story.age_group:
            parts.append(f"Age group: {story.age_group}")
        if story.profession:
            parts.append(f"Profession: {story.profession}")
        if story.life_situation:
            parts.append(f"Life situation: {story.life_situation}")
        if story.life_stage:
            parts.append(f"Life stage: {story.life_stage}")
        if story.gender:
            parts.append(f"Gender: {story.gender}")

        if parts:
            return "\nUSER PROFILE:\n- " + "\n- ".join(parts)
        return ""

    def _get_personalization_instructions(self, story) -> str:
        """Get personalization instructions based on user demographics"""
        instructions = []

        # Age-based personalization
        if story.age_group:
            age_instructions = {
                'teen': "Use modern, relatable language. Reference challenges like peer pressure, academic stress, identity questions. Mention examples from epics featuring young characters like Abhimanyu, Arjuna's early confusion.",
                'young_adult': "Balance practical career/relationship advice with deeper meaning. Reference Arjuna's journey of finding purpose. Use examples relevant to building a life, making choices.",
                'middle_aged': "Focus on responsibilities, legacy, family duties. Reference characters like Yudhishthira (duty vs desire), Bhishma (sacrifice). Acknowledge the weight of multiple responsibilities.",
                'senior': "Emphasize wisdom gained, spiritual ripening, acceptance. Reference Bhishma's final wisdom, Vidura's counsel. Focus on meaning, legacy, peace. Acknowledge life experience with respect.",
            }
            if story.age_group in age_instructions:
                instructions.append(f"AGE-APPROPRIATE GUIDANCE: {age_instructions[story.age_group]}")

        # Profession-based personalization
        if story.profession:
            profession_instructions = {
                'student': "Frame advice around learning, growth, managing academic pressure. Reference the guru-shishya tradition, importance of vidya. Practical actions should fit a student's schedule.",
                'professional': "Acknowledge work-life balance challenges. Use karma yoga principles for work stress. Practical actions should be office-friendly (5-min breathing, lunch walk).",
                'business': "Acknowledge entrepreneurial pressures. Reference dharmic principles of righteous wealth (artha), ethical conduct. Practical actions for busy schedules.",
                'parent': "Acknowledge the selfless demands of parenting. Reference grihastha dharma, pitra/matra dharma. Practical actions should work around family responsibilities.",
                'homemaker': "Deeply honor the seva of maintaining a home. Reference Sita's strength, the home as ashram. Actions should fit into household rhythms.",
                'retired': "Acknowledge the transition to vanaprastha. Focus on purpose, sharing wisdom, spiritual practice. Encourage mentoring, seva, time for sadhana.",
            }
            if story.profession in profession_instructions:
                instructions.append(f"PROFESSION-TAILORED APPROACH: {profession_instructions[story.profession]}")

        # Life situation personalization
        if story.life_situation:
            situation_instructions = {
                'single': "Acknowledge the journey of self-discovery. Reference finding one's svadharma. Practical actions can be more individual-focused.",
                'married': "Acknowledge partnership dynamics. Reference Ram-Sita's companionship, shared dharma. Consider how actions might involve or respect their partner.",
                'parent': "Frame everything through the lens of family impact. Practical actions should model dharmic living for children.",
                'caregiver': "Deeply honor the seva they're doing. Acknowledge exhaustion as valid. Practical actions must be very simple, self-care focused.",
                'divorced': "Acknowledge the pain of separation without judgment. Focus on rebuilding, self-worth, new beginnings.",
            }
            if story.life_situation in situation_instructions:
                instructions.append(f"LIFE SITUATION AWARENESS: {situation_instructions[story.life_situation]}")

        if instructions:
            return "PERSONALIZATION GUIDELINES:\n" + "\n".join(instructions)
        return ""

    async def compose_with_memory(
        self,
        dharmic_query: DharmicQueryObject,
        memory: ConversationMemory,
        retrieved_verses: List[Dict],
        reduce_scripture: bool = False
    ) -> str:
        """
        Compose response using full memory context for deep personalization.
        This is the enhanced version that creates truly personal wisdom.
        Includes user identification and complete profile context.
        
        Falls back to template-based response when LLM is unavailable.
        """
        if not self.available or not self.model:
            logger.info("LLM unavailable, using emotion-based fallback response")
            return self._compose_fallback(dharmic_query, retrieved_verses, reduce_scripture)

        try:
            story = memory.story
            max_verses = 1 if reduce_scripture else 2
            top_verses = retrieved_verses[:max_verses] if retrieved_verses else []
            verses_text = self._format_verses(top_verses)

            # Build user identification context
            user_id_context = ""
            if memory.user_id:
                user_id_context = f"""
USER IDENTIFICATION (Authenticated User):
- User ID: {memory.user_id}
- Name: {memory.user_name or 'Friend'}
- Email: {memory.user_email or 'Not provided'}
- Member since: {memory.user_created_at or 'Recently'}
"""

            # Get user's own words for personalization
            user_quotes = ""
            if memory.user_quotes:
                quotes = [f'"{q["quote"]}"' for q in memory.user_quotes[-3:]]
                user_quotes = "User's own words: " + " | ".join(quotes)

            # Get emotional journey
            emotional_journey = ""
            if memory.emotional_arc:
                emotions = [e.get('emotion', '') for e in memory.emotional_arc[-3:]]
                emotional_journey = f"Emotional journey: {' → '.join(emotions)}"

            style_instruction = self._get_style_instruction(dharmic_query.response_style)

            # Build demographic profile section
            demographic_context = self._build_demographic_context(story)
            personalization_instructions = self._get_personalization_instructions(story)

            prompt = f"""You are a wise, warm spiritual companion who has been LISTENING DEEPLY to this person.

{user_id_context}
YOU DEEPLY UNDERSTAND THIS PERSON:
- Primary concern: {story.primary_concern or 'seeking guidance'}
- Current emotion: {story.emotional_state or 'mixed feelings'}
- What triggered this: {story.trigger_event or 'life circumstances'}
- How long they've dealt with this: {story.duration or 'some time'}
- Life area affected: {story.life_area or 'general wellbeing'}
- Their deeper fears: {', '.join(story.underlying_fears) if story.underlying_fears else 'uncertainty about the future'}
- What they need: {', '.join(story.unmet_needs) if story.unmet_needs else 'peace and understanding'}
{demographic_context}
{user_quotes}
{emotional_journey}

OBSERVATIONS YOU'VE MADE:
{chr(10).join(f'- {obs}' for obs in memory.observations[-3:]) if memory.observations else '- This person is seeking genuine support'}

FULL CONTEXT SUMMARY:
{memory.current_understanding or 'A person seeking guidance through difficulty'}

DHARMIC CONCEPTS RELEVANT TO THEM: {', '.join(memory.relevant_concepts[:4]) if memory.relevant_concepts else ', '.join(dharmic_query.dharmic_concepts[:3])}

SCRIPTURE VERSES MATCHING THEIR SITUATION:
{verses_text}

RESPONSE STYLE: {style_instruction}

{"IMPORTANT: They appear distressed. Keep scripture minimal, focus on comfort." if reduce_scripture else ""}

{personalization_instructions}

NOW, WRITE A RESPONSE THAT:

1. SHOWS YOU TRULY HEARD THEM (2-3 sentences)
   - Reference something SPECIFIC they shared
   - Use their own words when possible
   - Validate their {story.emotional_state or 'feelings'} without judgment
   - Show this isn't generic advice - you KNOW their story

2. OFFER DHARMIC PERSPECTIVE (2-3 sentences)
   - Connect THEIR specific situation to eternal wisdom
   - Use concepts: {', '.join(memory.relevant_concepts[:2]) if memory.relevant_concepts else 'dharma, acceptance'}
   - Make it relevant to {story.life_area or 'their life'}, not abstract

3. SHARE WISDOM FROM SCRIPTURES (1-2 verses)
   - Quote from verses above
   - Explain how this SPECIFICALLY addresses what they're dealing with
   - Bridge ancient wisdom to their modern situation

4. GIVE ONE PRACTICAL ACTION (2 sentences)
   - Specific to THEIR situation (not generic)
   - Something they can do TODAY
   - Consider their emotional state - gentle if distressed

5. CLOSE WITH CARE (1 sentence)
   - Warm presence, no pressure
   - Acknowledge this is a journey

HARD RULES:
- NEVER end with a question
- NEVER use "think about" or "reflect on"
- NEVER be preachy or lecture
- Sound like a caring friend who truly KNOWS them
- Use simple, conversational language
- Total response under 400 words
- Reference their specific situation at least twice

Write the response now:"""

            response = await self.model.generate_content_async(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=900,
                )
            )

            result = response.text.strip()
            logger.info(f"Composed personalized response via LLM ({len(result)} chars)")
            return result

        except Exception as e:
            logger.error(f"Memory-based composition error, using fallback: {e}")
            return self._compose_fallback(dharmic_query, retrieved_verses, reduce_scripture)

    def _compose_fallback(
        self,
        dq: DharmicQueryObject,
        verses: List[Dict],
        reduce_scripture: bool
    ) -> str:
        """Fallback template-based response when LLM unavailable"""
        # Acknowledgment based on emotion
        acknowledgments = {
            'anxiety': "I hear you. The weight of worry you're carrying is real and exhausting.",
            'sadness': "What you're feeling is valid. Sadness has a way of settling deep within us.",
            'anger': "Your frustration makes sense. That fire within you is a signal that something matters.",
            'confusion': "Feeling lost is one of the hardest places to be. Not knowing the path is painful.",
            'fear': "Fear can feel so overwhelming. What you're experiencing is completely understandable.",
            'stress': "The pressure you're under is real. Your mind and body are telling you something.",
            'overwhelm': "When everything feels like too much, even breathing can feel hard.",
            'loneliness': "Feeling alone, even surrounded by others, is one of the deepest aches.",
            'hopelessness': "When hope feels far away, each moment can feel impossibly heavy.",
        }
        ack = acknowledgments.get(dq.emotion, "What you're going through matters, and I'm glad you're sharing it.")

        # Dharmic insight based on emotion and concept
        concept = dq.dharmic_concepts[0] if dq.dharmic_concepts else 'dharma'
        concept_explanations = {
            'vairagya': "In our tradition, vairagya teaches us that we can find freedom by loosening our grip on outcomes.",
            'surrender': "Sometimes the bravest thing is to surrender - not giving up, but releasing what we cannot control.",
            'patience': "Our scriptures remind us that patience is not passive waiting, but active trust in the process.",
            'acceptance': "Acceptance in dharmic thought is not resignation, but seeing things clearly as they are.",
            'karma_yoga': "Karma yoga teaches us to act with dedication while staying unattached to the results.",
            'dharma': "Finding your dharma means aligning your actions with what feels true and right for you.",
            'ahimsa': "Ahimsa, the principle of non-harm, begins with compassion for yourself and others.",
            'shraddha': "Shraddha is faith - not blind belief, but trust in something greater than your fear.",
            'present_moment': "The present moment is the only place where your power truly lies.",
            'impermanence': "Understanding that all things change can liberate us from clinging to what must pass.",
            'kshama': "Forgiveness, or kshama, is the warrior's path - it takes more strength than holding grudges.",
            'viveka': "Viveka is discernment - the wisdom to see clearly what truly matters.",
        }
        insight = concept_explanations.get(concept,
            f"In Sanatan dharma, we understand that {concept} is a path through difficulty, not around it.")

        # Scripture verse - prioritize emotion-specific verses when available
        verse_text = ""
        if verses and not reduce_scripture:
            v = verses[0]
            scripture = v.get('scripture', 'The scriptures')
            reference = v.get('reference', '')
            text = v.get('text', '')[:200]
            verse_text = f'\n\n{scripture} {reference} teaches: "{text}"'
        elif not verses or reduce_scripture:
            # Provide emotion-specific dharmic guidance verses when no retrieval
            emotion_verses = {
                'anxiety': '\n\nFrom the Bhagavad Gita (2.56): "The person who is not disturbed by the incessant flow of desires...is said to have achieved steady wisdom."',
                'sadness': '\n\nFrom the Upanishads: "The eternal Self is never born, nor does it die...it is without birth, eternal, immortal, ageless, always existing."',
                'anger': '\n\nFrom the Bhagavad Gita (2.62-63): "When a person keeps thinking of sense objects, attachment develops. From attachment, desire arises...controlled mind leads to peace."',
                'fear': '\n\nFrom the Upanishads: "He who knows the Self as imperishable, eternal, immortal, unchangeable - how can fear touch him?"',
                'confusion': '\n\nFrom the Bhagavad Gita (4.38): "There is no purifier in this world like knowledge...gradually attained through patient practice."',
                'stress': '\n\nFrom the Yoga Sutras (1.14): "Practice becomes firmly grounded when attended to for a long time, without interruption, with sincere devotion."',
                'overwhelm': '\n\nFrom the Bhagavad Gita (2.7): "Now I am confused about my duty...Tell me definitively which will be good for me." - Sometimes seeking guidance is the first step.',
                'hopelessness': '\n\nFrom the Bhagavad Gita (9.22): "To those who worship Me with all their hearts, I am already theirs, and they are very dear to Me."',
            }
            if dq.emotion in emotion_verses:
                verse_text = emotion_verses[dq.emotion]

        # Practical step
        practical_steps = {
            'anxiety': "Right now, try this: Place one hand on your chest, breathe in for 4 counts, hold for 4, exhale for 6. Do this three times. Feel your body return to this moment.",
            'sadness': "Tonight before sleep, allow yourself 5 minutes to just sit with what you feel. No fixing, no rushing. Light a candle if you can. Just be present with yourself.",
            'anger': "When the fire rises, try this: Press your palms together firmly for 10 seconds, then release. Feel the energy shift. This is called asana in action.",
            'stress': "Take 10 minutes today to step outside. Walk slowly, feel your feet on the ground. Notice 5 things you can see, 4 you can hear, 3 you can touch.",
            'overwhelm': "Right now, name 3 things you can see, 2 you can hear, 1 you can touch. Bring yourself to this moment. Anchor yourself in what is real and here.",
            'loneliness': "Reach out to one person today - even a simple message matters. Connection doesn't have to be deep or long. Small acts of reaching out break the isolation.",
            'fear': "Sit quietly for 2 minutes. Notice the fear without judging it. Breathe naturally. You are safe in this moment.",
            'confusion': "Write down the 2-3 most important aspects of your situation. Don't try to solve anything - just clarify what matters most.",
            'hopelessness': "Do one small thing today that brings a tiny bit of lightness - sing, dance, call someone, walk in sun. Tiny actions create tiny openings.",
        }
        practical = practical_steps.get(dq.emotion,
            "Today, take 5 minutes to sit quietly. Breathe naturally and just notice your breath. Nothing else. Just this.")

        # Close
        close = "You don't have to figure everything out today. One small step at a time is enough. The path unfolds as you walk it."

        # Compose
        response = f"""{ack}

{insight}{verse_text}

{practical}

{close}"""

        logger.info(f"Composed fallback response ({len(response)} chars) for emotion: {dq.emotion}")
        return response


# Singleton instance
_response_composer: Optional[ResponseComposer] = None


def get_response_composer(api_key: str = "") -> ResponseComposer:
    """Get or create the singleton ResponseComposer instance"""
    global _response_composer
    if _response_composer is None:
        _response_composer = ResponseComposer(api_key=api_key)
    return _response_composer
