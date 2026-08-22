"""
Message Classification Service (Signal vs Noise & Event Categories)
"""
import logging
import re
from enum import Enum
from typing import Tuple, Dict, Optional

from app.config import settings

logger = logging.getLogger(__name__)


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


class ClassifierCategory(str, Enum):
    """
    Unified category returned by :meth:`MessageClassifier.classify_single_shot`.

    Combines the signal/noise gate with the event-type taxonomy so the
    extraction service can branch on a single label. ``NOISE`` short-circuits
    extraction; the other four map 1:1 onto :class:`EventCategory`.
    """
    NOISE = "NOISE"
    DEADLINE = "DEADLINE"
    EVENT = "EVENT"
    ALERT = "ALERT"
    INFO = "INFO"


LOCAL_CATEGORY_TO_CLASSIFIER: Dict[str, ClassifierCategory] = {
    "noise": ClassifierCategory.NOISE,
    "assignment_deadline": ClassifierCategory.DEADLINE,
    "exam": ClassifierCategory.DEADLINE,
    "lecture_update": ClassifierCategory.ALERT,
    "event": ClassifierCategory.EVENT,
    "fee_notice": ClassifierCategory.DEADLINE,
    "general_announcement": ClassifierCategory.INFO,
}


# Maps a non-noise ClassifierCategory to its EventCategory twin.
CATEGORY_MAP: Dict[ClassifierCategory, Tuple[Classification, EventCategory]] = {
    ClassifierCategory.DEADLINE: (Classification.SIGNAL, EventCategory.DEADLINE),
    ClassifierCategory.EVENT: (Classification.SIGNAL, EventCategory.EVENT),
    ClassifierCategory.ALERT: (Classification.SIGNAL, EventCategory.ALERT),
    ClassifierCategory.INFO: (Classification.SIGNAL, EventCategory.INFO),
}


def _exact_keyword_regex(words: Tuple[str, ...]) -> re.Pattern:
    """Strict whole-word matcher, used for noise tokens.

    Plain ``kw in text`` substring matching silently produced false positives:
    ``"hi"`` matched inside ``"shifted"``, and the single-letter ``"k"`` matched
    ``"kindly"``, ``"check"`` and ``"booked"``. That made
    ``"The lecturer booked Hall A"`` score noise=2 / signal=1 and classify as
    NOISE. Noise tokens are exact chat acknowledgements, so no suffix is
    allowed — ``ok`` must not match ``booked``.
    """
    return re.compile(
        r"\b(?:" + "|".join(re.escape(w) for w in words) + r")\b",
        re.IGNORECASE,
    )


def _stem_keyword_regex(words: Tuple[str, ...]) -> re.Pattern:
    """Prefix-anchored matcher, used for signal stems.

    Signal words are content stems whose inflections carry the same meaning, so
    a trailing suffix is desirable: ``lecture`` must match ``lecturer``,
    ``cancel`` must match ``cancelled``/``cancellation``, ``assignment`` must
    match ``assignments``. The leading ``\\b`` still prevents matching inside an
    unrelated word.
    """
    return re.compile(
        r"\b(?:" + "|".join(re.escape(w) for w in words) + r")\w*",
        re.IGNORECASE,
    )


def _count_keywords(pattern: re.Pattern, text: str) -> int:
    """Count DISTINCT keywords present, matching the original scoring semantics."""
    return len({match.group(0).lower() for match in pattern.finditer(text)})


_SIGNAL_KEYWORDS: Tuple[str, ...] = (
    "assignment", "due", "quiz", "test", "exam", "class", "cancel",
    "seminar", "workshop", "deadline", "venue", "move", "lecture",
    "timetable", "schedul",
    # Present in _RE_TEST / _RE_MOVED below but previously missing here, so
    # "assessment shifted to Thursday" scored zero signal.
    "assess", "shift",
)

# Emoji are handled separately: \b has no meaning next to a non-word character.
_NOISE_EMOJI: Tuple[str, ...] = ("😂", "🤣", "😹")

