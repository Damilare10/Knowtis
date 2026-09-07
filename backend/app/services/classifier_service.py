"""
Academic event taxonomy.

What remains here is the TAXONOMY ONLY: the enums plus the maps between the
product-level category strings and the event types.

The keyword scorer, the SetFit wrapper and the semantic-similarity classifier
that used to live here were deleted in step 4C. Classification is now Agnes's
job (``agnes_service``), and the cheap deterministic drop rules live in
``prefilter``. Two latent substring bugs died with that code and need no
separate fix: ``"test"`` matched inside ``"latest"``, and ``"exam"`` inside
``"example"``.
"""
from enum import Enum
from typing import Dict, Tuple


class Classification(str, Enum):
    """Signal/noise gate result."""
    SIGNAL = "SIGNAL"
    NOISE = "NOISE"


class EventCategory(str, Enum):
    """Event category enum matching EventType."""
    DEADLINE = "DEADLINE"
    EVENT = "EVENT"
    ALERT = "ALERT"
    INFO = "INFO"


class ClassifierCategory(str, Enum):
    """Unified label combining the signal/noise gate with the event taxonomy.

    ``NOISE`` short-circuits extraction; the other four map 1:1 onto
    :class:`EventCategory` through :data:`CATEGORY_MAP`.
    """
    NOISE = "NOISE"
    DEADLINE = "DEADLINE"
    EVENT = "EVENT"
    ALERT = "ALERT"
    INFO = "INFO"


# Product-level category string -> unified label. Unknown categories fall back
# to INFO rather than NOISE: mislabelling a real announcement as noise loses a
# student's deadline, while an unnecessary INFO card is merely untidy.
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


class MessageClassifier:
    """Taxonomy helper.

    The classification methods (``classify_message``, ``classify_event_type``,
    ``classify_local_category``, ``classify_single_shot``, ``calculate_scores``)
    were removed in step 4C. Nothing local classifies text any more.
    """

    @staticmethod
    def category_to_classifier(category: str) -> ClassifierCategory:
        return LOCAL_CATEGORY_TO_CLASSIFIER.get(
            (category or "").lower(),
            ClassifierCategory.INFO,
        )
