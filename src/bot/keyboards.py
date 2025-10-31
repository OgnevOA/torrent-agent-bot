"""Inline keyboards for torrent selection."""
from typing import List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.scrapers.models import TorrentResult


def create_torrent_selection_keyboard(torrents: List[TorrentResult]) -> InlineKeyboardMarkup:
    """
    Create an inline keyboard for torrent selection.
    
    Args:
        torrents: List of TorrentResult objects
        
    Returns:
        InlineKeyboardMarkup with buttons for each torrent
    """
    keyboard = []
    
    for i, torrent in enumerate(torrents):
        # Truncate title if too long
        button_text = torrent.title
        if len(button_text) > 50:
            button_text = button_text[:47] + "..."
        
        # Add seeders info if available
        if torrent.seeders is not None:
            button_text += f" ⬆️{torrent.seeders}"
        
        # Use index as callback data to identify which torrent was selected
        callback_data = f"torrent_{i}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    return InlineKeyboardMarkup(keyboard)


def create_add_torrent_keyboard(torrent_index: int, download_url: str, magnet: str = None) -> InlineKeyboardMarkup:
    """
    Create keyboard for adding a specific torrent to qBittorrent.
    
    Args:
        torrent_index: Index of the torrent in the original list
        download_url: Download URL for the torrent
        magnet: Optional magnet link
        
    Returns:
        InlineKeyboardMarkup with add button
    """
    # Store the download URL in callback data (with prefix to identify)
    # Note: Telegram callback data is limited to 64 bytes, so we'll use index and fetch URL separately
    callback_data = f"add_{torrent_index}"
    
    buttons = [
        [InlineKeyboardButton("✅ Add to qBittorrent", callback_data=callback_data)]
    ]
    
    return InlineKeyboardMarkup(buttons)
