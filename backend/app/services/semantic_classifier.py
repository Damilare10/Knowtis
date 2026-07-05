"""
Semantic Classifier for WhatsApp messages.

Uses sentence-transformers (all-MiniLM-L6-v2), already loaded by app.utils, to
embed incoming messages and compare them against curated anchor phrases for
each EventCategory. The closest category wins by cosine similarity.

Why this approach:
- Robust to phrasing ("due to rain" no longer collides with "due Friday").
- Reuses an existing model, no extra dependency, no fine-tuning.
- Handles paraphrasing across languages/registers because MiniLM is a
  semantic encoder, not a keyword matcher.
- Lazy-loads anchor embeddings on first use; falls back to INFO if MiniLM
  is unavailable.

Anchor phrases were chosen to capture *intent* rather than keywords, so the
classifier generalizes to messages the curator never saw.
"""
import logging
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.services.classifier_service import Classification, EventCategory

logger = logging.getLogger(__name__)


# Curated anchor phrases per category. They are intentionally short and chat-like
# to match the surface form of WhatsApp messages. The classifier uses the
# *relative* (z-score across categories) similarity rather than absolute
# cosine, so phrase style matters more than exact word overlap.
_ANCHOR_PHRASES: Dict[EventCategory, List[str]] = {
    EventCategory.DEADLINE: [
        "test by 2pm friday",
        "quiz on friday",
        "exam next monday",
        "assignment due tomorrow",
        "submit by friday",
        "homework due 11pm",
        "submit your report before friday",
        "ca test next week",
        "midsem test on monday",
        "deadline is tomorrow",
        "your submission is due",
        "assignment closes on friday",
        "due date is moved",
        "test will hold by 5pm",
        "due date 30th",
    ],
    EventCategory.ALERT: [
        "class cancelled",
        "lecture cancelled",
        "class is cancelled",
        "lecture is moved",
        "class moved to hall b",
        "class postponed",
        "venue has changed",
        "no class today",
        "class will not hold",
        "don't come to class",
        "lecture cancelled due to rain",
        "urgent class update",
        "important announcement from lecturer",
        "rescheduled to next week",
        "class is suspended",
    ],
    EventCategory.EVENT: [
        "guest lecture tomorrow",
        "seminar on ai",
        "workshop on python",
        "guest speaker event",
        "invited talk",
        "orientation program",
        "tech talk this friday",
        "industry meetup",
        "symposium next week",
        "conference at the auditorium",
        "freshers welcome program",
        "guest lecture on machine learning",
    ],
    EventCategory.INFO: [
        "wear white on thursday",
        "bring your calculator",
        "bring textbooks",
        "fyi",
        "just fyi",
        "heads up",
        "for your information",
        "note that",
        "kindly note",
        "library closes at 8",
        "remember to sign the attendance",
        "check your email",
        "read the handout",
    ],
}

_SIGNAL_ANCHORS: List[str] = [
    "assignment deadline moved to tomorrow",
    "test will hold next week",
    "exam timetable has been released",
    "class has been postponed",
    "lecture venue has changed",
    "submit your report before friday",
    "department announced a compulsory seminar",
    "course representative shared an academic update",
    "bring your calculator for the practical",
    "school fees payment closes soon",
    "registration portal closes tomorrow",
    "lecturer moved the quiz to thursday",
    "there will be no class today",
    "tutorial starts by 2pm",
    "attendance is required for the workshop",
]

_NOISE_ANCHORS: List[str] = [
    "haha that was funny",
    "good morning everyone",
    "who is around",
    "send me the meme",
    "lol this group is quiet",
    "what are you guys doing",
    "please check your dm",
    "happy birthday",
    "anyone online",
    "thanks bro",
    "okay no problem",
    "I am on my way",
]

# Below this Z-score (relative margin above the cross-category mean) the
# message is treated as not clearly matching any category -> INFO.
_DEFAULT_MIN_ZSCORE = 0.6


class _AnchorStore:
    """Lazy-built cache of anchor embeddings keyed by EventCategory."""

    def __init__(self) -> None:
        self._by_category: Dict[EventCategory, np.ndarray] = {}
        self._signal_noise: Dict[Classification, np.ndarray] = {}
        self._loaded: bool = False
        self._failed: bool = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load(self) -> None:
        if self._loaded or self._failed:
            return
        try:
            from app.utils import generate_embedding
        except Exception as exc:
            logger.warning("semantic_classifier: cannot import utils (%s)", exc)
            self._failed = True
            return

        loaded_count = 0
        for category, phrases in _ANCHOR_PHRASES.items():
            vecs = _embed_phrases(phrases, generate_embedding)
            if vecs:
                self._by_category[category] = np.stack(vecs, axis=0)
                loaded_count += 1
                logger.info(
                    "semantic_classifier: loaded %d anchors for %s",
                    len(vecs), category.value,
                )

        for classification, phrases in {
            Classification.SIGNAL: _SIGNAL_ANCHORS,
            Classification.NOISE: _NOISE_ANCHORS,
        }.items():
            vecs = _embed_phrases(phrases, generate_embedding)
            if vecs:
                self._signal_noise[classification] = np.stack(vecs, axis=0)

        if loaded_count == 0 or len(self._signal_noise) < 2:
            self._failed = True
            logger.warning(
                "semantic_classifier: insufficient anchor embeddings produced; classifier will degrade to fallback rules",
            )
        else:
            self._loaded = True
            logger.info(
                "semantic_classifier: ready (%d/%d categories)",
                loaded_count, len(_ANCHOR_PHRASES),
            )

    def categories(self) -> Dict[EventCategory, np.ndarray]:
        if not self._loaded and not self._failed:
            self.load()
        return self._by_category

    def signal_noise(self) -> Dict[Classification, np.ndarray]:
        if not self._loaded and not self._failed:
            self.load()
        return self._signal_noise


