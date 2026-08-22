"""Unit Tests - Message Classifier"""

import pytest
from app.services.classifier_service import (
	ClassifierCategory,
	Classification,
	EventCategory,
	MessageClassifier,
)
from app.services.event_extraction_service import EventExtractionService
from datetime import datetime, timezone


def test_classify_message_signal():
	"""Test classification of signal message"""
	text = "Assignment 2 due tomorrow by 10:00 AM"
	classification, confidence = MessageClassifier.classify_message(text)
	assert classification == Classification.SIGNAL
	assert confidence > 0.5


def test_classify_message_noise():
	"""Test classification of noise message"""
	text = "Haha that's funny lol \U0001f602"
	classification, confidence = MessageClassifier.classify_message(text)
	assert classification == Classification.NOISE
	assert confidence > 0.5


def test_classify_event_type_deadline():
	"""Test event type classification for deadline"""
	text = "ELE310 assignment due tomorrow"
	event_type, confidence = MessageClassifier.classify_event_type(text)
	assert event_type == EventCategory.DEADLINE


def test_classify_event_type_alert():
	"""Test event type classification for alert"""
	text = "Class cancelled tomorrow morning"
	event_type, confidence = MessageClassifier.classify_event_type(text)
	assert event_type == EventCategory.ALERT


def test_classify_event_type_event():
	"""Test event type classification for event"""
	text = "Seminar on AI next Friday"
	event_type, confidence = MessageClassifier.classify_event_type(text)
	assert event_type == EventCategory.EVENT


def test_classify_message_semantic_academic_context():
	"""Academic context should not require exact trigger keywords."""
	text = "Dr. Taiwo shifted our CSC 301 assessment to Thursday morning"
	classification, confidence = MessageClassifier.classify_message(text)
	assert classification == Classification.SIGNAL
	assert confidence > 0.5


def test_classify_event_type_semantic_paraphrase():
	"""Category assignment should understand schedule-change paraphrases."""
	text = "Dr. Taiwo shifted our CSC 301 assessment to Thursday morning"
	event_type, confidence = MessageClassifier.classify_event_type(text)
	assert event_type in {EventCategory.ALERT, EventCategory.DEADLINE}
	assert confidence > 0.5


def test_category_to_classifier_mapping():
	assert MessageClassifier.category_to_classifier("exam") == ClassifierCategory.DEADLINE
	assert MessageClassifier.category_to_classifier("lecture_update") == ClassifierCategory.ALERT
	assert MessageClassifier.category_to_classifier("fee_notice") == ClassifierCategory.DEADLINE
	assert MessageClassifier.category_to_classifier("noise") == ClassifierCategory.NOISE


def test_classify_local_category_fallback():
	category, confidence = MessageClassifier.classify_local_category(
		"Dr. Taiwo shifted our CSC 301 assessment to Thursday morning"
	)
	assert category in {
		"assignment_deadline",
		"exam",
		"lecture_update",
		"event",
		"general_announcement",
	}
	assert confidence > 0.5


def test_calculate_scores():
	"""Test score calculation"""
	text = "Urgent: ELE310 exam moved to Thursday venue Hall A"
	scores = MessageClassifier.calculate_scores(text)
	assert "urgency_score" in scores
	assert "confidence_score" in scores
	assert "relevance_score" in scores
	assert "actionability_score" in scores
	assert all(0 <= score <= 1 for score in scores.values())


