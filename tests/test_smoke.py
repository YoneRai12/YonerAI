import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from src.bot import ORABot
from src.config import Config

@pytest.mark.asyncio
async def test_bot_setup_hook():
    # Mock Config
    mock_config = MagicMock(spec=Config)
    mock_config.app_id = 12345
    mock_config.token = "test_token"
    mock_config.search_api_key = "test_key"
    mock_config.search_engine = "google"
    mock_config.voicevox_api_url = "http://localhost:50021"
    mock_config.voicevox_speaker_id = 1
    mock_config.stt_model = "base"
    mock_config.public_base_url = "http://localhost:8000"
    mock_config.ora_api_base_url = "http://localhost:8000"
    mock_config.privacy_default = "public"
    mock_config.speak_search_progress_default = True
    mock_config.dev_guild_id = None
    mock_config.llm_base_url = "http://localhost:1234"
    mock_config.llm_api_key = "test"
    mock_config.llm_model = "test-model"
    mock_config.db_path = "test.db"
    mock_config.log_level = "INFO"

    # Mock Dependencies
    mock_link_client = MagicMock()
    mock_store = MagicMock()
    mock_llm_client = MagicMock()
    mock_session = MagicMock()
    
    # Mock Intents
    mock_intents = MagicMock()
    
    # Initialize Bot
    bot = ORABot(
        config=mock_config,
        link_client=mock_link_client,
        store=mock_store,
        llm_client=mock_llm_client,
        intents=mock_intents,
        session=mock_session
    )
    
    # Mock internal methods/attributes used in setup_hook
    bot.add_cog = AsyncMock()
    bot.load_extension = AsyncMock()
    bot.tree = MagicMock()
    bot.tree.sync = AsyncMock()
    
    # Mock external classes used in setup_hook
    with patch("src.bot.SearchClient"), \
         patch("src.bot.VoiceVoxClient"), \
         patch("src.bot.WhisperClient"), \
         patch("src.bot.VoiceManager"), \
         patch("src.bot.CoreCog"), \
         patch("src.bot.ORACog"), \
         patch("src.bot.MediaCog"):
        
        # Run setup_hook
        await bot.setup_hook()
        
        # Verify extensions loaded
        # We expect at least voice_recv and system
        assert bot.load_extension.call_count >= 2
        
        # Verify cogs added
        # Core, ORA, Media
        assert bot.add_cog.call_count >= 3
