"""
Message Classification Service (Signal vs Noise & Event Categories)
"""
import re
from enum import Enum
from typing import Tuple, Dict

class Classification(str, Enum):
    """Classification result enum"""
    SIGNAL = "SIGNAL"
    NOISE = "NOISE"

class EventCategory(str, Enum):
    """Event category enum matching EventType"""
    DEADLINE = "DEADLINE"
    EVENT = "EVENT"
    ALERT = "ALERT"
    INFO = "INFO"


class MessageClassifier:
    """Service to classify incoming messages and calculate scoring metrics"""

    @staticmethod
    def classify_message(text: str) -> Tuple[Classification, float]:
        """
        Classifies if a message is an academic signal or casual conversation noise.
        Returns (Classification, confidence_score)
        """
        text_lower = text.lower()
        signal_keywords = [
            "assignment", "due", "quiz", "test", "exam", "class", "cancel",
            "seminar", "workshop", "deadline", "venue", "moved", "lecture",
            "timetable", "schedule"
        ]
        noise_keywords = ["haha", "lol", "funny", "😂", "meme", "joke", "hey", "hello", "hi", "whats up"]

        signal_score = sum(1 for kw in signal_keywords if kw in text_lower)
        noise_score = sum(1 for kw in noise_keywords if kw in text_lower)

        # Look for course code patterns like ELE310 or CSC 401
        has_course_code = bool(re.search(r'[a-zA-Z]{3}\s?\d{3}', text))
        if has_course_code:
            signal_score += 2

        if signal_score > noise_score:
            confidence = min(0.5 + 0.15 * signal_score, 0.99)
            return Classification.SIGNAL, confidence
        elif noise_score > signal_score:
            confidence = min(0.5 + 0.15 * noise_score, 0.99)
            return Classification.NOISE, confidence
        else:
            if has_course_code:
                return Classification.SIGNAL, 0.75
            return Classification.NOISE, 0.60

    @staticmethod
    def classify_event_type(text: str) -> Tuple[EventCategory, float]:
        """
        Classifies the specific academic event category.
        Returns (EventCategory, confidence_score)
        """
        text_lower = text.lower()
        if any(kw in text_lower for kw in ["deadline", "due", "submit", "assignment"]):
            return EventCategory.DEADLINE, 0.90
        elif any(kw in text_lower for kw in ["cancel", "moved", "postponed", "alert", "urgent"]):
            return EventCategory.ALERT, 0.90
        elif any(kw in text_lower for kw in ["seminar", "workshop", "meeting", "guest", "program"]):
            return EventCategory.EVENT, 0.85
        else:
            return EventCategory.INFO, 0.70

    @staticmethod
    def calculate_scores(text: str) -> Dict[str, float]:
        """
        Calculate importance, confidence, relevance, and actionability scores.
        All scores are returned on a scale of 0.0 to 1.0.
        """
        text_lower = text.lower()
        urgency = 0.50
        if any(kw in text_lower for kw in ["urgent", "immediate", "cancel", "asap"]):
            urgency = 0.90
        elif "due tomorrow" in text_lower or "tomorrow" in text_lower:
            urgency = 0.80
        
        confidence = 0.80
        relevance = 0.70
        actionability = 0.60
        if any(kw in text_lower for kw in ["assignment", "exam", "quiz", "test"]):
            actionability = 0.90
            relevance = 0.90
            
        return {
            "urgency_score": urgency,
            "confidence_score": confidence,
            "relevance_score": relevance,
            "actionability_score": actionability
        }
