"""qBittorrent API client."""
import logging
from typing import Optional, List

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
                return dict(torrents[0]) if torrents else None
            else:
                torrents = self.client.torrents_info()
                return [dict(t) for t in torrents]
        except Exception as e:
            logger.error(f"Failed to get torrent info: {e}")
            return None
    
    def get_active_torrents(self) -> Optional[List[dict]]:
        """
        Get active torrents (downloading and seeding, excluding queued).
        
        Returns:
            List of active torrent dictionaries or None if error
        """
        if not self._authenticated:
            if not self.connect():
                return None
        
        try:
            torrents = self.client.torrents_info()
            # Filter to only downloading and seeding torrents
            # Seeding states: 'uploading', 'stalledUP', 'queuedUP'
            # Downloading states: 'downloading', 'stalledDL', 'queuedDL'
            active_torrents = [
                dict(t) for t in torrents 
                if t.state in ['downloading', 'seeding', 'uploading', 'stalledUP']
            ]
            return active_torrents
        except Exception as e:
            logger.error(f"Failed to get active torrents: {e}")
            return None
    
    def pause_torrent(self, torrent_hash: str) -> bool:
        """
        Pause/stop a torrent.
        
        Args:
            torrent_hash: Hash of the torrent to pause
            
        Returns:
            True if paused successfully, False otherwise
        """
        if not self._authenticated:
            if not self.connect():
                return False
        
        try:
            self.client.torrents_pause(torrent_hashes=torrent_hash)
            logger.info(f"Successfully paused torrent: {torrent_hash[:8]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to pause torrent: {e}")
            return False
    
    def resume_torrent(self, torrent_hash: str) -> bool:
        """
        Resume a paused torrent.
        
        Args:
            torrent_hash: Hash of the torrent to resume
            
        Returns:
            True if resumed successfully, False otherwise
        """
        if not self._authenticated:
            if not self.connect():
                return False
        
        try:
            self.client.torrents_resume(torrent_hashes=torrent_hash)
            logger.info(f"Successfully resumed torrent: {torrent_hash[:8]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to resume torrent: {e}")
            return False
    
    def delete_torrent(self, torrent_hash: str, delete_files: bool = False) -> bool:
        """
        Delete a torrent.
        
        Args:
            torrent_hash: Hash of the torrent to delete
            delete_files: If True, also delete downloaded files
            
        Returns:
            True if deleted successfully, False otherwise
        """
        if not self._authenticated:
            if not self.connect():
                return False
        
        try:
            self.client.torrents_delete(
                torrent_hashes=torrent_hash,
                delete_files=delete_files
            )
            logger.info(f"Successfully deleted torrent: {torrent_hash[:8]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to delete torrent: {e}")
            return False
    
    def get_torrent_files(self, torrent_hash: str) -> Optional[List[dict]]:
        """
        Get list of files in a torrent.
        
        Args:
            torrent_hash: Hash of the torrent
            
        Returns:
            List of file dictionaries or None if error
        """
        if not self._authenticated:
            if not self.connect():
                return None
        
        try:
            files = self.client.torrents_files(torrent_hash=torrent_hash)
            return [dict(f) for f in files]
        except Exception as e:
            logger.error(f"Failed to get torrent files: {e}")
            return None
    
    def set_file_priority(self, torrent_hash: str, file_ids: List[int], priority: int) -> bool:
        """
        Set priority for files in a torrent.
        
        Args:
            torrent_hash: Hash of the torrent
            file_ids: List of file IDs (indices) to set priority for
            priority: Priority level (0=Do not download, 1=Normal, 6=High, 7=Maximum)
            
        Returns:
            True if priority set successfully, False otherwise
        """
        if not self._authenticated:
            if not self.connect():
                return False
        
        try:
            # Convert file_ids to strings as qBittorrent API expects
            file_ids_str = [str(fid) for fid in file_ids]
            self.client.torrents_file_priority(
                torrent_hash=torrent_hash,
                file_ids=file_ids_str,
                priority=priority
            )
            logger.info(f"Successfully set file priority for torrent: {torrent_hash[:8]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to set file priority: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from qBittorrent API."""
        try:
            if self._authenticated:
                self.client.auth_log_out()
                self._authenticated = False
        except Exception as e:
            logger.warning(f"Error during disconnect: {e}")
