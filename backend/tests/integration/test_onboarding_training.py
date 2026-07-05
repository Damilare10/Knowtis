"""
Integration Tests - Onboarding & Training Feedback Routes
"""
import pytest
from uuid import uuid4


def test_research_onboarding_flow(client, test_user_data, db):
    """Test getting and updating research onboarding status"""
    # Register and login user
    reg_response = client.post("/api/v1/auth/register", json=test_user_data)
    token = reg_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get status (should be uncompleted by default)
    response = client.get("/api/v1/onboarding/research", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["completed"] is False
    assert data["skipped"] is False

    # Save onboarding questions
    onboarding_data = {
        "heard_about": "whatsapp_group",
        "primary_use_case": "assignment_deadlines",
        "skipped": False
    }
    response = client.post("/api/v1/onboarding/research", json=onboarding_data, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["heard_about"] == "whatsapp_group"
    assert data["primary_use_case"] == "assignment_deadlines"
    assert data["completed"] is True

    # Get status again (should be completed now)
    response = client.get("/api/v1/onboarding/research", headers=headers)
    assert response.status_code == 200
    assert response.json()["completed"] is True


def test_training_feedback_flow(client, test_user_data, db):
    """Test prediction log retrieval and feedback creation"""
    from app.models import PredictionRecord
    # Register and login user
    reg_response = client.post("/api/v1/auth/register", json=test_user_data)
    from uuid import UUID
    user_id = UUID(reg_response.json()["user"]["id"])
    token = reg_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Insert a dummy prediction record to db directly
    pred = PredictionRecord(
        user_id=user_id,
        message_text="CSC301 Assignment is due tomorrow",
        predicted_category="Assignments",
        predicted_confidence=0.88,
        event_type="DEADLINE",
        event_completeness="complete",
        actionability="schedule_reminder",
        needs_review=True,
        model_version="test-model"
    )
    db.add(pred)
    db.commit()

    # Get predictions
    response = client.get("/api/v1/training/predictions", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["message_text"] == "CSC301 Assignment is due tomorrow"

    # Create feedback
    feedback_data = {
        "prediction_id": str(pred.id),
        "feedback_type": "confirmed_correct"
    }
    response = client.post("/api/v1/training/feedback", json=feedback_data, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["feedback_type"] == "confirmed_correct"

    # Verify prediction needs_review is updated to False
    response = client.get("/api/v1/training/predictions", headers=headers)
    assert response.status_code == 200
    assert response.json()["items"][0]["needs_review"] is False