_NOISE_KEYWORDS: Tuple[str, ...] = (
    "haha", "lol", "funny", "meme", "joke", "hey", "hello", "hi",
    "whats up", "thanks", "noted", "ok", "k",
)

_RE_SIGNAL_KEYWORDS = _stem_keyword_regex(_SIGNAL_KEYWORDS)
_RE_NOISE_KEYWORDS = _exact_keyword_regex(_NOISE_KEYWORDS)


class MessageClassifier:
    """Service to classify incoming messages and calculate scoring metrics"""


    @staticmethod
    def category_to_classifier(category: str) -> ClassifierCategory:
        return LOCAL_CATEGORY_TO_CLASSIFIER.get(
            (category or "").lower(),
            ClassifierCategory.INFO,
        )

    @staticmethod
    def classify_local_category(text: str) -> Tuple[str, float]:
        """
        Return the product-level category from the trained SetFit classifier.

        Labels are: noise, assignment_deadline, exam, lecture_update, event,
        fee_notice, general_announcement. When the trained model is absent or
        uncertain, this falls back to the existing semantic classifier contract.
        """
        try:
            from app.services.setfit_classifier_service import SetFitClassifierService

            prediction = SetFitClassifierService.classify(text)
            if prediction and prediction.confidence >= settings.setfit_min_confidence:
                category = prediction.category.lower()
                if category in LOCAL_CATEGORY_TO_CLASSIFIER:
                    return category, prediction.confidence
        except Exception as exc:
            logger.warning("SetFit classifier failed (%s); using semantic fallback", exc)

        classifier_cat, confidence = MessageClassifier.classify_single_shot(text)
        fallback = {
            ClassifierCategory.NOISE: "noise",
            ClassifierCategory.DEADLINE: "assignment_deadline",
            ClassifierCategory.EVENT: "event",
            ClassifierCategory.ALERT: "lecture_update",
            ClassifierCategory.INFO: "general_announcement",
        }[classifier_cat]
        return fallback, confidence

    @staticmethod
    def classify_message(text: str) -> Tuple[Classification, float]:
        """
        Classifies if a message is an academic signal or casual conversation noise.
        Returns (Classification, confidence_score)
        """
        try:
            from app.services.setfit_classifier_service import SetFitClassifierService

            prediction = SetFitClassifierService.classify(text)
            if prediction and prediction.confidence >= settings.setfit_min_confidence:
                category = prediction.category.lower()
                if category in LOCAL_CATEGORY_TO_CLASSIFIER:
                    classification = (
                        Classification.NOISE
                        if category == "noise"
                        else Classification.SIGNAL
                    )
                    return classification, prediction.confidence
        except Exception as exc:
            logger.warning("SetFit signal/noise classifier failed (%s); using fallback", exc)

        try:
            from app.services.semantic_classifier import classify_signal_noise_semantic
            semantic_result = classify_signal_noise_semantic(text)
            if semantic_result is not None and semantic_result[1] >= 0.75:
                return semantic_result
        except Exception as exc:
            logger.warning("Semantic signal/noise classifier failed (%s); using fallback rules", exc)

        text_lower = text.lower().strip()

        # Strict peer inquiries, borrowing requests, or casual chatter patterns
        peer_inquiry_patterns = [
            r"^(?:who\s+(?:has|have|is|knows)|has\s+anyone|anyone\s+(?:seen|have|knows|with)|can\s+someone|does\s+anyone)",
            r"^(?:please\s+who|pls\s+who|where\s+(?:is|are|the)|are\s+we\s+having|is\s+there\s+any|is\s+class\s+holding)",
            r"^(?:did\s+anyone|has\s+the\s+lecturer|any\s+update\s+on|good\s+morning|good\s+afternoon|good\s+evening)",
            r"\b(?:i\s+need\s+to\s+borrow|borrow\s+(?:me\s+)?(?:the\s+)?(?:textbook|slides?|notes?|pdf|past\s+questions?))\b",
            r"\b(?:who\s+has\s+the\s+textbook|anyone\s+seen\s+the\s+lecturer|seen\s+the\s+lecturer\?)\b",
            r"\b(?:where\s+are\s+you\s+guys|are\s+you\s+guys\s+in\s+class|is\s+anyone\s+in\s+class)\b",
        ]
        is_peer_inquiry = any(re.search(p, text_lower) for p in peer_inquiry_patterns)
        ends_in_question = text_lower.endswith("?")

        # Definitive official announcement phrases that override general question marks
        official_override_patterns = [
            r"\b(?:assignment\s+is\s+due|deadline\s+is|submit\s+(?:by|before|on)|submission\s+link)\b",
            r"\b(?:class\s+is\s+(?:cancelled|postponed|rescheduled|moved)|lecture\s+(?:is\s+)?(?:cancelled|postponed))\b",
            r"\b(?:venue\s+(?:changed|is\s+now)|exam\s+timetable|test\s+scheduled\s+for)\b",
        ]
        has_official_announcement = any(re.search(p, text_lower) for p in official_override_patterns)

        if (is_peer_inquiry or ends_in_question) and not has_official_announcement:
            return Classification.NOISE, 0.92

        signal_score = _count_keywords(_RE_SIGNAL_KEYWORDS, text_lower)
        noise_score = _count_keywords(_RE_NOISE_KEYWORDS, text_lower)
        noise_score += sum(1 for emoji in _NOISE_EMOJI if emoji in text_lower)

        # Look for course code patterns like ELE310 or CSC 401
        has_course_code = bool(re.search(r'[a-zA-Z]{3}\s?\d{3}', text))
        if has_course_code and not is_peer_inquiry:
            signal_score += 1

        if signal_score > noise_score and signal_score >= 1:
            confidence = min(0.5 + 0.15 * signal_score, 0.99)
            return Classification.SIGNAL, confidence
        elif noise_score > signal_score:
            confidence = min(0.5 + 0.15 * noise_score, 0.99)
            return Classification.NOISE, confidence
        else:
            return Classification.NOISE, 0.70

    # Regex matchers kept only as a fallback when semantic embeddings are
    # unavailable. The primary path should understand context, not exact words.
    _RE_CANCEL = re.compile(
        r"\b(cancel{1,2}ed?|postpone[ds]?|rescheduled?|suspen[ds]?ed?)\b", re.IGNORECASE
    )
    _RE_MOVED = re.compile(
        r"\b(moved|shifted|move[d]? to|now at|venue.{0,12}chang|new venue|hall b)\b", re.IGNORECASE
    )
    _RE_VENUE_CHANGE = re.compile(
        r"\bvenue\s+(is\s+now|has\s+chang|chang)\w*\b", re.IGNORECASE
    )
    _RE_DUE_PHRASE = re.compile(
        r"\b(due|submission|deadline|submit)\b(?!\s*to\s+[a-z])(?!.{0,40}\b(closes?\s+at|library)\b)",
        re.IGNORECASE,
    )
    # "due to" the phrase meaning "because of" -> NOT a deadline signal.
    _RE_DUE_BECAUSE = re.compile(r"\bdue\s+to\b", re.IGNORECASE)
    _RE_ASSIGNMENT = re.compile(
        r"\b(assignment|homework|ca\s+test|mid\w*sem|lab\s+report|project|essay|"
        r"submission|portfolio|assignment)\b",
        re.IGNORECASE,
    )
    _RE_EXAM = re.compile(
        r"\b(exam|mid\w*sem\s+exam|final\s+exam|pop\s+quiz|ca[\s\-]?\d|ca\s+test|"
        r"midsem|midsemester|continuous\s+assess)\w*\b",
        re.IGNORECASE,
    )
    _RE_TEST = re.compile(
        r"\b(test|quiz|assessment|practical|prac)\b", re.IGNORECASE
    )
    _RE_EVENT = re.compile(
        r"\b(seminar|workshop|guest\s+lectur\w*|invited\s+talk|conference|"
        r"symposium|webinar|orientation|meetup|tech\s+talk|panel\s+discussion|"
        r"freshers?\s+\w*\s+program\w*|induction)\b",
        re.IGNORECASE,
    )
    _RE_ALERT = re.compile(
        r"\b(urgent|important\s+(?:notice|update|announcement)|"
        r"please\s+take\s+note|kindly\s+note|asap|immediately)\b",
        re.IGNORECASE,
    )

    @staticmethod
    def classify_event_type(text: str) -> Tuple[EventCategory, float]:
        """
        Classifies the specific academic event category.

        Strategy:
        1. Use semantic similarity to category anchors so paraphrases can be
           understood without exact keyword matches.
        2. Fall back to older regex rules only if embeddings are unavailable or
           the semantic classifier cannot produce a confident category.
        """
        if not text or not text.strip():
            return EventCategory.INFO, 0.50

        has_cancel = bool(MessageClassifier._RE_CANCEL.search(text))
        has_moved = bool(MessageClassifier._RE_MOVED.search(text))
        has_assignment = bool(MessageClassifier._RE_ASSIGNMENT.search(text))
        has_exam = bool(MessageClassifier._RE_EXAM.search(text))
        has_test = bool(MessageClassifier._RE_TEST.search(text))
        has_event = bool(MessageClassifier._RE_EVENT.search(text))
        has_alert = bool(MessageClassifier._RE_ALERT.search(text))
        has_due_because = bool(MessageClassifier._RE_DUE_BECAUSE.search(text))
        has_due_phrase = bool(MessageClassifier._RE_DUE_PHRASE.search(text)) and not has_due_because

        if has_cancel or has_moved or has_alert:
            return EventCategory.ALERT, 0.90

        if has_assignment or has_exam or has_due_phrase:
            return EventCategory.DEADLINE, 0.90
        if has_test:
            return EventCategory.DEADLINE, 0.88

        if has_event:
            return EventCategory.EVENT, 0.85

        try:
            from app.services.semantic_classifier import classify_by_semantic_similarity
            category, confidence = classify_by_semantic_similarity(text)
            return category, confidence
        except Exception as exc:
            logger.warning("Semantic event classifier failed (%s); using fallback rules", exc)

        return EventCategory.INFO, 0.50

    @staticmethod
    def classify_single_shot(
        text: str,
    ) -> Tuple[ClassifierCategory, float]:
        """
        One-pass classifier combining the signal/noise gate with event typing.

        Returns a :class:`ClassifierCategory` plus a confidence score. When the
        message is noise, ``ClassifierCategory.NOISE`` is returned and the
        caller should skip event extraction entirely. Otherwise the value is
        one of DEADLINE / EVENT / ALERT / INFO, mirroring
        :meth:`classify_event_type`.

        This method is the contract the extraction service depends on; it
        composes the two unit-tested classifiers (``classify_message`` and
        ``classify_event_type``) so their behaviour is preserved exactly.
        """
        if not text or not text.strip():
            return ClassifierCategory.INFO, 0.50

        try:
            from app.services.setfit_classifier_service import SetFitClassifierService

            prediction = SetFitClassifierService.classify(text)
            if prediction and prediction.confidence >= settings.setfit_min_confidence:
                category = prediction.category.lower()
                classifier_cat = LOCAL_CATEGORY_TO_CLASSIFIER.get(category)
                if classifier_cat is not None:
                    return classifier_cat, prediction.confidence
        except Exception as exc:
            logger.warning("SetFit single-shot classifier failed (%s); using fallback", exc)

        signal_noise, sn_conf = MessageClassifier.classify_message(text)
        if signal_noise == Classification.NOISE:
            return ClassifierCategory.NOISE, sn_conf

        event_cat, ev_conf = MessageClassifier.classify_event_type(text)
        # Map EventCategory -> ClassifierCategory (both share the same string
        # values, so a direct coercion is safe).
        unified = ClassifierCategory(event_cat.value)
        # Prefer the event-type confidence once we know it's a signal — it is
        # the more specific of the two judgements.
        return unified, ev_conf

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
