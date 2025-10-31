"""qBittorrent API client."""
import logging
from typing import Optional

from qbittorrentapi import Client, LoginFailed, APIConnectionError

from src.config.settings import settings

logger = logging.getLogger(__name__)


class QBittorrentClient:
    """Client for interacting with qBittorrent API."""
    
    def __init__(self):
        """Initialize qBittorrent client."""
        self.client = Client(
            host=settings.qbittorrent_url,
            username=settings.qbittorrent_username,
            password=settings.qbittorrent_password
        )
        self._authenticated = False
    
    def connect(self) -> bool:
        """
        Connect and authenticate with qBittorrent API.
        
        Returns:
            True if connection successful, False otherwise
        """
        if self._authenticated:
            return True
        
        try:
            self.client.auth_log_in()
            self._authenticated = True
            logger.info("Successfully connected to qBittorrent")
            return True
        except LoginFailed as e:
            logger.error(f"qBittorrent login failed: {e}")
            return False
        except APIConnectionError as e:
            logger.error(f"qBittorrent connection error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to qBittorrent: {e}")
            return False
    
    def add_torrent(self, torrent_link: str, category: Optional[str] = None) -> bool:
        """
        Add a torrent to qBittorrent.
        
        Args:
            torrent_link: Magnet link or URL to .torrent file
            category: Optional category for the torrent
            
        Returns:
            True if torrent added successfully, False otherwise
        """
        if not self._authenticated:
            if not self.connect():
                logger.error("Cannot add torrent - not authenticated")
                return False
        
        try:
            # Add torrent via API
            self.client.torrents_add(
                urls=torrent_link,
                category=category,
                is_paused=False
            )
            logger.info(f"Successfully added torrent: {torrent_link[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to add torrent: {e}")
            return False
    
    def get_torrent_info(self, torrent_hash: Optional[str] = None) -> Optional[dict]:
        """
        Get information about torrents.
        
        Args:
            torrent_hash: Optional torrent hash to get specific torrent info
            
        Returns:
            Dictionary with torrent information or None if error
        """
        if not self._authenticated:
            if not self.connect():
                return None
        
        try:
            if torrent_hash:
                torrents = self.client.torrents_info(torrent_hashes=torrent_hash)
                return torrents[0].dict() if torrents else None
            else:
                torrents = self.client.torrents_info()
                return [t.dict() for t in torrents]
        except Exception as e:
            logger.error(f"Failed to get torrent info: {e}")
            return None
    
    def disconnect(self):
        """Disconnect from qBittorrent API."""
        try:
            if self._authenticated:
                self.client.auth_log_out()
                self._authenticated = False
        except Exception as e:
            logger.warning(f"Error during disconnect: {e}")
