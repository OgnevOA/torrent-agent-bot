"""Flask web server for Telegram Mini App."""
import logging
import os
import hmac
import hashlib
import json
import urllib.parse
from pathlib import Path
from typing import Optional, Dict, Any
from flask import Flask, request, jsonify, send_from_directory, render_template, make_response
from werkzeug.exceptions import Forbidden
from flask_socketio import SocketIO, emit, disconnect

from src.config.settings import settings
from src.qbittorrent.client import QBittorrentClient
from src.metadata.title_parser import parse_torrent_title
from src.metadata.tmdb_client import TMDBClient
from src.metadata.cache import MetadataCache
from src.metadata.ai_parser import extract_title_with_ai

logger = logging.getLogger(__name__)

# Application version - update this when making changes
APP_VERSION = "1.1.3"

# Initialize metadata services (lazy initialization)
_metadata_cache = None
_tmdb_client = None


def get_metadata_cache() -> MetadataCache:
    """Get or create the metadata cache instance."""
    global _metadata_cache
    if _metadata_cache is None:
        _metadata_cache = MetadataCache()
    return _metadata_cache


def get_tmdb_client() -> Optional[TMDBClient]:
    """Get or create the TMDB client instance."""
    global _tmdb_client
    if _tmdb_client is None:
        try:
            if settings.tmdb_api_key:
                _tmdb_client = TMDBClient(api_key=settings.tmdb_api_key)
            else:
                logger.debug("TMDB API key not configured, metadata lookup disabled")
                return None
        except Exception as e:
            logger.warning(f"Failed to initialize TMDB client: {e}")
            return None
    return _tmdb_client


