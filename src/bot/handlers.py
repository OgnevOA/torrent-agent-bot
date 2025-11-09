"""Telegram bot command and message handlers."""
import logging
import re
from typing import List, Optional

from telegram import Update
from telegram.ext import ContextTypes

from src.scrapers.rutracker import RutrackerScraper
from src.scrapers.models import TorrentResult
from src.agent.langchain_agent import TorrentSearchAgent
from src.qbittorrent.client import QBittorrentClient
from src.bot.middleware import require_authorized_chat

logger = logging.getLogger(__name__)


def format_bytes(bytes_size: int) -> str:
    """
    Format bytes to human-readable format.
    
    Args:
        bytes_size: Size in bytes
        
    Returns:
        Formatted string (e.g., "1.5 MB", "500 KB")
    """
    if bytes_size == 0:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}" if bytes_size >= 1 else f"{bytes_size:.0f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} PB"


def format_speed(bytes_per_sec: int) -> str:
    """
    Format download/upload speed to human-readable format.
    
    Args:
        bytes_per_sec: Speed in bytes per second
        
    Returns:
        Formatted string (e.g., "1.2 MB/s", "500 KB/s")
    """
    return format_bytes(bytes_per_sec) + "/s"


def format_eta(eta_seconds: int) -> str:
    """
    Format ETA from seconds to human-readable format.
    
    Args:
        eta_seconds: ETA in seconds (-1 if unknown)
        
    Returns:
        Formatted string (e.g., "10m", "1h 30m", "∞")
    """
    if eta_seconds < 0:
        return "∞"
    
    if eta_seconds < 60:
        return f"{eta_seconds}s"
    elif eta_seconds < 3600:
        minutes = eta_seconds // 60
        seconds = eta_seconds % 60
        return f"{minutes}m{seconds}s" if seconds > 0 else f"{minutes}m"
    else:
        hours = eta_seconds // 3600
        minutes = (eta_seconds % 3600) // 60
        if minutes > 0:
            return f"{hours}h {minutes}m"
        return f"{hours}h"


def format_torrent_status(torrent: dict) -> str:
    """
    Format individual torrent status into compact single-line format.
    
    Args:
        torrent: Torrent dictionary from qBittorrent API
        
    Returns:
        Formatted string with emoji and torrent info
    """
    name = torrent.get('name', 'Unknown')
    state = torrent.get('state', '')
    progress_decimal = torrent.get('progress', 0)  # 0-1 decimal
    progress = progress_decimal * 100  # Convert to percentage
    dlspeed = torrent.get('dlspeed', 0)
    upspeed = torrent.get('upspeed', 0)
    eta = torrent.get('eta', -1)
    size = torrent.get('size', 0)
    # Calculate completed size from progress
    completed = int(size * progress_decimal) if size > 0 else 0
    # Try multiple possible field names for seeds/leechers
    num_seeds = torrent.get('num_seeds', torrent.get('seeders', 0))
    num_leechs = torrent.get('num_leechs', torrent.get('leechers', 0))
    num_complete = torrent.get('num_complete', 0)
    num_incomplete = torrent.get('num_incomplete', 0)
    
    # Format seeds and leechers with complete/incomplete counts
    seeds_str = f"{num_seeds}({num_complete})"
    leechs_str = f"{num_leechs}({num_incomplete})"
    
    # Choose emoji based on state
    if state == 'downloading':
        emoji = '🟢'
    elif state in ['seeding', 'uploading', 'stalledUP', 'queuedUP']:
        emoji = '🔵'
    else:
        emoji = '⚪'
    
    # Truncate long names (max 50 chars)
    if len(name) > 50:
        name = name[:47] + "..."
    
    # Format progress
    progress_str = f"{progress:.1f}%" if progress < 100 else "100%"
    
    # Format speeds
    dl_speed_str = format_speed(dlspeed) if dlspeed > 0 else "0 B/s"
    up_speed_str = format_speed(upspeed) if upspeed > 0 else "0 B/s"
    
    # Format ETA
    eta_str = format_eta(int(eta))
    
    # Format size
    size_str = format_bytes(size)
    completed_str = format_bytes(completed) if completed > 0 else "0 B"
    
    # Build status line
    if state == 'downloading':
        status_line = (
            f"{emoji} *{name}*\n"
            f"   {progress_str} • ↓ {dl_speed_str} • ↑ {up_speed_str} • ETA: {eta_str}\n"
            f"   {completed_str} / {size_str} • 🌱 {seeds_str} • 🐛 {leechs_str}"
        )
    elif state in ['seeding', 'uploading', 'stalledUP', 'queuedUP']:  # seeding/uploading states
        status_line = (
            f"{emoji} *{name}*\n"
            f"   {progress_str} • ↓ {dl_speed_str} • ↑ {up_speed_str}\n"
            f"   {size_str} • 🌱 {seeds_str} • 🐛 {leechs_str}"
        )
    else:
        status_line = (
            f"{emoji} *{name}*\n"
            f"   {progress_str} • ↓ {dl_speed_str} • ↑ {up_speed_str}\n"
            f"   {size_str} • 🌱 {seeds_str} • 🐛 {leechs_str}"
        )
    
    return status_line


