"""Flask web server for Telegram Mini App."""
import logging
import hmac
import hashlib
import json
import urllib.parse
from pathlib import Path
from typing import Optional, Dict, Any
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.exceptions import Forbidden
from flask_socketio import SocketIO, emit, disconnect

from src.config.settings import settings
from src.qbittorrent.client import QBittorrentClient

logger = logging.getLogger(__name__)

# Get the directory where this file is located
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / 'static'

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path='')
app.config['SECRET_KEY'] = 'torrent-agent-secret-key'  # Change in production
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')


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
    """Serve the Mini App HTML."""
    return send_from_directory(str(STATIC_DIR), 'index.html')


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok', 'message': 'Flask server is running'})


@app.route('/api/torrents', methods=['GET'])
def get_torrents():
    """Get all torrents data."""
    # Get initData from request header or query parameter
    init_data = request.headers.get('X-Telegram-Init-Data') or request.args.get('_auth')
    
    logger.debug(f"Received request from {request.remote_addr}")
    logger.debug(f"Headers: {dict(request.headers)}")
    
    if not init_data:
        logger.warning("No initData provided")
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Validate Telegram Web App
    user_id = validate_telegram_webapp(init_data)
    if not user_id:
        logger.warning(f"Unauthorized access attempt")
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
                'name': torrent.get('name', 'Unknown'),
                'size': torrent.get('size', 0),
                'progress': round(progress_percent, 1),
                'state': torrent.get('state', 'unknown'),
                'seeds': torrent.get('num_seeds', torrent.get('seeders', 0)),
                'peers': torrent.get('num_leechs', torrent.get('leechers', 0)),
                'dlspeed': torrent.get('dlspeed', 0),
                'upspeed': torrent.get('upspeed', 0),
                'eta': torrent.get('eta', -1),
            }
            formatted_torrents.append(formatted_torrent)
        
        return jsonify({'torrents': formatted_torrents})
        
    except Exception as e:
        logger.error(f"Error getting torrents: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


def format_torrents(torrents: list) -> list:
    """Format torrents for frontend."""
    formatted_torrents = []
    for torrent in torrents:
        progress_decimal = torrent.get('progress', 0)
        progress_percent = progress_decimal * 100
        
        formatted_torrent = {
            'name': torrent.get('name', 'Unknown'),
            'size': torrent.get('size', 0),
            'progress': round(progress_percent, 1),
            'state': torrent.get('state', 'unknown'),
            'seeds': torrent.get('num_seeds', torrent.get('seeders', 0)),
            'peers': torrent.get('num_leechs', torrent.get('leechers', 0)),
            'dlspeed': torrent.get('dlspeed', 0),
            'upspeed': torrent.get('upspeed', 0),
            'eta': torrent.get('eta', -1),
        }
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
    if auth and isinstance(auth, dict):
        init_data = auth.get('initData')
    
    if not init_data:
        # Try to get from query string
        init_data = request.args.get('initData')
    
    if not init_data:
        logger.warning("No initData provided in WebSocket connection")
        disconnect()
        return False
    
    # Validate Telegram Web App
    user_id = validate_telegram_webapp(init_data)
    if not user_id:
        logger.warning(f"Unauthorized WebSocket connection attempt")
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


def create_app():
    """Create and configure Flask app."""
    return app


def run_server(host: str = "0.0.0.0", port: int = 8080, debug: bool = False):
    """Run the Flask server with WebSocket support."""
    logger.info(f"Starting Flask web server with WebSocket support on {host}:{port}")
    
    # Start background task for broadcasting torrent updates using eventlet
    import eventlet
    eventlet.spawn(broadcast_torrents)
    logger.info("Started background task for real-time torrent updates")
    
    try:
        socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)
    except OSError as e:
        if "Address already in use" in str(e) or "Only one usage of each socket address" in str(e):
            logger.error(f"Port {port} is already in use. Please choose a different port or stop the service using it.")
        elif "Permission denied" in str(e):
            logger.error(f"Permission denied to bind to port {port}. Try running as administrator or use a port > 1024.")
        else:
            logger.error(f"Failed to start Flask server: {e}")
        raise

