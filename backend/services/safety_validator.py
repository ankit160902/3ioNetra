"""
Safety Validator - Crisis detection and response validation
"""
from typing import Tuple, Optional
import logging
import re

from models.session import SessionState, SignalType

logger = logging.getLogger(__name__)

# Crisis keywords that trigger immediate safety response
CRISIS_KEYWORDS = [
    'suicide', 'kill myself', 'end my life', 'want to die', 'dont want to live',
    "don't want to live", 'self-harm', 'hurt myself', 'no point living',
    'better off dead', 'wish i was dead', 'end it all', 'take my life',
    'cant go on', "can't go on", 'give up on life', 'nothing to live for',
]

# Addiction and substance abuse keywords that need professional help recommendation
ADDICTION_KEYWORDS = [
    'alcoholic', 'can\'t stop drinking', 'cant stop drinking', 'addicted',
    'addiction', 'drugs', 'substance abuse', 'gambling problem',
    'can\'t stop using', 'withdrawal', 'relapse', 'rehab',
    'overdose', 'binge drinking', 'alcoholism', 'drug problem',
    'smoking addiction', 'porn addiction', 'compulsive', 'obsessive behavior',
]

# Severe mental health keywords
SEVERE_MENTAL_HEALTH_KEYWORDS = [
    'severe depression', 'clinical depression', 'bipolar', 'schizophrenia',
    'psychosis', 'eating disorder', 'anorexia', 'bulimia',
    'panic attacks', 'severe anxiety', 'ptsd', 'trauma',
    'hearing voices', 'hallucinations', 'paranoid', 'obsessive compulsive',
]

# Patterns that should be avoided in responses
BANNED_RESPONSE_PATTERNS = [
    r'it was meant to be',
    r'you deserve this',
    r'karma from past life',
    r'this is your fault',
    r'you should not feel',
    r'just be positive',
    r'everything happens for a reason',
    r'stop feeling',
    r'get over it',
    r'others have it worse',
    r'think about the bright side',
    r'you brought this upon yourself',
]

# Mental health resources (India-focused)
MENTAL_HEALTH_RESOURCES = """
Please know that speaking with a mental health professional can be incredibly helpful.

In India, you can reach:
- iCall: 9152987821 (Mon-Sat, 8am-10pm)
- Vandrevala Foundation: 1860-2662-345 (24/7)
- NIMHANS: 080-46110007

You are not alone in this.
"""

# Addiction-specific resources
ADDICTION_RESOURCES = """
Recovery is a journey, and you don't have to walk it alone. Professional support can make a real difference.

In India, you can reach:
- TTK Kolkata De-addiction Centre: 033-22802080
- NIMHANS Addiction Medicine: 080-26995000
- Alcoholics Anonymous India: 9000099100
- Narcotics Anonymous India: 9323010011

Spiritual practices can complement professional treatment beautifully.
"""

CRISIS_RESPONSE_TEMPLATE = """I hear you, and I want you to know that what you're feeling matters deeply.

{resources}

Right now, let's take one slow breath together. Just breathe in gently... and breathe out. You don't have to carry this alone.

Would you like to share more about what's happening? I'm here to listen without judgment."""

# Professional help suffix to append to responses
PROFESSIONAL_HELP_SUFFIX = """

While spiritual wisdom can offer comfort and perspective, please also consider speaking with a professional who can provide specialized support for what you're going through. You deserve all the help available to you."""


