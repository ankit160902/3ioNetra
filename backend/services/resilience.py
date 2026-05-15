import time
import random
import logging
from enum import Enum
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Service is down, failing fast
    HALF_OPEN = "half-open" # Testing if service recovered

class CircuitBreaker:
    """Simple Circuit Breaker implementation for external service calls."""
    
    def __init__(
        self, 
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute the function based on current circuit state."""
        self._check_state()

        if self.state == CircuitState.OPEN:
            logger.warning(f"Circuit {self.name} is OPEN. Failing fast.")
            raise RuntimeError(f"Circuit {self.name} is currently open")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure(e)
            raise

    def _check_state(self):
        """Transition from OPEN to HALF_OPEN if timeout elapsed."""
        if self.state == CircuitState.OPEN and self.last_failure_time:
            jitter = random.uniform(0, self.recovery_timeout * 0.25)
            if time.time() - self.last_failure_time > (self.recovery_timeout + jitter):
                logger.info(f"Circuit {self.name} transitioning to HALF-OPEN")
                self.state = CircuitState.HALF_OPEN

    def _on_success(self):
        """Reset failures on successful call."""
        if self.state != CircuitState.CLOSED:
            logger.info(f"Circuit {self.name} recovered! Closing.")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None

    def _on_failure(self, e: Exception):
        """Increment failures and trip circuit if threshold reached."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        logger.error(f"Circuit {self.name} failure {self.failure_count}/{self.failure_threshold}: {e}")
        
        if self.failure_count >= self.failure_threshold:
            logger.critical(f"Circuit {self.name} TRIPPED to OPEN state")
            self.state = CircuitState.OPEN
