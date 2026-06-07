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
    
    assert response.status_code == 200
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
