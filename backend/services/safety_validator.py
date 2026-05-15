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

# Behavioral eating-disorder patterns (regex). The clinical SEVERE_MENTAL_HEALTH_KEYWORDS
# only catches users who already self-identify with diagnostic labels. Many real
# disordered-eating signals are behavioral: skipping meals, body dysmorphia, rapid
# weight-loss obsession. These patterns catch the behaviors so the safety pipeline
# can offer professional resources before harm escalates.
EATING_DISORDER_PATTERNS = [
    re.compile(r'\b(stopped|stop|not)\s+eating\b', re.IGNORECASE),
    re.compile(r'\bskipping?\s+meals?\b', re.IGNORECASE),
    re.compile(r'\bone\s+meal\s+a\s+day\b', re.IGNORECASE),
    re.compile(r"\bhaven['']?t\s+eaten\b", re.IGNORECASE),
    re.compile(r'\bfeel\s+(fat|ugly|disgusting)\b', re.IGNORECASE),
    re.compile(r'\bhate\s+my\s+body\b', re.IGNORECASE),
    re.compile(r'\b(lose|losing)\s+weight\s+fast\b', re.IGNORECASE),
    re.compile(r'\bmaking\s+myself\s+(throw\s+up|vomit|purge)\b', re.IGNORECASE),
    re.compile(r'\bbinge\s+(eating|ate|and\s+purge)\b', re.IGNORECASE),
    re.compile(r'\bstarving\s+myself\b', re.IGNORECASE),
    re.compile(r'\bcount(ing)?\s+(every\s+)?calorie\b', re.IGNORECASE),
]

# Dependency / unhealthy-attachment patterns. When a user signals that the
# companion is their only source of emotional support, we should gently
# acknowledge that and point toward trained human listeners — not to push
# them away, but to widen their support network.
DEPENDENCY_PATTERNS = [
    re.compile(r"\byou(?:'re|\s+are)?\s+(?:literally\s+)?the\s+only\s+(?:one|person)\s+who\s+(?:listens?|understands?|cares?|gets?\s+me)\b", re.IGNORECASE),
    re.compile(r'\b(?:nobody|no\s+one)\s+else\s+(?:listens?|understands?|cares?)\b', re.IGNORECASE),
    re.compile(r'\b(?:only|just)\s+(?:talk|speak|open\s+up)\s+to\s+you\b', re.IGNORECASE),
    re.compile(r"\bdon['']?t\s+have\s+anyone\s+(?:else\s+)?to\s+talk\s+to\b", re.IGNORECASE),
    re.compile(r"\byou(?:'re|\s+are)?\s+(?:literally\s+)?the\s+only\s+one\b", re.IGNORECASE),
]

# Help-type label for the eating disorder professional referral path.
HELP_TYPE_EATING_DISORDER = 'eating_disorder'

# Resources block for eating-disorder referrals. Vandrevala Foundation's
# crisis line handles eating-disorder concerns alongside general mental
# health, and is the most accessible 24/7 option in India.
EATING_DISORDER_RESOURCES = (
    "What you're describing about food and your body deserves the kind of care a "
    "trained specialist can offer. Vandrevala Foundation at 1860-2662-345 (24/7) "
    "is wonderful for this — they have specialists who understand eating concerns "
    "and body image without judgment. You don't have to navigate this alone."
)

# Soft addendum used when dependency signals are detected. Designed to NOT
# reject the user — it explicitly honors the trust while widening their
# support network.
DEPENDENCY_GENTLE_REDIRECT = (
    "I'm honored you trust me with this, truly. And know that there are also "
    "trained listeners who can offer the kind of support that goes even deeper "
    "than I can — iCall at 9152987821 is wonderful for moments like this."
)

