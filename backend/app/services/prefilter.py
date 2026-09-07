"""
Deterministic prefilter for WhatsApp messages.

A zero-cost tier that drops obviously worthless messages before they reach the
LLM. Everything here must be cheap and deterministic.

Rules, first match wins:
    1. empty / whitespace-only / media-only        -> SKIPPED_EMPTY
    2. fewer than 4 tokens AND no action verb      -> SKIPPED_FRAGMENT
    3. same text_hash in this group within 24h     -> SKIPPED_REPEAT
    otherwise                                     -> None (pass to the LLM)

Deliberately absent, because each caused real misclassification:
    * no ``text.endswith("?")`` rule — reps write "Class moved to Hall B, ok?"
    * no signal/noise keyword scoring
    * no SetFit, no embeddings, no semantic similarity
    * no unbounded substring matching ("hi" once matched inside "shifted")

Recall matters far more than precision here. A false pass costs a fraction of a
cent; a false skip loses a student's deadline.
"""
import hashlib
import re
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models import ProcessingStatus, RawMessage

# Words that rescue terse but genuine announcements ("Class cancelled",
# "Exam moved"). Matched with word boundaries only, never as substrings.
ACTION_VERBS = frozenset({
    "cancelled", "canceled", "moved", "postponed", "rescheduled", "extended",
    "added", "updated", "changed", "shifted", "relocated", "suspended",
    "confirmed", "required", "mandatory", "due", "new", "urgent", "important",
    "submitted", "deadline", "exam", "class", "quiz", "assignment", "meeting",
    "lecture", "venue", "time", "date", "test", "submission", "holiday",
})

_ACTION_VERB_RE = re.compile(
    r"\b(?:" + "|".join(sorted(map(re.escape, ACTION_VERBS))) + r")\b",
    re.IGNORECASE,
)

# Emoji and pictograph ranges only. Deliberately does NOT include the whole
# supplementary plane (U+10000-U+10FFFF): that would classify a message written
# entirely in a non-Latin supplementary-plane script as media-only and silently
# drop it.
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F5FF"   # symbols & pictographs
    "\U0001F600-\U0001F64F"   # emoticons
    "\U0001F680-\U0001F6FF"   # transport & map
    "\U0001F900-\U0001F9FF"   # supplemental symbols
    "\U0001FA70-\U0001FAFF"   # extended-A
    "\U0001F1E0-\U0001F1FF"   # regional indicators (flags)
    "\u2600-\u27BF"           # misc symbols & dingbats
    "\u2B00-\u2BFF"
    "\uFE0F\u200D\u20E3\u3030"  # variation selector, ZWJ, keycap, wavy dash
    "]+",
    flags=re.UNICODE,
)

MIN_TOKENS = 4
REPEAT_WINDOW_HOURS = 24


def normalise_for_hash(text: str) -> str:
    """Canonical form for duplicate detection: lowercased, whitespace collapsed."""
    return " ".join((text or "").lower().split())


def compute_text_hash(text: str) -> Optional[str]:
    """The ONE hash contract. Both ingest and the prefilter must call this.

    Keeping a second copy in the listener is how the embedding-mismatch bug
    happened elsewhere in this pipeline: three writers built vectors from three
    different base strings and dedup silently compared incompatible values.
    """
    normalised = normalise_for_hash(text)
    if not normalised:
        return None
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def _is_media_only(text: str) -> bool:
    """True when nothing but whitespace and emoji remain."""
    stripped = (text or "").strip()
    if not stripped:
        return True
    return not _EMOJI_RE.sub("", stripped).strip()


def _has_action_verb(text: str) -> bool:
    return bool(_ACTION_VERB_RE.search(text or ""))


def classify_skip(
    text: str,
    group_id,
    db: Session,
    exclude_message_id=None,
    before: Optional[datetime] = None,
) -> Optional[ProcessingStatus]:
    """Return the status to record for a droppable message, else None.

    ``exclude_message_id`` MUST be passed when the message being classified is
    already persisted, which is the normal case: the listener stores every
    message (with its ``text_hash``) before the batch writer runs. Without the
    exclusion the repeat check matches the row against itself and every single
    message is reported as SKIPPED_REPEAT.

    ``before`` should be the candidate's own ``created_at``. The repeat rule is
    "keep the first, skip later copies", so only STRICTLY OLDER messages count.
    Without it, two identical messages in one batch exclude each other by id and
    both are skipped, losing the announcement entirely.
    """
    if _is_media_only(text):
        return ProcessingStatus.SKIPPED_EMPTY

    if len(text.split()) < MIN_TOKENS and not _has_action_verb(text):
        return ProcessingStatus.SKIPPED_FRAGMENT

    digest = compute_text_hash(text)
    if digest:
        cutoff = datetime.utcnow() - timedelta(hours=REPEAT_WINDOW_HOURS)
        query = db.query(RawMessage.id).filter(
            RawMessage.group_id == group_id,
            RawMessage.text_hash == digest,
            RawMessage.created_at >= cutoff,
        )
        if before is not None:
            query = query.filter(RawMessage.created_at < before)
        if exclude_message_id is not None:
            query = query.filter(RawMessage.id != exclude_message_id)
        if query.first():
            return ProcessingStatus.SKIPPED_REPEAT

    return None
