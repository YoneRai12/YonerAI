import pytest

from src.utils import browser_agent


@pytest.mark.asyncio
async def test_missing_playwright_fails_at_browser_start_only():
    if browser_agent.async_playwright is not None:
        pytest.skip("Playwright is installed in this environment.")

    agent = browser_agent.BrowserAgent()

    with pytest.raises(RuntimeError, match="optional dependency 'playwright'"):
        await agent.start()