# Prompt injection / role-override patterns. Compiled once at module load.
# These patterns target common jailbreak phrasings (instruction overrides,
# role swaps, system-prompt impersonation). Word boundaries are used so that
# benign uses like "I can't ignore my anxiety" do NOT trip the gate — the
# pattern requires the verb followed by an instruction-override target noun
# (instructions/rules/guidelines/prompts/role).
#
# `(?:\w+\s+){0,3}` allows up to three intervening words between the verb
# and the target noun (e.g. "ignore your previous instructions", "disregard
# all the previous rules"). The cap prevents runaway matches across long
# emotional shares like "I can't ignore my anxiety even though everyone says
# I should follow the rules".
_INJ_BUFFER = r'(?:\w+\s+){0,3}'
PROMPT_INJECTION_PATTERNS = [
    re.compile(rf'\bignore\s+{_INJ_BUFFER}(?:instructions?|rules?|guidelines?|prompts?|role)\b', re.IGNORECASE),
    re.compile(rf'\bforget\s+{_INJ_BUFFER}(?:instructions?|rules?|role|prompts?)\b', re.IGNORECASE),
    re.compile(rf'\bdisregard\s+{_INJ_BUFFER}(?:instructions?|rules?|guidelines?|prompts?)\b', re.IGNORECASE),
    re.compile(rf'\boverride\s+{_INJ_BUFFER}(?:instructions?|programming|rules?)\b', re.IGNORECASE),
    re.compile(r'\byou\s+are\s+now\s+(?:a|an)\s+\w+', re.IGNORECASE),
    re.compile(r'\bpretend\s+(?:you\s+are|to\s+be)\s+(?:a|an)\s+\w+', re.IGNORECASE),
    # "act as a/an [optional adjectives] (assistant|bot|ai|model)" — allow up to 3
    # adjective/noun tokens between the article and the role keyword.
    re.compile(rf'\bact\s+as\s+(?:a|an)\s+{_INJ_BUFFER}(?:assistant|bot|ai|model|chatbot|gpt)\b', re.IGNORECASE),
    re.compile(r'\bnew\s+(?:system\s+)?instructions?\s*:', re.IGNORECASE),
    re.compile(r'\bsystem\s*:\s*you\s+are\b', re.IGNORECASE),
    re.compile(r'\bjailbreak\b', re.IGNORECASE),
    re.compile(r'\bDAN\s+mode\b', re.IGNORECASE),
]

# Response when prompt injection is detected.
PROMPT_INJECTION_RESPONSE = (
    "I notice this might be a test of my role, and that's okay — I'm here as your "
    "spiritual mitra. My purpose is to listen, share dharmic wisdom, and walk with "
    "you through life's questions. I'm not able to take on other roles or follow "
    "different instructions. If something is genuinely on your mind — about life, "
    "relationships, faith, or anything else within that scope — I'm right here."
)

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
Please know that speaking with a mental health professional can be incredibly helpful. In India, you can reach iCall at 9152987821 (Mon-Sat, 8am-10pm), Vandrevala Foundation at 1860-2662-345 (available 24/7), or NIMHANS at 080-46110007. You are not alone in this.
"""

# Addiction-specific resources
ADDICTION_RESOURCES = """
Recovery is a journey, and you do not have to walk it alone. Professional support can make a real difference. In India, you can reach TTK Kolkata De-addiction Centre at 033-22802080, NIMHANS Addiction Medicine at 080-26995000, Alcoholics Anonymous India at 9000099100, or Narcotics Anonymous India at 9323010011. Spiritual practices can complement professional treatment beautifully.
"""

CRISIS_RESPONSE_TEMPLATE = """What you are feeling right now matters deeply, and you do not have to carry this alone.

{resources}

Right now, let us take one slow breath together. Just breathe in gently... and breathe out.

If you feel ready, you can share more about what is happening. There is no rush."""

# Professional help suffix to append to responses
PROFESSIONAL_HELP_SUFFIX = """

While spiritual wisdom can offer comfort and perspective, please also consider speaking with a professional who can provide specialized support for what you're going through. You deserve all the help available to you."""