class TestEventExtractionBareFragment:
	"""Bare temporal fragments like '4pm tomorrow' must not become events."""

	def test_rejects_bare_time_date_fragment(self):
		result = EventExtractionService.extract_event(
			"4pm tomorrow",
			msg_created_at=datetime.now(timezone.utc),
		)
		assert result is None, f"Expected None for bare fragment, got {result!r}"

	def test_rejects_bare_tomorrow(self):
		result = EventExtractionService.extract_event(
			"tomorrow",
			msg_created_at=datetime.now(timezone.utc),
		)
		assert result is None

	def test_rejects_bare_date(self):
		result = EventExtractionService.extract_event(
			"12/06/2024",
			msg_created_at=datetime.now(timezone.utc),
		)
		assert result is None

	def test_rejects_bare_weekday(self):
		result = EventExtractionService.extract_event(
			"next Friday",
			msg_created_at=datetime.now(timezone.utc),
		)
		assert result is None

	def test_rejects_bare_time_only(self):
		result = EventExtractionService.extract_event(
			"2:30 pm",
			msg_created_at=datetime.now(timezone.utc),
		)
		assert result is None

	def test_rejects_bare_combined_temporal(self):
		result = EventExtractionService.extract_event(
			"4pm tomorrow",
			msg_created_at=datetime.now(timezone.utc),
		)
		assert result is None

	def test_allows_short_cancelled_with_course(self):
		result = EventExtractionService.extract_event(
			"CSC 301 quiz cancelled tomorrow",
			msg_created_at=datetime.now(timezone.utc),
		)
		assert result is not None
		assert result["course_code"] == "CSC301"
		assert "CSC" in result["title"]

	def test_allows_short_exam_announcement(self):
		result = EventExtractionService.extract_event(
			"ELE310 exam next Monday",
			msg_created_at=datetime.now(timezone.utc),
		)
		assert result is not None

	def test_allows_short_due_announcement(self):
		result = EventExtractionService.extract_event(
			"CSC 301 assignment due tomorrow",
			msg_created_at=datetime.now(timezone.utc),
		)
		assert result is not None

	def test_allows_longer_contextual_message(self):
		result = EventExtractionService.extract_event(
			"The CSC 301 quiz scheduled for tomorrow has been moved to Thursday.",
			msg_created_at=datetime.now(timezone.utc),
		)
		assert result is not None


def test_pydantic_ai_schemas_validation():
	"""Test Upgrade 1: Pydantic SingleMessageAIResponse & BatchMessageAIResponse validation."""
	from app.schemas import SingleMessageAIResponse, BatchMessageAIResponse

	raw_single_json = '''
	{
		"classification": "SIGNAL",
		"events": [
			{
				"category": "DEADLINE",
				"course_code": "CSC301",
				"title": "CSC301 Lab Report Due",
				"description": "Lab report 2 due Friday by 5pm",
				"date_time": "2026-07-31T17:00:00Z"
			}
		]
	}
	'''
	parsed = SingleMessageAIResponse.model_validate_json(raw_single_json)
	assert parsed.classification == "SIGNAL"
	assert len(parsed.events) == 1
	assert parsed.events[0].course_code == "CSC301"

	raw_batch_json = '''
	{
		"items": [
			{
				"index": 1,
				"classification": "SIGNAL",
				"events": [
					{
						"category": "ALERT",
						"course_code": "ELE310",
						"title": "Class canceled"
					}
				]
			}
		]
	}
	'''
	batch_parsed = BatchMessageAIResponse.model_validate_json(raw_batch_json)
	assert len(batch_parsed.items) == 1
	assert batch_parsed.items[0].events[0].course_code == "ELE310"


def test_anchor_timestamp_day_of_week_formatting():
	"""Test Upgrade 3: Formatting of anchor timestamp with explicit Day of Week."""
	from app.services.agnes_service import AgnesService

	dt = datetime(2026, 7, 29, 18, 43, 30, tzinfo=timezone.utc)
	formatted = AgnesService._format_anchor_timestamp(dt)
	assert "Wednesday" in formatted
	assert "Day of week: Wednesday" in formatted


def test_align_course_code():
	"""Test Upgrade 4: Course code normalization and canonical alignment."""
	cleaned = EventExtractionService.align_course_code(" csc  301 ")
	assert cleaned == "CSC301"

	cleaned_hyphen = EventExtractionService.align_course_code("mth-201")
	assert cleaned_hyphen == "MTH201"


def test_extract_events_multi_event():
	"""Test Upgrade 2: Multi-event extraction helper signature."""
	events = EventExtractionService.extract_events(
		"CSC 301 quiz cancelled tomorrow",
		msg_created_at=datetime.now(timezone.utc),
	)
	assert isinstance(events, list)
	assert len(events) >= 1