@require_authorized_chat
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    logger.info(f"Received /start command from user {update.effective_user.id}")
    welcome_message = """
🤖 *Torrent Agent Bot*

I can help you search for torrents on rutracker.org and add them directly to your qBittorrent!

*How to use:*
1. Send me a natural language search query (e.g., "Find X, with russian dub, Fox Crime preferred")
2. I'll search rutracker.org and show you numbered results
3. Reply with the number (e.g., "Download the third one" or "3")
4. I'll add it to your qBittorrent automatically

*Commands:*
• /status - View active torrents (downloading/seeding)

*Examples:*
• "Find Matrix movie torrent with good seeders"
• "Find X, with russian dub, Fox Crime preferred"
• "Latest Linux distribution ISO"

Send /help for more information.
"""
    await update.message.reply_text(
        welcome_message,
        parse_mode="Markdown"
    )


@require_authorized_chat
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_message = """
📚 *Help*

*Commands:*
/start - Show welcome message
/help - Show this help message
/search - Start a new search
/status - Show active torrents (downloading/seeding)

*Usage:*
1. Send me a natural language search query (e.g., "Find X, with russian dub, Fox Crime preferred")
2. I'll search rutracker.org and show you numbered results
3. Reply with the number (e.g., "Download the third one" or "3") to add it to qBittorrent

You can specify:
• Search terms (e.g., "Matrix movie")
• Audio preferences (e.g., "russian dub", "english audio")
• Preferred sources/channels (e.g., "Fox Crime preferred")
• Minimum seeders (e.g., "with good seeders")
"""
    await update.message.reply_text(
        help_message,
        parse_mode="Markdown"
    )


