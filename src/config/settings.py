"""Configuration management using Pydantic settings."""
import os
import logging
from pathlib import Path
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Telegram Bot - uses TG_BOT_TOKEN in env to avoid Windows env variable conflicts
    telegram_bot_token: str = Field(alias="TG_BOT_TOKEN")
    
    # Security: Allowed chat IDs (comma-separated list)
    # Get your chat ID by messaging @userinfobot on Telegram
    allowed_chat_ids: str = Field(default="", description="Comma-separated list of allowed Telegram chat IDs")
    
    # Rutracker
    rutracker_username: str
    rutracker_password: str
    
    # qBittorrent
    qbittorrent_url: str
    qbittorrent_username: str
    qbittorrent_password: str
    
    # Google Gemini
    google_api_key: str
    
    # TMDB (The Movie Database) - Optional, for metadata enrichment in web UI
    tmdb_api_key: str = Field(default="", description="TMDB API Key (v3) for movie/TV show metadata")
    
    # Web App Configuration
    # Note: Telegram Mini Apps require HTTPS (except localhost)
    # For local testing, you can use:
    # - http://localhost:27800 (if testing on same device)
    # - A tunnel service like ngrok or Cloudflare Tunnel
    web_app_url: str = Field(default="https://torrents.guagohomeassistant.space", description="URL for Telegram Mini App")
    web_server_host: str = Field(default="0.0.0.0", description="Host for Flask web server")
    web_server_port: int = Field(default=27800, description="Port for Flask web server")
    
    def get_allowed_chat_ids(self) -> List[int]:
        """Parse allowed_chat_ids string into a list of integers."""
        if not self.allowed_chat_ids:
            return []
        try:
            return [int(chat_id.strip()) for chat_id in self.allowed_chat_ids.split(",") if chat_id.strip()]
        except ValueError:
            logger.warning(f"Invalid chat IDs format in ALLOWED_CHAT_IDS: {self.allowed_chat_ids}")
            return []
    
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent.parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


# Global settings instance with error handling
try:
    env_file_path = Path(__file__).parent.parent.parent / ".env"
    if env_file_path.exists():
        logger.info(f"Loading .env file from: {env_file_path}")
    else:
        logger.warning(f".env file not found at {env_file_path}. Make sure you've created it!")
    
    # Check if old TELEGRAM_BOT_TOKEN is set (should use TG_BOT_TOKEN instead)
    import os
    if os.getenv("TELEGRAM_BOT_TOKEN"):
        logger.warning("TELEGRAM_BOT_TOKEN found in system environment variables!")
        logger.warning("Please use TG_BOT_TOKEN instead to avoid conflicts.")
    
    settings = Settings()
    
    # Log which token was actually loaded
    logger.info(f"Loaded token: {settings.telegram_bot_token[:10]}... (first 10 chars)")
    
except Exception as e:
    logger.error(f"Failed to load settings: {e}")
    logger.error(f"Make sure .env file exists at: {Path(__file__).parent.parent.parent / '.env'}")
    raise
