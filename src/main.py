"""Entry point and bot initialization."""
import logging
import sys
import threading
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from src.bot.handlers import (
    start_command,
    help_command,
    search_command,
    status_command,
    ui_command,
    handle_message,
    error_handler
)
from src.config.settings import settings
from src.web.server import run_server


# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("torrent_bot.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def create_application() -> Application:
    """Create and configure the Telegram bot application."""
    # Create application
    application = Application.builder().token(settings.telegram_bot_token).build()
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("ui", ui_command))
    
    # Register message handler for text messages (routes to search or download)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message
    ))
    
    # Register error handler
    application.add_error_handler(error_handler)
    
    return application


def main():
    """Main entry point."""
    try:
        logger.info("Starting Torrent Agent Telegram Bot...")
        
        # Validate configuration
        if not settings.telegram_bot_token or settings.telegram_bot_token == "your_telegram_bot_token_here":
            logger.error("TG_BOT_TOKEN not set or still has placeholder value!")
            logger.error("Please set TG_BOT_TOKEN in your .env file")
            sys.exit(1)
        
        if not settings.google_api_key or settings.google_api_key == "your_google_api_key_here":
            logger.error("GOOGLE_API_KEY not set or still has placeholder value!")
            logger.error("Please set GOOGLE_API_KEY in your .env file")
            sys.exit(1)
        
        logger.info("Configuration loaded successfully")
        logger.info(f"Bot token being used: {settings.telegram_bot_token[:10]}... (first 10 chars)")
        logger.info(f"Full token starts with: {settings.telegram_bot_token[:20]}...")
        
        # Verify the token matches what user expects
        if not settings.telegram_bot_token.startswith("8441904924"):
            logger.warning("⚠️  WARNING: Token doesn't start with expected value!")
            logger.warning(f"   Expected: 8441904924...")
            logger.warning(f"   Got:      {settings.telegram_bot_token[:20]}...")
            logger.warning("   This might be from system environment variables, not .env file!")
        
        # Start Flask web server in background thread
        web_server_thread = threading.Thread(
            target=run_server,
            args=(settings.web_server_host, settings.web_server_port, False),
            daemon=True,
            name="FlaskWebServer"
        )
        web_server_thread.start()
        logger.info(f"Flask web server started on {settings.web_server_host}:{settings.web_server_port}")
        logger.info(f"Web app URL: {settings.web_app_url}")
        
        # Create and run application
        application = create_application()
        
        logger.info("Bot is running. Press Ctrl+C to stop.")
        logger.info("Try sending /start to your bot on Telegram")
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        logger.error("Check the error above and verify your .env file is configured correctly")
        sys.exit(1)


if __name__ == "__main__":
    main()
