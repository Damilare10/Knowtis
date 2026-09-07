"""
Regression tests for the "Academic Update" placeholder-title defect.

Root cause: AgnesService.BATCH_PROMPT -- the only prompt used in production --
shipped without an event schema, saying merely
    { ...event object adhering to standard schema... }
so the model guessed field names, omitted `title`, and the pydantic default on
ExtractedEventItem silently turned every card into "Academic Update" with no
course code, venue or date.
"""
import pytest

from app.services.agnes_service import (
    _EVENT_OBJECT_SCHEMA,
    _SHARED_EVENT_RULES,
    AgnesService,
    EXTRACTION_SYSTEM_PROMPT,
    _trunc_title,
)
from app.services.event_extraction_service import EventExtractionService

REQUIRED_KEYS = [
    "action_type", "category", "course_code", "title", "description", "venue",
    "date_expression", "date_is_explicit", "lecturer",
    "confidence_score", "relevance_score", "actionability_score",
    "needs_review", "event_completeness",
]


# -- the prompts must actually describe the schema ----------------------------

@pytest.mark.parametrize("prompt_name,prompt", [
    ("BATCH_PROMPT", AgnesService.BATCH_PROMPT),
    ("EXTRACTION_SYSTEM_PROMPT", EXTRACTION_SYSTEM_PROMPT),
])
@pytest.mark.parametrize("key", REQUIRED_KEYS)
def test_prompt_enumerates_every_event_field(prompt_name, prompt, key):
    assert f'"{key}"' in prompt, f"{prompt_name} does not mention {key}"


def test_batch_prompt_has_no_schema_placeholder():
    """The literal defect: a hand-wave instead of a schema."""
    assert "adhering to standard schema" not in AgnesService.BATCH_PROMPT


def test_both_prompts_share_one_schema_block():
    """Two copies drift; one copy cannot."""
    assert _EVENT_OBJECT_SCHEMA in AgnesService.BATCH_PROMPT
    assert _EVENT_OBJECT_SCHEMA in EXTRACTION_SYSTEM_PROMPT
    assert _SHARED_EVENT_RULES in AgnesService.BATCH_PROMPT
    assert _SHARED_EVENT_RULES in EXTRACTION_SYSTEM_PROMPT


def test_prompts_forbid_the_placeholder_title():
    assert "Academic Update" in _EVENT_OBJECT_SCHEMA  # named as forbidden
    assert "Never" in _EVENT_OBJECT_SCHEMA


def test_prompts_still_ban_llm_date_arithmetic():
    for prompt in (AgnesService.BATCH_PROMPT, EXTRACTION_SYSTEM_PROMPT):
        assert "date_expression" in prompt
        assert "Never output an ISO date" in prompt
        assert "urgency_score" in prompt  # named as forbidden output


# -- absence must stay detectable --------------------------------------------

def test_trunc_title_preserves_emptiness():
    """It used to substitute the placeholder, hiding the omission."""
    assert _trunc_title("") == ""
    assert _trunc_title(None) == ""
    assert _trunc_title("Real title") == "Real title"
    assert len(_trunc_title("x" * 200)) == 80


def test_extracted_event_item_title_defaults_to_empty():
    from app.schemas import ExtractedEventItem
    assert ExtractedEventItem().title == ""


# -- salvage or reject, never persist a placeholder --------------------------

@pytest.mark.parametrize("placeholder", [
    "", "Academic Update", "academic update", "ACADEMIC UPDATE",
    "Update", "Announcement", "Notice", "N/A", "none", "Untitled", "info.",
])
def test_placeholder_title_is_salvaged_from_description(placeholder):
    result = EventExtractionService._resolve_title({
        "title": placeholder,
        "description": "Good morning everyone. The ELE310 CA test has moved to Hall B.",
    })
    assert result
    assert result.lower() not in {"academic update", "update", ""}
    # The greeting opener must be stripped, not used as the title.
    assert not result.lower().startswith("good morning")


def test_real_title_is_left_alone():
    assert EventExtractionService._resolve_title(
        {"title": "ELE310 CA test moved to Friday 2pm", "description": "..."}
    ) == "ELE310 CA test moved to Friday 2pm"


def test_unsalvageable_event_is_dropped_not_placeholdered():
    """No title and no usable body -> the event must be rejected outright."""
    assert EventExtractionService._resolve_title({"title": "", "description": ""}) == ""

    wrapped = EventExtractionService._wrap_batch_result({
        "category": "DEADLINE",
        "title": "Academic Update",
        "description": "",
    })
    assert wrapped is None


def test_wrap_batch_result_keeps_a_salvaged_event():
    wrapped = EventExtractionService._wrap_batch_result({
        "category": "DEADLINE",
        "title": "",
        "description": "Attention all: CSC301 assignment is due on Friday.",
    })
    assert wrapped is not None
    assert wrapped["title"]
    assert wrapped["title"].lower() != "academic update"
    assert not wrapped["title"].lower().startswith("attention")


def test_no_event_ever_carries_the_placeholder_title():
    """End-to-end over the shapes a sloppy model actually returns."""
    sloppy_payloads = [
        {"category": "DEADLINE", "description": "CSC301 test holds on Monday in Hall A."},
        {"category": "ALERT", "title": None, "description": "Please note: lecture cancelled today."},
        {"category": "INFO", "title": "  ", "description": "Bring your calculator for the practical."},
    ]
    for payload in sloppy_payloads:
        wrapped = EventExtractionService._wrap_batch_result(payload)
        assert wrapped is not None, payload
        assert wrapped["title"].strip().lower() not in {"academic update", "update", ""}
