from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional


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

    @abstractmethod
    def understand(
        self,
        text: Optional[str] = None,
        audio: Optional[bytes] = None,
        mime_type: Optional[str] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """One conversational turn → structured parse.

        Returns the same dict shape as detect_intent() plus:
          transcript              what the user said (verbatim)
          engine                  "gemini" | "rule_based"
          clarification_question  set when a required slot is missing (status → needs_clarification)
          stt_failed              True when audio could not be understood at all
        """
        raise NotImplementedError
