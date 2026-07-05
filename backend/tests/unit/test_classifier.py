"""
Unit Tests - Message Classifier
"""

import pytest
from app.services.classifier_service import (
    ClassifierCategory,
    Classification,
    EventCategory,
    MessageClassifier,
)


def test_classify_message_signal():
    """Test classification of signal message"""
    text = "Assignment 2 due tomorrow by 10:00 AM"
    classification, confidence = MessageClassifier.classify_message(text)
    
    assert classification == Classification.SIGNAL
    assert confidence > 0.5


def test_classify_message_noise():
    """Test classification of noise message"""
    text = "Haha that's funny lol 😂"
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
