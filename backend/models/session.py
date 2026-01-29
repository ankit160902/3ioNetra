"""
Session models for conversation state management
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
import uuid


class ConversationPhase(str, Enum):
    """Phases of the conversation flow"""
    CLARIFICATION = "clarification"
    SYNTHESIS = "synthesis"
    ANSWERING = "answering"
    LISTENING = "listening"
    GUIDANCE = "guidance"
    CLOSURE = "closure"


class SignalType(str, Enum):
    """Types of signals collected during conversation"""
    EMOTION = "emotion"
    TRIGGER = "trigger"
    LIFE_DOMAIN = "life_domain"
    MENTAL_STATE = "mental_state"
    USER_GOAL = "user_goal"
    INTENT = "intent"
    SEVERITY = "severity"


@dataclass
class Signal:
    """Represents a collected signal with its value"""
    signal_type: SignalType
    value: str
    confidence: float = 1.0


@dataclass
class SessionState:
    """
    Represents the state of a conversation session.
    Tracks signals, conversation history, and phase transitions.
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    phase: ConversationPhase = ConversationPhase.LISTENING
    turn_count: int = 0
    signals_collected: Dict[SignalType, Signal] = field(default_factory=dict)
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)

    # Thresholds for phase transition
    min_signals_threshold: int = 4
    min_clarification_turns: int = 3
    max_clarification_turns: int = 6

    # Memory context for rich understanding
    memory: Optional[Any] = field(default=None)

    # Synthesized query for RAG
    dharmic_query: Optional[Any] = field(default=None)

    def __post_init__(self):
        # Initialize memory if not provided
        if self.memory is None:
            from models.memory_context import ConversationMemory
            self.memory = ConversationMemory()

    def add_signal(self, signal_type: SignalType, value: str, confidence: float = 1.0) -> None:
        """Add or update a signal"""
        self.signals_collected[signal_type] = Signal(
            signal_type=signal_type,
            value=value,
            confidence=confidence
        )

    def get_signal(self, signal_type: SignalType) -> Optional[Signal]:
        """Get a specific signal"""
        return self.signals_collected.get(signal_type)

    def add_message(self, role: str, content: str) -> None:
        """Add a message to conversation history"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })
        self.last_activity = datetime.utcnow()

    def get_signals_summary(self) -> Dict[str, str]:
        """Get a summary of collected signals as simple key-value pairs"""
        return {
            signal_type.value: signal.value
            for signal_type, signal in self.signals_collected.items()
        }

    def should_force_transition(self) -> bool:
        """Check if we should force transition to answering phase"""
        # Force transition after max turns
        if self.turn_count >= self.max_clarification_turns:
            return True

        # Check if enough signals have been collected after min turns
        if self.turn_count >= self.min_clarification_turns:
            if len(self.signals_collected) >= self.min_signals_threshold:
                return True

        return False

    @property
    def memory_readiness(self) -> float:
        """Get the memory's readiness for wisdom score"""
        if self.memory and hasattr(self.memory, 'readiness_for_wisdom'):
            return self.memory.readiness_for_wisdom
        return 0.0

    def is_ready_for_transition(self) -> bool:
        """Check if session is ready to transition to answering phase"""
        if self.memory_readiness >= 0.7:
            return True

        # Check turn count
        if self.turn_count >= self.min_clarification_turns:
            # Check signal count
            if len(self.signals_collected) >= self.min_signals_threshold:
                return True

        return False
