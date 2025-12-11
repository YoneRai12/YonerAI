import pytest
import asyncio
import aiohttp
from unittest.mock import MagicMock, AsyncMock
from src.utils.llm_client import robust_json_request, TransientHTTPError

class MockTime:
    def __init__(self):
        self.current = 0.0
    
    def monotonic(self):
        return self.current
    
    def advance(self, seconds):
        self.current += seconds

@pytest.mark.asyncio
async def test_robust_json_request_budget_exceeded():
    mock_time = MockTime()
    
    async def mock_sleep(seconds):
        mock_time.advance(seconds)
    
    # Mock session
    session = MagicMock(spec=aiohttp.ClientSession)
    # Mock request context manager
    request_ctx = AsyncMock()
    session.request.return_value = request_ctx
    
    # Setup response to always fail with 500 so it retries
    response = AsyncMock()
    response.status = 500
    response.headers = {}
    request_ctx.__aenter__.return_value = response
    
    # Set budget to 30s
    # We expect it to retry until max attempts or budget exhausted
    # Here max_attempts=5, and backoff will consume time
    
    with pytest.raises(RuntimeError, match="Max attempts reached"):
        await robust_json_request(
            session, "GET", "http://test",
            total_retry_budget=30.0,
            max_attempts=5,
            _sleep_func=mock_sleep,
            _time_func=mock_time.monotonic
        )
    
    # Verify time advanced
    assert mock_time.current > 0

@pytest.mark.asyncio
async def test_robust_json_request_retry_after_exceeds_budget():
    mock_time = MockTime()
    mock_sleep = AsyncMock()
    
    session = MagicMock(spec=aiohttp.ClientSession)
    request_ctx = AsyncMock()
    session.request.return_value = request_ctx
    
    response = AsyncMock()
    response.status = 429
    # Retry-After 40s > Budget 30s
    response.headers = {"Retry-After": "40"}
    request_ctx.__aenter__.return_value = response
    
    with pytest.raises(TransientHTTPError, match="exceeds budget"):
        await robust_json_request(
            session, "GET", "http://test",
            total_retry_budget=30.0,
            _sleep_func=mock_sleep,
            _time_func=mock_time.monotonic
        )

@pytest.mark.asyncio
async def test_robust_json_request_cancelled_error():
    # Test that CancelledError is propagated immediately
    mock_time = MockTime()
    mock_sleep = AsyncMock()
    
    session = MagicMock(spec=aiohttp.ClientSession)
    request_ctx = AsyncMock()
    session.request.return_value = request_ctx
    
    # Simulate CancelledError during request
    request_ctx.__aenter__.side_effect = asyncio.CancelledError()
    
    with pytest.raises(asyncio.CancelledError):
        await robust_json_request(
            session, "GET", "http://test",
            _sleep_func=mock_sleep,
            _time_func=mock_time.monotonic
        )

@pytest.mark.asyncio
async def test_robust_json_request_success():
    mock_time = MockTime()
    mock_sleep = AsyncMock()
    
    session = MagicMock(spec=aiohttp.ClientSession)
    request_ctx = AsyncMock()
    session.request.return_value = request_ctx
    
    response = AsyncMock()
    response.status = 200
    response.json.return_value = {"ok": True}
    request_ctx.__aenter__.return_value = response
    
    result = await robust_json_request(
        session, "GET", "http://test",
        _sleep_func=mock_sleep,
        _time_func=mock_time.monotonic
    )
    
    assert result == {"ok": True}
