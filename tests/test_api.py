import os
import sys
from unittest.mock import MagicMock, patch

# import pytest
from fastapi.testclient import TestClient

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.web.app import app

# Mock Google Auth
sys.modules["google.oauth2"] = MagicMock()
sys.modules["google.oauth2.id_token"] = MagicMock()
sys.modules["google_auth_oauthlib"] = MagicMock()
sys.modules["google_auth_oauthlib.flow"] = MagicMock()

# Setup TestClient
client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "ORA Discord Bot API is running"}


def test_link_init():
    # Mock store
    with patch("src.web.endpoints.get_store"):
        # We need a real store or a good mock.
        # Since the app initializes store in lifespan, TestClient might not trigger it fully if we mock get_store?
        # Actually TestClient runs lifespan.
        # But we want to inspect the DB.
        pass


# We will use a more integration-style test with a real DB file
# but we need to set env vars first.

os.environ["ORA_BOT_DB"] = "test_ora_bot.db"
os.environ["GOOGLE_CLIENT_ID"] = "test_client_id"
os.environ["GOOGLE_CLIENT_SECRET"] = "test_client_secret"
os.environ["GOOGLE_REDIRECT_URI"] = "http://localhost:8000/auth/discord"

# Clean up old db
if os.path.exists("test_ora_bot.db"):
    os.remove("test_ora_bot.db")


def test_full_flow():
    with TestClient(app) as client:
        # 1. Link Init
        response = client.post("/api/link/init", json={"user_id": "123456789"})
        assert response.status_code == 200
        data = response.json()
        assert "code" in data
        link_code = data["code"]
        print(f"Link code: {link_code}")

        # 2. Auth Discord (Initial)
        # Should redirect to Google
        with patch("src.web.endpoints.Flow") as MockFlow:
            mock_flow_instance = MagicMock()
            MockFlow.from_client_config.return_value = mock_flow_instance
            mock_flow_instance.authorization_url.return_value = ("http://google.com/auth", "state")

            response = client.get(f"/auth/discord?state={link_code}")
            assert response.status_code == 200
            assert "Redirecting to Google" in response.text

            # Verify consume_login_state was called implicitly by success
            # But we can't easily check internal state of Store without accessing it.
            # However, if we try to use the same code again, it should fail.
            response_retry = client.get(f"/auth/discord?state={link_code}")
            assert response_retry.status_code == 400
            assert "Invalid or expired link" in response_retry.text

        # 3. Auth Discord (Callback)
        with (
            patch("src.web.endpoints.Flow") as MockFlow,
            patch("src.web.endpoints.id_token.verify_oauth2_token") as mock_verify,
        ):
            mock_flow_instance = MagicMock()
            MockFlow.from_client_config.return_value = mock_flow_instance

            # Mock token verification
            mock_verify.return_value = {"sub": "google_12345"}

            # The state passed back from Google should be the discord_user_id ("123456789")
            # because we consumed the link code and passed the user_id as state to Google.

            response = client.get("/auth/discord?code=auth_code&state=123456789")
            assert response.status_code == 200
            assert "Link Successful" in response.text

        # 4. Dataset Ingest
        # Create a dummy file
        files = {"file": ("test.txt", b"hello world", "text/plain")}
        data = {"discord_user_id": "123456789", "dataset_name": "test_dataset"}

        response = client.post("/api/datasets/ingest", data=data, files=files)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        dataset_id = response.json()["dataset_id"]
        print(f"Dataset ID: {dataset_id}")

        # Verify file exists
        # We need to know where it saved.
        # It saves to data/datasets/123456789/...
        # We can check if the directory exists.
        assert os.path.exists("data/datasets/123456789")


if __name__ == "__main__":
    try:
        test_full_flow()
        print("All tests passed!")
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback

        traceback.print_exc()
    finally:
        if os.path.exists("test_ora_bot.db"):
            os.remove("test_ora_bot.db")