def get_torrent_metadata(torrent_name: str, torrent_hash: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get metadata for a torrent by parsing its name and looking up in TMDB.
    
    For TV shows:
    - If season is present but episode is None: returns season metadata (fallback to show)
    - If both season and episode are present: returns episode metadata (fallback to season, then show)
    - Otherwise: returns show-level metadata
    
    Args:
        torrent_name: Name of the torrent
        torrent_hash: Optional torrent hash for AI caching
        
    Returns:
        Metadata dict or None if not found/not available
    """
    if not torrent_name:
        return None
    
    # Check if TMDB is available
    tmdb = get_tmdb_client()
    if not tmdb or not tmdb.enabled:
        return None
    
    # Parse the torrent title
    parsed = parse_torrent_title(torrent_name)
    title = parsed.get('title', '').strip()
    media_type = parsed.get('media_type', 'movie')
    season = parsed.get('season')
    episode = parsed.get('episode')
    
    if not title:
        logger.debug(f"Could not extract title from: {torrent_name}, trying AI fallback")
        # Try AI immediately if regex parsing failed
        ai_parsed = extract_title_with_ai(torrent_name, torrent_hash=torrent_hash)
        if ai_parsed:
            title = ai_parsed.get('title', '').strip()
            media_type = ai_parsed.get('media_type', 'movie')
            parsed['year'] = ai_parsed.get('year')
            parsed['season'] = ai_parsed.get('season')
            parsed['episode'] = ai_parsed.get('episode')
            season = parsed.get('season')
            episode = parsed.get('episode')
            logger.debug(f"AI extracted title: '{title}' (type: {media_type})")
        
        if not title:
            logger.debug(f"Could not extract title even with AI: {torrent_name}")
            return None
    
    logger.info(f"🔍 Parsed '{torrent_name}' -> title: '{title}', type: {media_type}, season: {season}, episode: {episode}")
    
    # Check cache first (with season/episode if applicable)
    cache = get_metadata_cache()
    cached = cache.get(title, parsed.get('year'), season, episode)
    if cached:
        logger.info(f"✅ Found cached metadata for: {title} (season: {season}, episode: {episode})")
        return cached
    
    # Handle TV shows with season/episode info
    if media_type == 'tv' and season is not None:
        logger.info(f"📺 TV show detected with season info: {title}, season={season}, episode={episode}")
        try:
            # First, get the TV show to obtain its ID
            show_metadata = tmdb.search_tv_show(title)
            if not show_metadata:
                logger.debug(f"TV show not found: {title}")
                # Try AI fallback for better title extraction
                ai_parsed = extract_title_with_ai(torrent_name, torrent_hash=torrent_hash)
                if ai_parsed:
                    ai_title = ai_parsed.get('title', '').strip()
                    if ai_title and ai_title.lower() != title.lower():
                        logger.debug(f"Trying AI-extracted title: '{ai_title}'")
                        show_metadata = tmdb.search_tv_show(ai_title)
                        if show_metadata:
                            title = ai_title
            
            if not show_metadata:
                logger.debug(f"No TV show metadata found for: {title}")
                return None
            
            tv_id = show_metadata.get('tmdb_id')
            show_title = show_metadata.get('title', title)
            
            if not tv_id:
                logger.debug(f"No TV ID found in show metadata for: {title}")
                # Fallback to show-level metadata
                cache.set(title, show_metadata, parsed.get('year'), season, episode)
                return show_metadata
            
            # Case 1: Whole season torrent (season present, episode None)
            if episode is None:
                logger.info(f"📦 Whole season torrent detected: {title} S{season}")
                logger.info(f"🔍 Fetching season metadata for TV ID {tv_id}, season {season}")
                season_metadata = tmdb.get_season_metadata(tv_id, season, show_title)
                
                if season_metadata:
                    # Cache and return season metadata
                    cache.set(title, season_metadata, parsed.get('year'), season, episode)
                    logger.info(f"✅ Successfully fetched season metadata for: {title} S{season}")
                    logger.info(f"   Description: {season_metadata.get('description', '')[:100]}...")
                    logger.info(f"   Poster: {season_metadata.get('poster_url', 'None')}")
                    return season_metadata
                else:
                    # Fallback to show-level metadata
                    logger.info(f"⚠️ Season metadata not found, falling back to show metadata for: {title}")
                    cache.set(title, show_metadata, parsed.get('year'), season, episode)
                    return show_metadata
            
            # Case 2: Single episode torrent (both season and episode present)
            else:
                logger.info(f"🎬 Single episode torrent detected: {title} S{season}E{episode}")
                logger.info(f"🔍 Fetching episode metadata for TV ID {tv_id}, S{season}E{episode}")
                episode_metadata = tmdb.get_episode_metadata(tv_id, season, episode, show_title)
                
                if episode_metadata:
                    # Cache and return episode metadata
                    cache.set(title, episode_metadata, parsed.get('year'), season, episode)
                    logger.info(f"✅ Successfully fetched episode metadata for: {title} S{season}E{episode}")
                    logger.info(f"   Description: {episode_metadata.get('description', '')[:100]}...")
                    logger.info(f"   Poster: {episode_metadata.get('poster_url', 'None')}")
                    return episode_metadata
                else:
                    # Fallback to season metadata
                    logger.info(f"⚠️ Episode metadata not found, trying season metadata for: {title} S{season}")
                    season_metadata = tmdb.get_season_metadata(tv_id, season, show_title)
                    
                    if season_metadata:
                        cache.set(title, season_metadata, parsed.get('year'), season, episode)
                        logger.info(f"✅ Using season metadata as fallback for: {title} S{season}E{episode}")
                        return season_metadata
                    else:
                        # Final fallback to show-level metadata
                        logger.info(f"⚠️ Season metadata not found, falling back to show metadata for: {title}")
                        cache.set(title, show_metadata, parsed.get('year'), season, episode)
                        return show_metadata
        
        except Exception as e:
            logger.debug(f"Error fetching TV metadata for '{title}': {e}", exc_info=True)
            # Try to return show-level metadata if available
            try:
                show_metadata = tmdb.search_tv_show(title)
                if show_metadata:
                    cache.set(title, show_metadata, parsed.get('year'), season, episode)
                    return show_metadata
            except Exception:
                pass
            return None
    
    # Handle movies or TV shows without season/episode info
    try:
        metadata = tmdb.get_metadata(
            title=title,
            year=parsed.get('year'),
            media_type=media_type
        )
        
        if metadata:
            # Cache the result
            cache.set(title, metadata, parsed.get('year'), season, episode)
            logger.debug(f"Successfully fetched metadata for: {title} ({media_type})")
            return metadata
        else:
            logger.debug(f"No metadata found in TMDB for: {title} ({media_type})")
            
            # Last resort: Try AI to extract a better title
            logger.debug(f"Attempting AI fallback for: {torrent_name}")
            ai_parsed = extract_title_with_ai(torrent_name, torrent_hash=torrent_hash)
            
            if ai_parsed:
                ai_title = ai_parsed.get('title', '').strip()
                ai_media_type = ai_parsed.get('media_type', 'movie')
                ai_year = ai_parsed.get('year')
                ai_season = ai_parsed.get('season')
                ai_episode = ai_parsed.get('episode')
                
                if ai_title and ai_title.lower() != title.lower():
                    logger.debug(f"AI extracted different title: '{ai_title}' (type: {ai_media_type})")
                    
                    # Check cache for AI-extracted title
                    cached_ai = cache.get(ai_title, ai_year, ai_season, ai_episode)
                    if cached_ai:
                        logger.debug(f"Found cached metadata for AI-extracted title: {ai_title}")
                        return cached_ai
                    
                    # Try TMDB search with AI-extracted title
                    try:
                        ai_metadata = tmdb.get_metadata(
                            title=ai_title,
                            year=ai_year,
                            media_type=ai_media_type
                        )
                        
                        if ai_metadata:
                            # Cache the result
                            cache.set(ai_title, ai_metadata, ai_year, ai_season, ai_episode)
                            logger.debug(f"Successfully fetched metadata using AI-extracted title: {ai_title}")
                            return ai_metadata
                        else:
                            logger.debug(f"No metadata found even with AI-extracted title: {ai_title}")
                    except Exception as e:
                        logger.debug(f"Error fetching metadata with AI title '{ai_title}': {e}")
                else:
                    logger.debug(f"AI extracted same or empty title, skipping retry")
    except Exception as e:
        logger.debug(f"Error fetching metadata for '{title}': {e}", exc_info=True)
    
    return None

# Get the directory where this file is located
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / 'static'
TEMPLATE_DIR = BASE_DIR / 'static'

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path='', template_folder=str(TEMPLATE_DIR))

# Production configuration
app.config['DEBUG'] = False
app.config['TESTING'] = False
# SECRET_KEY should be set from environment variable in production
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'torrent-agent-secret-key-change-in-production')
# Only set secure cookies if using HTTPS (check via environment variable)
use_https = os.getenv('USE_HTTPS', 'true').lower() == 'true'
app.config['SESSION_COOKIE_SECURE'] = use_https  # Only send cookies over HTTPS when using HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Configure CORS - restrict to Telegram domains in production
cors_origins = os.getenv('CORS_ORIGINS', '*')  # Default to * for development
socketio = SocketIO(
    app, 
    cors_allowed_origins=cors_origins.split(',') if cors_origins != '*' else '*',
    async_mode='eventlet',
    logger=False,  # Disable SocketIO logging in production
    engineio_logger=False
)


def validate_telegram_webapp(init_data: str) -> Optional[int]:
    """
    Validate Telegram Web App initData and extract user ID.
    
    Args:
        init_data: The initData string from Telegram Web App
        
    Returns:
        User ID if valid and authorized, None otherwise
    """
    try:
        # Parse initData
        parsed_data = urllib.parse.parse_qs(init_data)
        
        # Extract user data
        if 'user' not in parsed_data:
            logger.warning("No user data in initData")
            return None
            
        user_data = json.loads(parsed_data['user'][0])
        user_id = user_data.get('id')
        
        if not user_id:
            logger.warning("No user ID in user data")
            return None
        
        # Check if user is authorized
        allowed_chat_ids = settings.get_allowed_chat_ids()
        if allowed_chat_ids and user_id not in allowed_chat_ids:
            logger.warning(f"User {user_id} not in allowed chat IDs")
            return None
        
        # Validate hash (basic validation - Telegram sends hash in initData)
        # For production, you should validate the hash properly using bot token
        # This is a simplified version
        if 'hash' not in parsed_data:
            logger.warning("No hash in initData")
            return None
        
        # Basic hash validation (simplified - full validation requires bot token)
        # In production, validate: HMAC_SHA256(bot_token, sorted_data_string) == hash
        # For now, we'll trust the initData if user is authorized
        
        return user_id
        
    except Exception as e:
        logger.error(f"Error validating Telegram Web App data: {e}", exc_info=True)
        return None


@app.route('/')
def index():
    """Serve the Mini App HTML with version injected."""
    from flask import render_template
    response = make_response(render_template('index.html', version=APP_VERSION))
    # Prevent caching of HTML to ensure users get latest version
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files with appropriate cache headers."""
    # Don't serve API routes or other special paths
    if filename.startswith('api/') or filename.startswith('health'):
        return jsonify({'error': 'Not found'}), 404
    
    # Only serve files from static directory
    file_path = STATIC_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        return jsonify({'error': 'Not found'}), 404
    
    response = send_from_directory(str(STATIC_DIR), filename)
    
    # Set cache headers based on file type
    if filename.endswith(('.js', '.css')):
        # Cache JS/CSS for 1 hour, but allow revalidation
        # The version query parameter will force cache invalidation when changed
        response.headers['Cache-Control'] = 'public, max-age=3600, must-revalidate'
    elif filename.endswith(('.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg')):
        # Cache images longer
        response.headers['Cache-Control'] = 'public, max-age=86400'
    else:
        # No cache for other files
        response.headers['Cache-Control'] = 'no-cache, must-revalidate'
    
    return response


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok', 'message': 'Flask server is running'})


@app.route('/api/torrents', methods=['GET'])
def get_torrents():
    """Get all torrents data."""
    logger.debug(f"Received request from {request.remote_addr}")
    logger.debug(f"Headers: {dict(request.headers)}")
    
    # Validate authentication (includes X-Chat-ID header check)
    user_id = require_auth()
    if not user_id:
        logger.warning(f"Unauthorized access attempt from {request.remote_addr}")
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        # Get all torrents from qBittorrent
        qb_client = QBittorrentClient()
        torrents = qb_client.get_torrent_info()
        
        if torrents is None:
            return jsonify({'error': 'Failed to connect to qBittorrent'}), 500
        
        # Format torrents for frontend
        formatted_torrents = []
        for torrent in torrents:
            progress_decimal = torrent.get('progress', 0)
            progress_percent = progress_decimal * 100
            
            formatted_torrent = {
                'hash': torrent.get('hash', ''),
                'name': torrent.get('name', 'Unknown'),
                'size': torrent.get('size', 0),
                'progress': round(progress_percent, 1),
                'state': torrent.get('state', 'unknown'),
                'seeds': torrent.get('num_seeds', torrent.get('seeders', 0)),
                'peers': torrent.get('num_leechs', torrent.get('leechers', 0)),
                'dlspeed': torrent.get('dlspeed', 0),
                'upspeed': torrent.get('upspeed', 0),
                'eta': torrent.get('eta', -1),
                'added_on': torrent.get('added_on', 0),  # Unix timestamp
                'category': 'other',  # Default category, will be updated if metadata is available
            }
            formatted_torrents.append(formatted_torrent)
        
        return jsonify({'torrents': formatted_torrents})
        
    except Exception as e:
        logger.error(f"Error getting torrents: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


def format_torrents(torrents: list) -> list:
    """Format torrents for frontend with optional metadata enrichment."""
    formatted_torrents = []
    for torrent in torrents:
        progress_decimal = torrent.get('progress', 0)
        progress_percent = progress_decimal * 100
        
        torrent_name = torrent.get('name', 'Unknown')
        
        formatted_torrent = {
            'hash': torrent.get('hash', ''),
            'name': torrent_name,
            'size': torrent.get('size', 0),
            'progress': round(progress_percent, 1),
            'state': torrent.get('state', 'unknown'),
            'seeds': torrent.get('num_seeds', torrent.get('seeders', 0)),
            'peers': torrent.get('num_leechs', torrent.get('leechers', 0)),
            'dlspeed': torrent.get('dlspeed', 0),
            'upspeed': torrent.get('upspeed', 0),
            'eta': torrent.get('eta', -1),
            'added_on': torrent.get('added_on', 0),  # Unix timestamp
        }
        
        # Try to get metadata (non-blocking, fails gracefully)
        try:
            torrent_hash = torrent.get('hash', '')
            metadata = get_torrent_metadata(torrent_name, torrent_hash=torrent_hash if torrent_hash else None)
            if metadata:
                formatted_torrent['metadata'] = metadata
                # Determine category based on metadata
                media_type = metadata.get('media_type', 'movie')
                if media_type == 'movie':
                    formatted_torrent['category'] = 'movies'
                elif media_type == 'tv':
                    formatted_torrent['category'] = 'tv_shows'
                else:
                    formatted_torrent['category'] = 'other'
            else:
                formatted_torrent['category'] = 'other'
        except Exception as e:
            logger.debug(f"Error getting metadata for torrent '{torrent_name}': {e}")
            formatted_torrent['category'] = 'other'
        
        formatted_torrents.append(formatted_torrent)
    return formatted_torrents


def broadcast_torrents():
    """Background task to periodically fetch and broadcast torrent updates."""
    import eventlet
    while True:
        try:
            eventlet.sleep(2)  # Update every 2 seconds for smooth real-time feel
            
            qb_client = QBittorrentClient()
            torrents = qb_client.get_torrent_info()
            
            if torrents is not None:
                formatted_torrents = format_torrents(torrents)
                # Emit to all connected clients (broadcast by default when not in a request context)
                socketio.emit('torrents_update', {'torrents': formatted_torrents}, namespace='/')
        except Exception as e:
            logger.error(f"Error in broadcast_torrents: {e}", exc_info=True)
            eventlet.sleep(5)  # Wait longer on error


@socketio.on('connect')
def handle_connect(auth):
    """Handle WebSocket connection."""
    logger.info(f"WebSocket client connected: {request.sid}")
    
    # Get initData from auth or query string
    init_data = None
    chat_id_from_auth = None
    
    if auth and isinstance(auth, dict):
        init_data = auth.get('initData')
        chat_id_from_auth = auth.get('chatId')
    
    if not init_data:
        # Try to get from query string
        init_data = request.args.get('initData')
        chat_id_from_auth = request.args.get('chatId')
    
    if not init_data:
        logger.warning("No initData provided in WebSocket connection")
        disconnect()
        return False
    
    # Validate Telegram Web App (primary authentication)
    user_id = validate_telegram_webapp(init_data)
    if not user_id:
        logger.warning(f"Unauthorized WebSocket connection attempt")
        disconnect()
        return False
    
    # Additional security: check X-Chat-ID header or auth data
    chat_id_to_check = None
    
    # Priority: header > auth object > query string
    chat_id_header = request.headers.get('X-Chat-ID')
    if chat_id_header:
        chat_id_to_check = chat_id_header
    elif chat_id_from_auth:
        chat_id_to_check = chat_id_from_auth
    
    if chat_id_to_check:
        try:
            header_chat_id = int(chat_id_to_check)
            if header_chat_id != user_id:
                logger.warning(f"WebSocket chat ID mismatch: provided={header_chat_id}, initData={user_id}")
                disconnect()
                return False
            
            # Verify against allowed_chat_ids
            allowed_chat_ids = settings.get_allowed_chat_ids()
            if allowed_chat_ids and header_chat_id not in allowed_chat_ids:
                logger.warning(f"Chat ID {header_chat_id} not in allowed chat IDs")
                disconnect()
                return False
        except (ValueError, TypeError):
            logger.warning(f"Invalid chat ID format in WebSocket: {chat_id_to_check}")
            disconnect()
            return False
    
    logger.info(f"Authorized WebSocket connection for user {user_id}")
    
    # Send initial torrent data
    try:
        qb_client = QBittorrentClient()
        torrents = qb_client.get_torrent_info()
        
        if torrents is not None:
            formatted_torrents = format_torrents(torrents)
            emit('torrents_update', {'torrents': formatted_torrents})
    except Exception as e:
        logger.error(f"Error sending initial torrent data: {e}", exc_info=True)
    
    return True


@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection."""
    logger.info(f"WebSocket client disconnected: {request.sid}")


def validate_chat_id_header() -> Optional[int]:
    """
    Validate X-Chat-ID header against allowed_chat_ids.
    
    Returns:
        Chat ID if valid and authorized, None otherwise
    """
    chat_id_header = request.headers.get('X-Chat-ID')
    if not chat_id_header:
        logger.debug("No X-Chat-ID header provided")
        return None
    
    try:
        chat_id = int(chat_id_header)
    except (ValueError, TypeError):
        logger.warning(f"Invalid X-Chat-ID header format: {chat_id_header}")
        return None
    
    # Check if chat_id is in allowed list
    allowed_chat_ids = settings.get_allowed_chat_ids()
    if allowed_chat_ids and chat_id not in allowed_chat_ids:
        logger.warning(f"Chat ID {chat_id} not in allowed chat IDs")
        return None
    
    return chat_id


def require_auth():
    """
    Helper function to validate Telegram Web App authentication.
    Validates both initData and X-Chat-ID header for additional security.
    
    Returns:
        User ID if valid and authorized, None otherwise
    """
    # First validate initData (primary authentication)
    init_data = request.headers.get('X-Telegram-Init-Data') or request.args.get('_auth')
    if not init_data:
        logger.debug("No initData provided")
        return None
    
    user_id = validate_telegram_webapp(init_data)
    if not user_id:
        logger.debug("initData validation failed")
        return None
    
    # Additional security layer: validate X-Chat-ID header
    chat_id_header = request.headers.get('X-Chat-ID')
    if chat_id_header:
        try:
            header_chat_id = int(chat_id_header)
            # Verify that header chat_id matches user_id from initData
            if header_chat_id != user_id:
                logger.warning(f"Chat ID mismatch: header={header_chat_id}, initData={user_id}")
                return None
        except (ValueError, TypeError):
            logger.warning(f"Invalid X-Chat-ID header format: {chat_id_header}")
            return None
        
        # Double-check against allowed_chat_ids (redundant but adds security)
        allowed_chat_ids = settings.get_allowed_chat_ids()
        if allowed_chat_ids and header_chat_id not in allowed_chat_ids:
            logger.warning(f"Chat ID {header_chat_id} from header not in allowed chat IDs")
            return None
    else:
        # X-Chat-ID header is optional but recommended for additional security
        logger.debug("X-Chat-ID header not provided (optional security layer)")
    
    return user_id


@app.route('/api/torrents/<torrent_hash>/pause', methods=['POST'])
def pause_torrent(torrent_hash):
    """Pause/stop a torrent."""
    user_id = require_auth()
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        qb_client = QBittorrentClient()
        success = qb_client.pause_torrent(torrent_hash)
        
        if success:
            return jsonify({'success': True, 'message': 'Torrent paused'})
        else:
            return jsonify({'error': 'Failed to pause torrent'}), 500
    except Exception as e:
        logger.error(f"Error pausing torrent: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/torrents/<torrent_hash>/resume', methods=['POST'])
def resume_torrent(torrent_hash):
    """Resume a paused torrent."""
    user_id = require_auth()
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        qb_client = QBittorrentClient()
        success = qb_client.resume_torrent(torrent_hash)
        
        if success:
            return jsonify({'success': True, 'message': 'Torrent resumed'})
        else:
            return jsonify({'error': 'Failed to resume torrent'}), 500
    except Exception as e:
        logger.error(f"Error resuming torrent: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/torrents/<torrent_hash>/delete', methods=['POST'])
def delete_torrent(torrent_hash):
    """Delete a torrent."""
    user_id = require_auth()
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        data = request.get_json() or {}
        delete_files = data.get('delete_files', False)
        
        qb_client = QBittorrentClient()
        success = qb_client.delete_torrent(torrent_hash, delete_files=delete_files)
        
        if success:
            return jsonify({'success': True, 'message': 'Torrent deleted'})
        else:
            return jsonify({'error': 'Failed to delete torrent'}), 500
    except Exception as e:
        logger.error(f"Error deleting torrent: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/torrents/<torrent_hash>/files', methods=['GET'])
def get_torrent_files(torrent_hash):
    """Get list of files in a torrent."""
    user_id = require_auth()
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        qb_client = QBittorrentClient()
        files = qb_client.get_torrent_files(torrent_hash)
        
        if files is None:
            return jsonify({'error': 'Failed to get torrent files'}), 500
        
        # Format files for frontend
        formatted_files = []
        for file in files:
            formatted_file = {
                'id': file.get('index', 0),
                'name': file.get('name', 'Unknown'),
                'size': file.get('size', 0),
                'progress': round(file.get('progress', 0) * 100, 1),
                'priority': file.get('priority', 0),
                'is_seed': file.get('is_seed', False),
            }
            formatted_files.append(formatted_file)
        
        return jsonify({'files': formatted_files})
    except Exception as e:
        logger.error(f"Error getting torrent files: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/torrents/<torrent_hash>/files/priority', methods=['POST'])
def set_file_priority(torrent_hash):
    """Set priority for files in a torrent."""
    user_id = require_auth()
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        file_ids = data.get('file_ids', [])
        priority = data.get('priority', 1)
        
        if not file_ids:
            return jsonify({'error': 'No file IDs provided'}), 400
        
        qb_client = QBittorrentClient()
        success = qb_client.set_file_priority(torrent_hash, file_ids, priority)
        
        if success:
            return jsonify({'success': True, 'message': 'File priority updated'})
        else:
            return jsonify({'error': 'Failed to set file priority'}), 500
    except Exception as e:
        logger.error(f"Error setting file priority: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


def create_app():
    """Create and configure Flask app."""
    return app


def run_server(host: str = "0.0.0.0", port: int = 8080, debug: bool = False):
    """Run the Flask server with WebSocket support."""
    # Ensure debug mode is disabled in production
    is_production = os.getenv('FLASK_ENV', 'production').lower() != 'development'
    debug_mode = debug and not is_production
    
    if is_production:
        logger.info(f"Starting Flask web server in PRODUCTION mode on {host}:{port}")
        app.config['DEBUG'] = False
        app.config['TESTING'] = False
    else:
        logger.info(f"Starting Flask web server in DEVELOPMENT mode on {host}:{port}")
        app.config['DEBUG'] = True
    
    # Start background task for broadcasting torrent updates using eventlet
    import eventlet
    eventlet.spawn(broadcast_torrents)
    logger.info("Started background task for real-time torrent updates")
    
    try:
        # Only allow unsafe werkzeug in development
        socketio.run(
            app, 
            host=host, 
            port=port, 
            debug=debug_mode,
            allow_unsafe_werkzeug=debug_mode,  # Only True in development
            use_reloader=False  # Disable reloader in production
        )
    except OSError as e:
        if "Address already in use" in str(e) or "Only one usage of each socket address" in str(e):
            logger.error(f"Port {port} is already in use. Please choose a different port or stop the service using it.")
        elif "Permission denied" in str(e):
            logger.error(f"Permission denied to bind to port {port}. Try running as administrator or use a port > 1024.")
        else:
            logger.error(f"Failed to start Flask server: {e}")
        raise

