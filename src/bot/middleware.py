"""Security middleware for Telegram bot."""
import logging
from functools import wraps
from typing import Callable, List, Optional

from telegram import Update
from telegram.ext import ContextTypes

from src.config.settings import settings

logger = logging.getLogger(__name__)

# Cache parsed chat IDs
_allowed_chat_ids: Optional[List[int]] = None


def get_allowed_chat_ids() -> List[int]:
    """Get list of allowed chat IDs, cached."""
    global _allowed_chat_ids
    if _allowed_chat_ids is None:
        _allowed_chat_ids = settings.get_allowed_chat_ids()
        if _allowed_chat_ids:
            logger.info(f"Security enabled: Bot will only respond to {len(_allowed_chat_ids)} allowed chat ID(s)")
        else:
            logger.warning("Security disabled: No ALLOWED_CHAT_IDS configured. Bot will respond to everyone!")
    return _allowed_chat_ids


def require_authorized_chat(func: Callable) -> Callable:
    """
    Decorator to restrict bot commands to authorized chat IDs only.
    
    Usage:
        @require_authorized_chat
        async def my_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            ...
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        # Check if security is enabled
        allowed_ids = get_allowed_chat_ids()
        
        if not allowed_ids:
            # Security disabled - allow all
            return await func(update, context, *args, **kwargs)
        
        # Get chat ID from update
        chat_id = None
        if update.message:
            chat_id = update.message.chat_id
        elif update.callback_query:
            chat_id = update.callback_query.message.chat_id
        elif update.edited_message:
            chat_id = update.edited_message.chat_id
        
        if chat_id is None:
            logger.warning("Could not determine chat ID from update")
            return
        
        # Check if chat ID is allowed
        if chat_id not in allowed_ids:
            logger.warning(f"Unauthorized access attempt from chat ID: {chat_id}")
            # Send a message only if we have a message to reply to
            if update.message:
                await update.message.reply_text(
                    "❌ Access denied. This bot is restricted to authorized users only."
                )
            return
        
        # Chat ID is authorized - proceed
        return await func(update, context, *args, **kwargs)
    
    return wrapper

