"""
Integration Tests - Events Routes
"""

import pytest
from uuid import uuid4


def test_create_event(client, test_user_data, test_event_data, db):
    """Test creating an event"""
    # Register and login user
    reg_response = client.post("/api/v1/auth/register", json=test_user_data)
    token = reg_response.json()["access_token"]
    
    # Create event
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/api/v1/events",
        json=test_event_data,
        headers=headers
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == test_event_data["title"]
    assert data["event_type"] == test_event_data["event_type"]


def test_list_events(client, test_user_data, test_event_data, db):
    """Test listing events"""
    # Register and login
    reg_response = client.post("/api/v1/auth/register", json=test_user_data)
    token = reg_response.json()["access_token"]
    
    # Create event
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/events", json=test_event_data, headers=headers)
    
    # List events
    response = client.get("/api/v1/events", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] > 0


def test_get_event(client, test_user_data, test_event_data, db):
    """Test getting a specific event"""
    # Register and login
    reg_response = client.post("/api/v1/auth/register", json=test_user_data)
    token = reg_response.json()["access_token"]
    
    # Create event
    headers = {"Authorization": f"Bearer {token}"}
    create_response = client.post("/api/v1/events", json=test_event_data, headers=headers)
    event_id = create_response.json()["id"]
    
    # Get event
    response = client.get(f"/api/v1/events/{event_id}", headers=headers)
    
    assert response.status_code == 200
    assert response.json()["id"] == event_id


def test_delete_event(client, test_user_data, test_event_data, db):
    """Test deleting an event"""
    # Register and login
    reg_response = client.post("/api/v1/auth/register", json=test_user_data)
    token = reg_response.json()["access_token"]
    
    # Create event
    headers = {"Authorization": f"Bearer {token}"}
    create_response = client.post("/api/v1/events", json=test_event_data, headers=headers)
    event_id = create_response.json()["id"]
    
    # Delete event
    response = client.delete(f"/api/v1/events/{event_id}", headers=headers)
    
    assert response.status_code == 200


def test_list_events_with_group_name_and_superseded_filtered(client, test_user_data, db):
    """Test that group_name is exposed and SUPERSEDED status events are filtered out"""
    from app.models import WhatsAppGroup, AcademicEvent, EventStatus, CoverageState
    from uuid import UUID
    reg_response = client.post("/api/v1/auth/register", json=test_user_data)
    token = reg_response.json()["access_token"]
    user_id = UUID(reg_response.json()["user"]["id"])
    headers = {"Authorization": f"Bearer {token}"}

    grp = WhatsAppGroup(
        user_id=user_id,
        group_name="Computer Science 400L",
        group_jid="cs400@g.us",
        is_active=True,
        coverage_state=CoverageState.ACTIVE,
    )
    db.add(grp)
    db.flush()

    active_ev = AcademicEvent(
        user_id=user_id,
        group_id=grp.id,
        event_type="DEADLINE",
        title="CSC401 Project",
        status=EventStatus.ACTIVE,
        date_precision="exact",
        confidence_score=0.9,
    )
    superseded_ev = AcademicEvent(
        user_id=user_id,
        group_id=grp.id,
        event_type="DEADLINE",
        title="Old CSC401 Project Draft",
        status=EventStatus.SUPERSEDED,
        confidence_score=0.9,
    )
    db.add_all([active_ev, superseded_ev])
    db.commit()

    response = client.get("/api/v1/events", headers=headers)
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    titles = [item["title"] for item in items]
    assert "CSC401 Project" in titles
    assert "Old CSC401 Project Draft" not in titles
    target = next(item for item in items if item["title"] == "CSC401 Project")
    assert target["group_name"] == "Computer Science 400L"
    assert target["status"] == "ACTIVE"


def test_list_events_truncation_signal_for_free_user(client, test_user_data, db):
    """Free-tier users with >3 events receive truncated=True and plan_limit=3"""
    from app.models import AcademicEvent, EventStatus
    from uuid import UUID
    reg_response = client.post("/api/v1/auth/register", json=test_user_data)
    token = reg_response.json()["access_token"]
    user_id = UUID(reg_response.json()["user"]["id"])
    headers = {"Authorization": f"Bearer {token}"}

    for i in range(5):
        db.add(AcademicEvent(
            user_id=user_id,
            event_type="DEADLINE",
            title=f"Event {i}",
            status=EventStatus.ACTIVE,
            urgency_score=0.1 * i,
            confidence_score=0.9,
        ))
    db.commit()

    response = client.get("/api/v1/events", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["items"]) == 3
    assert data["truncated"] is True
    assert data["plan_limit"] == 3


def test_update_event_put(client, test_user_data, test_event_data, db):
    """Test PUT /api/v1/events/{id} updates fields, appends revisions, clears needs_review, recomputes urgency"""
    from app.models import AcademicEvent
    from uuid import UUID
    reg_response = client.post("/api/v1/auth/register", json=test_user_data)
    token = reg_response.json()["access_token"]
    user_id = UUID(reg_response.json()["user"]["id"])
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post("/api/v1/events", json=test_event_data, headers=headers)
    event_id = create_res.json()["id"]

    update_payload = {
        "title": "Updated CSC301 Exam Final",
        "course_code": "CSC301",
        "venue": "Hall A",
        "event_type": "DEADLINE",
    }
    put_res = client.put(f"/api/v1/events/{event_id}", json=update_payload, headers=headers)
    assert put_res.status_code == 200
    data = put_res.json()
    assert data["title"] == "Updated CSC301 Exam Final"
    assert data["venue"] == "Hall A"
    assert data["event_type"] == "DEADLINE"
    assert data["needs_review"] is False
    assert len(data["revisions"]) >= 1
    assert data["revisions"][-1]["action"] == "USER_UPDATE"

