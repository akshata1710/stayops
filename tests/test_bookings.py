import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

BASE = "/api/v1"

# ── Helpers ───────────────────────────────────────────────────────────────────

async def register_and_login(client: AsyncClient, email: str, role: str = "guest") -> str:
    """Register a user and return their access token."""
    await client.post(f"{BASE}/auth/register", json={
        "email": email,
        "full_name": "Test User",
        "password": "Secure1234",
        "role": role,
    })
    resp = await client.post(
        f"{BASE}/auth/login",
        data={"username": email, "password": "Secure1234"},
    )
    return resp.json()["access_token"]


# ── Auth tests ─────────────────────────────────────────────────────────────────

async def test_register_success(client: AsyncClient):
    resp = await client.post(f"{BASE}/auth/register", json={
        "email": "newuser@example.com",
        "full_name": "New User",
        "password": "Secure1234",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "newuser@example.com"
    assert "hashed_password" not in data  # never leak the hash


async def test_register_duplicate_email(client: AsyncClient):
    payload = {"email": "dup@example.com", "full_name": "Dup", "password": "Secure1234"}
    await client.post(f"{BASE}/auth/register", json=payload)
    resp = await client.post(f"{BASE}/auth/register", json=payload)
    assert resp.status_code == 409


async def test_login_wrong_password(client: AsyncClient):
    await client.post(f"{BASE}/auth/register", json={
        "email": "wrong@example.com", "full_name": "W", "password": "Secure1234"
    })
    resp = await client.post(
        f"{BASE}/auth/login",
        data={"username": "wrong@example.com", "password": "BadPass99"},
    )
    assert resp.status_code == 401


# ── Property tests ─────────────────────────────────────────────────────────────

async def test_create_property_requires_host(client: AsyncClient):
    token = await register_and_login(client, "guest@example.com", role="guest")
    resp = await client.post(
        f"{BASE}/properties/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Nice Flat", "address": "1 Main St", "city": "New York",
            "country": "USA", "max_guests": 2, "bedrooms": 1, "bathrooms": 1,
            "price_per_night": "120.00", "property_type": "apartment",
        },
    )
    assert resp.status_code == 403


async def test_create_and_list_property(client: AsyncClient):
    token = await register_and_login(client, "host@example.com", role="host")
    resp = await client.post(
        f"{BASE}/properties/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Cozy Studio", "address": "5 Park Ave", "city": "Boston",
            "country": "USA", "max_guests": 2, "bedrooms": 1, "bathrooms": 1,
            "price_per_night": "95.00", "property_type": "studio",
        },
    )
    assert resp.status_code == 201
    prop_id = resp.json()["id"]

    # appears in listing
    list_resp = await client.get(f"{BASE}/properties/?city=Boston")
    assert any(p["id"] == prop_id for p in list_resp.json())


# ── Booking tests ──────────────────────────────────────────────────────────────

async def _create_property(client, host_token) -> str:
    resp = await client.post(
        f"{BASE}/properties/",
        headers={"Authorization": f"Bearer {host_token}"},
        json={
            "title": "Beach House", "address": "1 Ocean Dr", "city": "Miami",
            "country": "USA", "max_guests": 4, "bedrooms": 2, "bathrooms": 1,
            "price_per_night": "200.00", "property_type": "house",
        },
    )
    return resp.json()["id"]


async def test_create_booking_calculates_price(client: AsyncClient):
    host_token = await register_and_login(client, "host2@example.com", role="host")
    guest_token = await register_and_login(client, "guest2@example.com")
    prop_id = await _create_property(client, host_token)

    resp = await client.post(
        f"{BASE}/bookings/",
        headers={"Authorization": f"Bearer {guest_token}"},
        json={
            "property_id": prop_id,
            "check_in": "2025-09-01",
            "check_out": "2025-09-05",   # 4 nights × $200 = $800
            "num_guests": 2,
        },
    )
    assert resp.status_code == 201
    assert float(resp.json()["total_price"]) == 800.0


async def test_double_booking_prevented(client: AsyncClient):
    host_token = await register_and_login(client, "host3@example.com", role="host")
    guest1_token = await register_and_login(client, "guest3a@example.com")
    guest2_token = await register_and_login(client, "guest3b@example.com")
    prop_id = await _create_property(client, host_token)

    payload = {
        "property_id": prop_id,
        "check_in": "2025-10-10",
        "check_out": "2025-10-15",
        "num_guests": 1,
    }
    r1 = await client.post(
        f"{BASE}/bookings/", headers={"Authorization": f"Bearer {guest1_token}"}, json=payload
    )
    r2 = await client.post(
        f"{BASE}/bookings/", headers={"Authorization": f"Bearer {guest2_token}"}, json=payload
    )
    assert r1.status_code == 201
    assert r2.status_code == 409   # conflict — dates already taken


async def test_cancel_booking(client: AsyncClient):
    host_token = await register_and_login(client, "host4@example.com", role="host")
    guest_token = await register_and_login(client, "guest4@example.com")
    prop_id = await _create_property(client, host_token)

    booking_resp = await client.post(
        f"{BASE}/bookings/",
        headers={"Authorization": f"Bearer {guest_token}"},
        json={
            "property_id": prop_id,
            "check_in": "2025-11-01",
            "check_out": "2025-11-03",
            "num_guests": 1,
        },
    )
    booking_id = booking_resp.json()["id"]

    cancel_resp = await client.post(
        f"{BASE}/bookings/{booking_id}/cancel",
        headers={"Authorization": f"Bearer {guest_token}"},
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"