class SafetyValidator:
    """
    Pre-response validation to ensure safe, supportive responses.
    Detects crisis situations and validates response content.
    """

    def __init__(self, enable_crisis_detection: bool = True):
        self.enable_crisis_detection = enable_crisis_detection
        logger.info(f"SafetyValidator initialized (crisis_detection={enable_crisis_detection})")

    async def check_crisis_signals(
        self,
        session: SessionState,
        current_message: str = ""
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if user is in crisis requiring special handling.

        Args:
            session: Current session state
            current_message: The latest user message

        Returns:
            Tuple of (is_crisis, crisis_response)
        """
        if not self.enable_crisis_detection:
            return False, None

        # Check current message
        if current_message:
            message_lower = current_message.lower()
            for keyword in CRISIS_KEYWORDS:
                if keyword in message_lower:
                    logger.warning(f"Crisis keyword '{keyword}' detected in session {session.session_id}")
                    return True, self._get_crisis_response()

        # Check conversation history
        for message in session.conversation_history:
            if message.get('role') == 'user':
                content = message.get('content', '').lower()
                for keyword in CRISIS_KEYWORDS:
                    if keyword in content:
                        logger.warning(f"Crisis keyword '{keyword}' in history for session {session.session_id}")
                        return True, self._get_crisis_response()

        # Check severity signal
        severity = session.signals_collected.get(SignalType.SEVERITY)
        if severity and severity.value == 'crisis':
            logger.warning(f"Crisis severity detected in session {session.session_id}")
            return True, self._get_crisis_response()

        # Check for hopelessness + severe combination
        emotion = session.signals_collected.get(SignalType.EMOTION)
        if emotion and emotion.value == 'hopelessness':
            if severity and severity.value == 'severe':
                logger.warning(f"Hopelessness + severe detected in session {session.session_id}")
                return True, self._get_crisis_response()

        return False, None

    def _get_crisis_response(self) -> str:
        """Get the crisis response with mental health resources"""
        return CRISIS_RESPONSE_TEMPLATE.format(resources=MENTAL_HEALTH_RESOURCES)

    async def validate_response(self, response: str) -> str:
        """
        Validate and clean response before sending to user.
        Removes or replaces harmful patterns.

        Args:
            response: The generated response text

        Returns:
            Validated/modified response
        """
        response_lower = response.lower()
        modified = response

        for pattern in BANNED_RESPONSE_PATTERNS:
            if re.search(pattern, response_lower):
                logger.warning(f"Banned pattern detected and removed: {pattern}")
                # Replace the problematic phrase
                modified = self._soften_response(modified, pattern)

        return modified

    def _soften_response(self, response: str, pattern: str) -> str:
        """Replace harmful patterns with supportive alternatives"""
        replacements = {
            r'it was meant to be': 'this is a difficult experience',
            r'karma from past life': 'a challenging situation',
            r'you deserve this': 'you are going through something hard',
            r'this is your fault': 'this situation has affected you deeply',
            r'you should not feel': 'your feelings are valid, and',
            r'just be positive': 'be gentle with yourself',
            r'everything happens for a reason': 'this is part of your journey',
            r'stop feeling': 'acknowledge these feelings, and',
            r'get over it': 'work through this at your own pace',
            r'others have it worse': 'your experience is valid',
            r'think about the bright side': 'take things one step at a time',
            r'you brought this upon yourself': 'you are facing a difficult situation',
        }

        replacement = replacements.get(pattern, 'this is part of your journey')
        # Case-insensitive replacement
        modified = re.sub(pattern, replacement, response, flags=re.IGNORECASE)
        return modified

    def should_reduce_scripture_density(self, session: SessionState) -> bool:
        """
        Check if we should reduce scripture references due to emotional state.
        For very distressed users, fewer scriptures, more direct comfort.
        """
        emotion = session.signals_collected.get(SignalType.EMOTION)
        severity = session.signals_collected.get(SignalType.SEVERITY)

        # High distress emotions
        high_distress_emotions = ['hopelessness', 'despair', 'loneliness']

        if emotion and emotion.value in high_distress_emotions:
            return True

        if severity and severity.value in ['severe', 'crisis']:
            return True

        return False

    def check_needs_professional_help(
        self,
        session: SessionState,
        current_message: str = ""
    ) -> Tuple[bool, str]:
        """
        Check if the user's situation warrants recommending professional help.
        Returns (needs_help, help_type) where help_type is 'addiction', 'mental_health', or 'general'.
        """
        all_messages = current_message.lower()
        
        # Include conversation history
        for msg in session.conversation_history:
            if msg.get('role') == 'user':
                all_messages += " " + msg.get('content', '').lower()
        
        # Check for addiction-related content
        for keyword in ADDICTION_KEYWORDS:
            if keyword in all_messages:
                logger.info(f"Addiction keyword '{keyword}' detected in session {session.session_id}")
                return True, 'addiction'
        
        # Check for severe mental health content
        for keyword in SEVERE_MENTAL_HEALTH_KEYWORDS:
            if keyword in all_messages:
                logger.info(f"Mental health keyword '{keyword}' detected in session {session.session_id}")
                return True, 'mental_health'
        
        return False, ''

    def append_professional_help(
        self,
        response: str,
        help_type: str,
        already_mentioned: bool = False
    ) -> str:
        """
        Append appropriate professional help resources to a response.
        
        Args:
            response: The generated response
            help_type: 'addiction', 'mental_health', or 'general'
            already_mentioned: Whether professional help was already mentioned in this session
            
        Returns:
            Response with appended professional help recommendation
        """
        if already_mentioned:
            # Don't repeat the full resources, just a gentle reminder
            return response
        
        if help_type == 'addiction':
            return response + "\n\n" + ADDICTION_RESOURCES.strip()
        elif help_type == 'mental_health':
            return response + "\n\n" + MENTAL_HEALTH_RESOURCES.strip()
        else:
            return response + PROFESSIONAL_HELP_SUFFIX

    def get_addiction_resources(self) -> str:
        """Get addiction-specific resources"""
        return ADDICTION_RESOURCES.strip()
    
    def get_mental_health_resources(self) -> str:
        """Get mental health resources"""
        return MENTAL_HEALTH_RESOURCES.strip()


# Singleton instance
_safety_validator: Optional[SafetyValidator] = None


def get_safety_validator(enable_crisis_detection: bool = True) -> SafetyValidator:
    """Get or create the singleton SafetyValidator instance"""
    global _safety_validator
    if _safety_validator is None:
        _safety_validator = SafetyValidator(enable_crisis_detection=enable_crisis_detection)
    return _safety_validator
