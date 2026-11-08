from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseLLMAdapter(ABC):
    """Provider-independent LLM adapter interface (Section 10.2)."""

    @abstractmethod
    def detect_intent(self, message: str) -> Dict[str, Any]:
        """Classify user intent and extract structured parameters from Azerbaijani text."""
        raise NotImplementedError

    @abstractmethod
    def analyze_security_text(self, message: str) -> Dict[str, Any]:
        """Analyze a suspicious message and produce structured risk explanations in Azerbaijani."""
        raise NotImplementedError