_STORE = _AnchorStore()


def _embed_phrases(phrases, generate_embedding) -> List[np.ndarray]:
    vecs: List[np.ndarray] = []
    for phrase in phrases:
        emb = generate_embedding(phrase)
        if emb is None:
            continue
        arr = np.asarray(emb, dtype=np.float32)
        norm = float(np.linalg.norm(arr))
        if norm > 0.0:
            vecs.append(arr / norm)
    return vecs


def _embed_text(text: str) -> Optional[np.ndarray]:
    try:
        from app.utils import generate_embedding
        msg_emb = generate_embedding(text)
    except Exception as exc:
        logger.warning("semantic_classifier: embedding call failed (%s)", exc)
        return None
    if msg_emb is None:
        return None
    msg_vec = np.asarray(msg_emb, dtype=np.float32)
    msg_norm = float(np.linalg.norm(msg_vec))
    if msg_norm == 0.0:
        return None
    return msg_vec / msg_norm


def _classify_against_anchors(text: str, anchors: Dict, min_margin: float) -> Optional[Tuple[object, float]]:
    msg_unit = _embed_text(text)
    if msg_unit is None or not anchors:
        return None

    scores = {
        label: float((anchor_vecs @ msg_unit).max())
        for label, anchor_vecs in anchors.items()
    }
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_label, best_score = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = best_score - runner_up
    if margin < min_margin:
        return None
    confidence = round(min(0.99, 0.55 + best_score + margin), 4)
    return best_label, confidence


def prewarm() -> None:
    """Eagerly load anchor embeddings at startup to avoid first-message latency."""
    _STORE.load()


def classify_signal_noise_semantic(
    text: str,
    min_margin: float = 0.025,
) -> Optional[Tuple[Classification, float]]:
    """Classify academic relevance by contextual similarity, not keywords."""
    if not text or not text.strip():
        return Classification.NOISE, 0.50

    result = _classify_against_anchors(text, _STORE.signal_noise(), min_margin)
    if result is None:
        return None
    classification, confidence = result
    return classification, confidence


def classify_by_semantic_similarity(
    text: str,
    min_zscore: float = _DEFAULT_MIN_ZSCORE,
) -> Tuple[EventCategory, float]:
    """
    Classify `text` by semantic similarity to curated anchor phrases.

    Scoring is RELATIVE (z-score) rather than absolute cosine, so it is
    robust to MiniLM's general low-magnitude regime (unrelated sentences
    often sit at cos_sim ~0.05–0.15).

    Per-category score = max cosine similarity to any anchor in that category.
    z-score = (per_category - mean_across_categories) / std_across_categories
    The category with the highest z-score wins. When its z-score is below
    ``min_zscore`` we fall back to INFO (no confident semantic match).

    Returns (EventCategory, confidence in [0, 1]).
    """
    if not text or not text.strip():
        return EventCategory.INFO, 0.0

    categories = _STORE.categories()
    if not categories:
        return EventCategory.INFO, 0.40

    msg_unit = _embed_text(text)
    if msg_unit is None:
        return EventCategory.INFO, 0.40

    per_category: Dict[EventCategory, float] = {}
    for category, anchor_vecs in categories.items():
        # anchor_vecs are already L2-normalized, so dot product == cosine sim.
        sims = anchor_vecs @ msg_unit
        per_category[category] = float(sims.max())

    scores = np.array(list(per_category.values()), dtype=np.float64)
    mean = float(scores.mean())
    std = float(scores.std()) if scores.size > 1 else 0.0

    best_category = max(per_category, key=per_category.get)  # type: ignore[arg-type]
    best_sim = per_category[best_category]
    best_zscore = (best_sim - mean) / std if std > 1e-9 else 0.0

    if best_zscore < min_zscore:
        # No category cleanly stands out -> safe default is INFO.
        return EventCategory.INFO, round(max(0.40, 0.50 + 0.20 * best_sim), 4)

    # Map z-score to a calibrated [0.5, 0.99] confidence.
    confidence = round(min(0.99, 0.60 + 0.20 * min(best_zscore, 2.0)), 4)
    logger.debug(
        "semantic_classifier: '%s' -> %s (sim=%.3f, z=%.2f, mean=%.3f, std=%.3f, per_cat=%s)",
        text[:60], best_category.value, best_sim, best_zscore, mean, std, per_category,
    )
    return best_category, confidence


__all__ = [
    "classify_by_semantic_similarity",
    "prewarm",
]
