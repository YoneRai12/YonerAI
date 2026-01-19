import asyncio
import logging
import os
import sys
from unittest.mock import AsyncMock, MagicMock

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.llm_client import LLMClient

# Setup Logger
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("DebugLLM")


async def test_payload_generation():
    print("--- STARTING PAYLOAD TEST ---\n")

    # Mock Session
    mock_session = MagicMock()
    mock_request = AsyncMock()

    # Mock Response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "OK"}}],
        "object": "response",
        "output": "OK",
    }
    mock_request.__aenter__.return_value = mock_response
    mock_session.request.return_value = mock_request
    mock_session.post.return_value = mock_request  # For vLLM

    # Initialize Client
    client = LLMClient(base_url="http://mock", api_key="mock", model="gpt-4", session=mock_session)

    # Test Cases
    test_cases = [
        {"model": "gpt-4o", "temp": 0.7, "desc": "GPT-4o (Legacy Standard - Temp Allowed)"},
        {"model": "gpt-5-mini", "temp": 0.7, "desc": "GPT-5 Mini (New Standard - NO Temp)"},
        {"model": "gpt-4.1-mini", "temp": 0.5, "desc": "GPT-4.1 Mini (Alt Standard - NO Temp)"},
        {"model": "gpt-5.1-codex", "temp": 0.0, "desc": "Codex (Agentic - NO Temp)"},
    ]

    for case in test_cases:
        print(f"\n[TEST CASE]: {case['desc']}")
        print(f"Model: {case['model']}, Temp Input: {case['temp']}")

        try:
            # We rely on the internal robust_json_request to be called.
            # But robust_json_request is imported in llm_client.
            # We need to mock the session.request call which robust_json_request uses.

            await client.chat(
                messages=[{"role": "user", "content": "Hello"}],
                model=case["model"],
                temperature=case["temp"],
                max_tokens=100,
            )

            # Extract call args
            # The client calls robust_json_request, which calls session.request
            # We inspect the LAST call to session.request
            call_args = mock_session.request.call_args
            if not call_args:
                print("❌ No Request Made!")
                continue

            args, kwargs = call_args
            url = args[1]
            json_data = kwargs.get("json")

            print(f"URL: {url}")
            print(f"Payload Keys: {list(json_data.keys())}")

            if "temperature" in json_data:
                print(f"❌ Temperature PRESENT: {json_data['temperature']}")
            else:
                print("✅ Temperature OMITTED")

            if "max_completion_tokens" in json_data:
                print(f"✅ max_completion_tokens: {json_data['max_completion_tokens']}")
            elif "max_output_tokens" in json_data:
                # v1/responses uses max_output_tokens, check mapping
                print(f"✅ max_output_tokens: {json_data['max_output_tokens']}")
            elif "max_tokens" in json_data:
                print(f"⚠️ max_tokens: {json_data['max_tokens']}")

            # Reset mock
            mock_session.request.reset_mock()

        except Exception as e:
            print(f"❌ Error: {e}")

    print("\n--- TEST COMPLETE ---")


if __name__ == "__main__":
    asyncio.run(test_payload_generation())