@require_authorized_chat
async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /search command."""
    await update.message.reply_text(
        "🔍 Send me a search query. For example: 'Find Matrix movie torrent'"
    )


@require_authorized_chat
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command - show active torrents."""
    logger.info(f"Received /status command from user {update.effective_user.id}")
    
    status_message = await update.message.reply_text("⏳ Fetching torrent status...")
    
    try:
        qb_client = QBittorrentClient()
        active_torrents = qb_client.get_active_torrents()
        
        if active_torrents is None:
            await status_message.edit_text(
                "❌ Failed to connect to qBittorrent.\n\n"
                "Please check:\n"
                "• qBittorrent is running\n"
                "• API is enabled in qBittorrent settings\n"
                "• Connection details are correct"
            )
            return
        
        if not active_torrents:
            await status_message.edit_text(
                "✅ No active torrents (downloading or seeding) at the moment."
            )
            return
        
        # Format torrents
        formatted_lines = ["📊 *Active Torrents:*\n"]
        for torrent in active_torrents:
            formatted_lines.append(format_torrent_status(torrent))
            formatted_lines.append("")  # Empty line between torrents
        
        message = "\n".join(formatted_lines)
        
        # Telegram has a 4096 character limit per message
        if len(message) > 4000:
            # Split into multiple messages if too long
            # For now, truncate and add note
            truncated_count = 0
            truncated_message = formatted_lines[0]  # Keep header
            for i, line in enumerate(formatted_lines[1:], 1):
                test_message = truncated_message + "\n" + line
                if len(test_message) > 4000:
                    truncated_count = len(active_torrents) - (i // 3)  # Approximate
                    break
                truncated_message = test_message
            message = truncated_message
            if truncated_count > 0:
                message += f"\n\n... and {truncated_count} more torrents"
        
        await status_message.edit_text(
            message,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error getting torrent status: {e}", exc_info=True)
        await status_message.edit_text(
            f"❌ Error getting torrent status: {str(e)}\n\nPlease try again."
        )


@require_authorized_chat
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route messages to either download request or new search."""
    # Check if we have search results and this looks like a download request
    if context.user_data.get("search_results"):
        user_message = update.message.text.lower().strip()
        
        # Check for download keywords
        download_keywords = ['download', 'get', 'add', 'take', 'select', 'choose', 'send']
        has_download_keyword = any(keyword in user_message for keyword in download_keywords)
        
        # Check for numbers (digits or words)
        has_number = bool(re.search(r'\b\d+\b', update.message.text)) or any(
            word in user_message for word in ['first', 'second', 'third', 'fourth', 'fifth',
                                               'sixth', 'seventh', 'eighth', 'ninth', 'tenth',
                                               'one', 'two', 'three', 'four', 'five',
                                               'six', 'seven', 'eight', 'nine', 'ten']
        )
        
        # Check if message is just a number (likely a download request)
        is_just_number = user_message.isdigit() or user_message in ['first', 'second', 'third', 'fourth', 'fifth',
                                                                    'sixth', 'seventh', 'eighth', 'ninth', 'tenth',
                                                                    'one', 'two', 'three', 'four', 'five',
                                                                    'six', 'seven', 'eight', 'nine', 'ten']
        
        # If it's just a number or has download keywords with numbers, treat as download request
        if is_just_number or (has_download_keyword and has_number):
            return await handle_download_request(update, context)
    
    # Otherwise treat as new search
    return await handle_search_message(update, context)


async def handle_search_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle natural language search queries."""
    user_query = update.message.text
    
    if not user_query or not user_query.strip():
        await update.message.reply_text("Please provide a search query.")
        return
    
    # Send "searching" message
    status_message = await update.message.reply_text("🔍 Searching rutracker.org...")
    
    try:
        # Initialize components
        agent = TorrentSearchAgent()
        scraper = RutrackerScraper()
        
        # Parse query using LangChain agent
        search_query = agent.parse_query(user_query)
        
        # Update status
        await status_message.edit_text(
            f"🔍 Searching for: *{search_query.query}*...",
            parse_mode="Markdown"
        )
        
        # Search rutracker
        results = scraper.search(search_query.query, max_results=search_query.max_results)
        
        # Apply filters if specified
        if search_query.min_seeders:
            results = [r for r in results if r.seeders and r.seeders >= search_query.min_seeders]
        
        if not results:
            await status_message.edit_text(
                f"❌ No torrents found for: *{search_query.query}*\n\n"
                "Try a different search term or check your spelling.",
                parse_mode="Markdown"
            )
            return
        
        # Store results in context for text-based selection
        context.user_data["search_results"] = results
        context.user_data["last_query"] = user_query
        
        # Format and send results
        formatted_message = agent.format_results(results, search_query.query)
        formatted_message += "\n📥 *To download, reply with:*\n"
        formatted_message += "• The number (e.g., \"3\")\n"
        formatted_message += "• Or \"Download the third one\"\n"
        formatted_message += "• Or \"Download number 3\""
        
        await status_message.edit_text(
            formatted_message,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error during search: {e}", exc_info=True)
        await status_message.edit_text(
            f"❌ Error searching for torrents: {str(e)}\n\nPlease try again."
        )


def extract_torrent_number(text: str) -> Optional[int]:
    """
    Extract torrent number from text like "Download the third one", "3", "number 3", etc.
    
    Args:
        text: User's message text
        
    Returns:

    """
    text = text.lower().strip()
    
    # Check if it's a direct number
    match = re.search(r'\b(\d+)\b', text)
    if match:
        return int(match.group(1))
    
    # Check for ordinal words
    ordinals = {
        'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5,
        'sixth': 6, 'seventh': 7, 'eighth': 8, 'ninth': 9, 'tenth': 10,
        '1st': 1, '2nd': 2, '3rd': 3, '4th': 4, '5th': 5,
        '6th': 6, '7th': 7, '8th': 8, '9th': 9, '10th': 10
    }
    
    for word, num in ordinals.items():
        if word in text:
            return num
    
    # Check for "one", "two", "three" etc.
    numbers = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
    }
    
    for word, num in numbers.items():
        if word in text:
            return num
    
    return None


async def handle_download_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text replies requesting to download a torrent by number."""
    user_message = update.message.text
    
    # Check if this looks like a download request
    download_keywords = ['download', 'get', 'add', 'take', 'select', 'choose', 'send']
    has_download_keyword = any(keyword in user_message.lower() for keyword in download_keywords)
    has_number = bool(re.search(r'\b\d+\b', user_message)) or any(
        word in user_message.lower() for word in ['first', 'second', 'third', 'one', 'two', 'three']
    )
    
    # Only process if it looks like a download request and we have search results
    if not context.user_data.get("search_results"):
        # Not a download request, might be a new search
        return await handle_search_message(update, context)
    
    if not (has_download_keyword or has_number):
        # Doesn't look like a download request, treat as new search
        return await handle_search_message(update, context)
    
    try:
        # Extract torrent number
        torrent_number = extract_torrent_number(user_message)
        
        if torrent_number is None:
            await update.message.reply_text(
                "❌ Could not understand which torrent to download.\n\n"
                "Please reply with a number (e.g., \"3\") or \"Download the third one\""
            )
            return
        
        # Convert to 0-based index
        torrent_index = torrent_number - 1
        
        results: List[TorrentResult] = context.user_data.get("search_results")
        
        if not results or torrent_index < 0 or torrent_index >= len(results):
            await update.message.reply_text(
                f"❌ Torrent #{torrent_number} not found.\n\n"
                f"Please choose a number between 1 and {len(results)}."
            )
            return
        
        selected_torrent = results[torrent_index]
        
        # Send confirmation message
        status_message = await update.message.reply_text(
            f"⏳ Adding torrent #{torrent_number} to qBittorrent...\n\n"
            f"*{selected_torrent.title}*",
            parse_mode="Markdown"
        )
        
        # Initialize qBittorrent client
        qb_client = QBittorrentClient()
        
        # Get download link (magnet or URL)
        # rutracker-api provides magnet links directly from search results
        torrent_link = None
        if selected_torrent.magnet:
            torrent_link = selected_torrent.magnet
        elif selected_torrent.download_url:
            torrent_link = selected_torrent.download_url
        else:
            # Fallback: try to get magnet from torrent page if we have URL
            if selected_torrent.url:
                logger.warning("No magnet link available, trying to get from torrent page")
                scraper = RutrackerScraper()
                scraper.login()
                torrent_link = scraper.get_torrent_download_url(selected_torrent.url)
        
        if not torrent_link:
            await status_message.edit_text(
                f"❌ Could not get download link for torrent #{torrent_number}.\n\n"
                "Please try selecting another torrent."
            )
            return
        
        # Add to qBittorrent
        success = qb_client.add_torrent(torrent_link)
        
        if success:
            await status_message.edit_text(
                f"✅ *Torrent #{torrent_number} added successfully!*\n\n"
                f"*{selected_torrent.title}*\n\n"
                "Check your qBittorrent to see the download.",
                parse_mode="Markdown"
            )
            # Clear search results to allow new search
            context.user_data.pop("search_results", None)
        else:
            await status_message.edit_text(
                f"❌ Failed to add torrent #{torrent_number} to qBittorrent.\n\n"
                "Please check:\n"
                "• qBittorrent is running\n"
                "• API is enabled in qBittorrent settings\n"
                "• Connection details are correct"
            )
        
    except Exception as e:
        logger.error(f"Error adding torrent: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Error adding torrent: {str(e)}\n\nPlease try again."
        )




async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors in the bot."""
    logger.error(f"Exception while handling an update: {context.error}", exc_info=True)
    
    if isinstance(update, Update) and update.message:
        await update.message.reply_text(
            "❌ An error occurred. Please try again or use /help for assistance."
        )
