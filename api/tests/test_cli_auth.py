"""Tests for CLI authentication module."""

import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from eggnest.auth import (
    Credentials,
    clear_credentials,
    get_current_user,
    is_logged_in,
    load_credentials,
    save_credentials,
    CREDENTIALS_FILE,
)


@pytest.fixture
def temp_credentials_file(tmp_path, monkeypatch):
    """Use a temporary credentials file for testing."""
    creds_file = tmp_path / ".eggnest" / "credentials.json"
    monkeypatch.setattr("eggnest.auth.CREDENTIALS_FILE", creds_file)
    return creds_file


@pytest.fixture
def sample_credentials():
    """Sample valid credentials."""
    return Credentials(
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        expires_at=time.time() + 3600,  # 1 hour from now
        user_email="test@example.com",
    )


@pytest.fixture
def expired_credentials():
    """Sample expired credentials."""
    return Credentials(
        access_token="expired_access_token",
        refresh_token="expired_refresh_token",
        expires_at=time.time() - 3600,  # 1 hour ago
        user_email="expired@example.com",
    )


class TestCredentials:
    """Tests for the Credentials dataclass."""

    def test_credentials_not_expired(self, sample_credentials):
        """Test that fresh credentials are not expired."""
        assert not sample_credentials.is_expired()

    def test_credentials_expired(self, expired_credentials):
        """Test that old credentials are expired."""
        assert expired_credentials.is_expired()

    def test_credentials_to_dict(self, sample_credentials):
        """Test serialization to dict."""
        data = sample_credentials.to_dict()
        assert data["access_token"] == "test_access_token"
        assert data["refresh_token"] == "test_refresh_token"
        assert data["user_email"] == "test@example.com"
        assert "expires_at" in data

    def test_credentials_from_dict(self, sample_credentials):
        """Test deserialization from dict."""
        data = sample_credentials.to_dict()
        restored = Credentials.from_dict(data)
        assert restored.access_token == sample_credentials.access_token
        assert restored.refresh_token == sample_credentials.refresh_token
        assert restored.user_email == sample_credentials.user_email

    def test_credentials_expiry_buffer(self):
        """Test that credentials expiring within 5 minutes are considered expired."""
        # Expires in 4 minutes (within 5 min buffer)
        creds = Credentials(
            access_token="token",
            refresh_token="refresh",
            expires_at=time.time() + 240,
            user_email="test@example.com",
        )
        assert creds.is_expired()

        # Expires in 6 minutes (outside buffer)
        creds = Credentials(
            access_token="token",
            refresh_token="refresh",
            expires_at=time.time() + 360,
            user_email="test@example.com",
        )
        assert not creds.is_expired()


class TestCredentialsPersistence:
    """Tests for saving and loading credentials."""

    def test_save_credentials(self, temp_credentials_file, sample_credentials):
        """Test saving credentials to disk."""
        save_credentials(sample_credentials)

        assert temp_credentials_file.exists()
        data = json.loads(temp_credentials_file.read_text())
        assert data["access_token"] == "test_access_token"
        assert data["user_email"] == "test@example.com"

    def test_save_credentials_creates_directory(self, temp_credentials_file, sample_credentials):
        """Test that save_credentials creates parent directory."""
        assert not temp_credentials_file.parent.exists()
        save_credentials(sample_credentials)
        assert temp_credentials_file.parent.exists()

    def test_load_credentials_exists(self, temp_credentials_file, sample_credentials):
        """Test loading existing credentials."""
        save_credentials(sample_credentials)
        loaded = load_credentials()

        assert loaded is not None
        assert loaded.access_token == sample_credentials.access_token
        assert loaded.user_email == sample_credentials.user_email

    def test_load_credentials_not_exists(self, temp_credentials_file):
        """Test loading when no credentials file exists."""
        assert load_credentials() is None

    def test_load_credentials_invalid_json(self, temp_credentials_file):
        """Test loading with invalid JSON."""
        temp_credentials_file.parent.mkdir(parents=True, exist_ok=True)
        temp_credentials_file.write_text("invalid json")

        assert load_credentials() is None

    def test_load_credentials_missing_keys(self, temp_credentials_file):
        """Test loading with missing required keys."""
        temp_credentials_file.parent.mkdir(parents=True, exist_ok=True)
        temp_credentials_file.write_text('{"access_token": "token"}')

        assert load_credentials() is None

    def test_clear_credentials(self, temp_credentials_file, sample_credentials):
        """Test clearing credentials."""
        save_credentials(sample_credentials)
        assert temp_credentials_file.exists()

        clear_credentials()
        assert not temp_credentials_file.exists()

    def test_clear_credentials_not_exists(self, temp_credentials_file):
        """Test clearing when no credentials exist."""
        # Should not raise
        clear_credentials()


class TestAuthHelpers:
    """Tests for authentication helper functions."""

    def test_get_current_user_logged_in(self, temp_credentials_file, sample_credentials):
        """Test getting current user when logged in."""
        save_credentials(sample_credentials)
        assert get_current_user() == "test@example.com"

    def test_get_current_user_not_logged_in(self, temp_credentials_file):
        """Test getting current user when not logged in."""
        assert get_current_user() is None

    def test_is_logged_in_with_valid_credentials(self, temp_credentials_file, sample_credentials):
        """Test is_logged_in with valid credentials."""
        save_credentials(sample_credentials)
        assert is_logged_in()

    def test_is_logged_in_without_credentials(self, temp_credentials_file):
        """Test is_logged_in without credentials."""
        assert not is_logged_in()

    def test_is_logged_in_with_expired_credentials_refresh_fails(
        self, temp_credentials_file, expired_credentials
    ):
        """Test is_logged_in with expired credentials when refresh fails."""
        save_credentials(expired_credentials)

        with patch("eggnest.auth.refresh_access_token", return_value=None):
            assert not is_logged_in()

    def test_is_logged_in_with_expired_credentials_refresh_succeeds(
        self, temp_credentials_file, expired_credentials, sample_credentials
    ):
        """Test is_logged_in with expired credentials when refresh succeeds."""
        save_credentials(expired_credentials)

        with patch("eggnest.auth.refresh_access_token", return_value=sample_credentials):
            assert is_logged_in()