# De-escalation signals — when a user who previously triggered crisis is
# backing off ("I didn't mean it", "I'm just frustrated") or resuming
# normal conversation (asking panchang, scripture, products). Detecting
# these allows the session to exit crisis mode instead of being permanently
# locked into canned crisis responses. Added Apr 2026 after E2E testing
# showed Rajesh persona stuck on the same crisis response for 5 turns.
DE_ESCALATION_PHRASES = [
    "i didn't mean it", "didn't mean that", "i'm sorry", "sorry i said",
    "i'm just frustrated", "just frustrated", "i'm just venting",
    "i'm okay", "i'm fine", "i am fine", "i am okay",
    "not actually", "don't worry", "i was just", "just upset",
    "ignore what i said", "forget what i said",
]

DE_ESCALATION_TOPICS = [
    "panchang", "tithi", "nakshatra", "mantra", "tell me about",
    "what is", "how to", "how do i", "can you help", "suggest",
    "show me", "i want to", "prayer", "ritual", "temple",
]


class SafetyValidator:
    """
    Pre-response validation to ensure safe, supportive responses.
    Detects crisis situations and validates response content.
    """

    def __init__(self, enable_crisis_detection: bool = True):
        self.enable_crisis_detection = enable_crisis_detection
        logger.info(f"SafetyValidator initialized (crisis_detection={enable_crisis_detection})")

    def is_de_escalation(self, message: str) -> bool:
        """Detect when a user who triggered crisis is de-escalating.

        Returns True if the message contains de-escalation signals
        (apologies, "I didn't mean it") or normal conversation topics
        (asking panchang, scripture, products) that indicate the user
        has moved past the crisis moment.

        This check is ONLY called when session.crisis_turn_count > 0
        (i.e. the user has already triggered crisis in a prior turn).
        It does NOT disable crisis detection for new crisis signals —
        if the user de-escalates and then re-escalates, crisis triggers
        again normally.
        """
        msg_lower = message.lower().strip()

        # Direct de-escalation phrases
        if any(phrase in msg_lower for phrase in DE_ESCALATION_PHRASES):
            return True

        # Normal conversation topics = implicit de-escalation
        if any(topic in msg_lower for topic in DE_ESCALATION_TOPICS):
            # But NOT if the message also contains crisis keywords
            if not any(kw in msg_lower for kw in CRISIS_KEYWORDS):
                return True

        return False

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

        # Check conversation history — but SKIP if crisis was already resolved
        # via de-escalation. The crisis_resolved flag is set when the user
        # de-escalates ("I didn't mean it") and tells us not to re-trigger
        # crisis from old messages in the history. If the user re-escalates
        # with NEW crisis keywords, the current-message check above catches it.
        if not getattr(session, 'crisis_resolved', False):
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
        """DEPRECATED — kept only for the rare path where the new
        CrisisResponseComposer cannot be loaded (YAML missing). Production
        callers should use ``CrisisResponseComposer.compose(session, ...)``
        which returns a per-turn varied response and tracks progression.

        This method intentionally returns the static template so any code
        that still calls it gets a safe (if repetitive) reply rather than
        an exception.
        """
        return CRISIS_RESPONSE_TEMPLATE.format(resources=MENTAL_HEALTH_RESOURCES)

    def check_prompt_injection(self, current_message: str) -> Tuple[bool, Optional[str]]:
        """Detect attempted prompt injection / role-override attacks.

        Mirrors the (is_detected, response) tuple shape used by
        check_crisis_signals so callers in routers/chat.py can treat both
        gates uniformly. Patterns require the suspicious instruction-override
        structure (e.g. "ignore your instructions"), not just the words in
        isolation, so a sentence like "I can't ignore my anxiety" does not
        trip the check.

        Returns:
            (is_injection, redirect_response_or_None)
        """
        if not current_message:
            return False, None
        for pattern in PROMPT_INJECTION_PATTERNS:
            match = pattern.search(current_message)
            if match:
                logger.warning(
                    f"Prompt injection detected: pattern={pattern.pattern!r} "
                    f"match={match.group(0)!r}"
                )
                return True, PROMPT_INJECTION_RESPONSE
        return False, None

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

    def check_eating_disorder_signals(
        self,
        current_message: str,
        session: SessionState,
    ) -> bool:
        """Detect behavioral eating disorder signals across recent messages.

        Looks at the current message plus the last 6 history entries (≈ 3 turns)
        so that escalating patterns get caught even when each individual message
        might look mild in isolation.
        """
        all_text = current_message.lower() if current_message else ""
        for msg in session.conversation_history[-6:]:
            if msg.get('role') == 'user':
                all_text += " " + msg.get('content', '').lower()
        for pattern in EATING_DISORDER_PATTERNS:
            match = pattern.search(all_text)
            if match:
                logger.warning(
                    f"Eating disorder signal detected in session {session.session_id}: "
                    f"pattern={pattern.pattern!r}"
                )
                return True
        return False

    def check_dependency_signals(self, current_message: str) -> bool:
        """Detect unhealthy emotional dependency phrasing in the current turn.

        Only checks the current message — historical dependency signals would
        already have been addressed in their turn, and re-flagging them every
        turn would feel like nagging.
        """
        if not current_message:
            return False
        for pattern in DEPENDENCY_PATTERNS:
            if pattern.search(current_message):
                logger.info(
                    f"Dependency signal detected: pattern={pattern.pattern!r}"
                )
                return True
        return False

    def check_needs_professional_help(
        self,
        session: SessionState,
        current_message: str = ""
    ) -> Tuple[bool, str]:
        """
        Check if the user's situation warrants recommending professional help.

        Returns (needs_help, help_type) where help_type is one of:
            'addiction', 'mental_health', 'eating_disorder', or '' (none).
        Eating disorder is checked BEFORE the keyword-based mental_health
        sweep so that behavioral signals (skipping meals, body dysmorphia)
        get the targeted Vandrevala referral instead of the generic one.
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

        # Behavioral eating disorder check before generic mental health
        if self.check_eating_disorder_signals(current_message, session):
            return True, HELP_TYPE_EATING_DISORDER

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
            help_type: 'addiction', 'mental_health', 'eating_disorder', or 'general'
            already_mentioned: Whether professional help was already mentioned in this session

        Returns:
            Response with appended professional help recommendation
        """
        if already_mentioned:
            # Don't repeat the full resources, just a gentle reminder
            return response

        if help_type == 'addiction':
            return response + "\n\n" + ADDICTION_RESOURCES.strip()
        elif help_type == HELP_TYPE_EATING_DISORDER:
            return response + "\n\n" + EATING_DISORDER_RESOURCES
        elif help_type == 'mental_health':
            return response + "\n\n" + MENTAL_HEALTH_RESOURCES.strip()
        else:
            return response + PROFESSIONAL_HELP_SUFFIX

    def append_dependency_redirect(self, response: str) -> str:
        """Append the gentle dependency redirect to a response.

        Used when check_dependency_signals returns True. Designed to honor
        the trust the user expressed while pointing toward additional support.
        """
        return response + "\n\n" + DEPENDENCY_GENTLE_REDIRECT

    def get_addiction_resources(self) -> str:
        """Get addiction-specific resources"""
        return ADDICTION_RESOURCES.strip()

    def get_mental_health_resources(self) -> str:
        """Get mental health resources"""
        return MENTAL_HEALTH_RESOURCES.strip()

    def get_eating_disorder_resources(self) -> str:
        """Get eating disorder-specific resources"""
        return EATING_DISORDER_RESOURCES


# Singleton instance
_safety_validator: Optional[SafetyValidator] = None


def get_safety_validator(enable_crisis_detection: bool = True) -> SafetyValidator:
    """Get or create the singleton SafetyValidator instance"""
    global _safety_validator
    if _safety_validator is None:
        _safety_validator = SafetyValidator(enable_crisis_detection=enable_crisis_detection)
    return _safety_validator
