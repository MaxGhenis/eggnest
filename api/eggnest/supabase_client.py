"""Supabase client for authentication and data persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .config import get_settings

# Supabase is optional - works without it for core simulation
try:
    from supabase import Client, create_client
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False
    Client = None
    create_client = None

if TYPE_CHECKING:
    from supabase import Client


def get_supabase_client() -> Client | None:
    """Get Supabase client instance (returns None if not configured)."""
    if not HAS_SUPABASE:
        return None
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_anon_key:
        return None
    return create_client(settings.supabase_url, settings.supabase_anon_key)


def get_supabase_admin_client() -> Client | None:
    """Get Supabase admin client with service key."""
    if not HAS_SUPABASE:
        return None
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_key:
        return None
    return create_client(settings.supabase_url, settings.supabase_service_key)


async def verify_jwt(token: str) -> dict | None:
    """
    Verify a Supabase JWT token.

    Returns user data if valid, None otherwise.
    """
    client = get_supabase_client()
    if not client:
        return None
    try:
        response = client.auth.get_user(token)
        if response and response.user:
            return {
                "id": response.user.id,
                "email": response.user.email,
                "created_at": str(response.user.created_at),
            }
    except Exception:
        pass
    return None


async def save_simulation(
    user_id: str, name: str, input_params: dict
) -> dict | None:
    """Save a simulation configuration for a user."""
    client = get_supabase_client()
    if not client:
        return None
    try:
        result = (
            client.table("simulations")
            .insert(
                {
                    "user_id": user_id,
                    "name": name,
                    "input_params": input_params,
                }
            )
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception:
        return None


async def get_user_simulations(user_id: str) -> list[dict]:
    """Get all saved simulations for a user."""
    client = get_supabase_client()
    if not client:
        return []
    try:
        result = (
            client.table("simulations")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception:
        return []


async def delete_simulation(user_id: str, simulation_id: str) -> bool:
    """Delete a saved simulation."""
    client = get_supabase_client()
    if not client:
        return False
    try:
        client.table("simulations").delete().eq("id", simulation_id).eq(
            "user_id", user_id
        ).execute()
        return True
    except Exception:
        return False
