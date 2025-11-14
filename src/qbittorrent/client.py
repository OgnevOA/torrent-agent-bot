"""qBittorrent API client."""
import logging
import re
import time
from typing import Optional, List

import requests
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
        Add a torrent to qBittorrent and configure it for sequential download
        with first/last piece priority.
        
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
            # Get existing torrent hashes before adding
            existing_hashes = set()
            try:
                existing_torrents = self.client.torrents_info()
                existing_hashes = {t.hash for t in existing_torrents}
            except Exception as e:
                logger.warning(f"Could not get existing torrents to find new hash: {e}")
            
            # Add torrent via API
            self.client.torrents_add(
                urls=torrent_link,
                category=category,
                is_paused=False
            )
            logger.info(f"Successfully added torrent: {torrent_link[:50]}...")
            
            # Get the hash of the newly added torrent
            torrent_hash = None
            try:
                # Wait a moment for qBittorrent to process the new torrent
                time.sleep(0.5)  # Small delay to ensure torrent is processed
                
                # Get all torrents and find the new one
                all_torrents = self.client.torrents_info()
                for torrent in all_torrents:
                    if torrent.hash not in existing_hashes:
                        torrent_hash = torrent.hash
                        break
                
                # If we couldn't find it by hash comparison, try extracting from magnet link
                if not torrent_hash and torrent_link.startswith("magnet:"):
                    # Extract hash from magnet link: magnet:?xt=urn:btih:HASH&...
                    match = re.search(r'btih:([a-fA-F0-9]{40})', torrent_link)
                    if match:
                        torrent_hash = match.group(1).lower()
                
            except Exception as e:
                logger.warning(f"Could not determine torrent hash after adding: {e}")
            
            # Apply sequential download and first/last piece priority settings
            if torrent_hash:
                try:
                    self.set_torrent_options(
                        torrent_hash=torrent_hash,
                        sequential_download=True,
                        first_last_piece_priority=True
                    )
                except Exception as e:
                    # Log warning but don't fail the torrent addition
                    logger.warning(f"Failed to set sequential download options for torrent {torrent_hash[:8]}...: {e}")
            else:
                logger.warning("Could not determine torrent hash, skipping sequential download configuration")
            
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
    
    def set_torrent_options(self, torrent_hash: str, sequential_download: bool = True, first_last_piece_priority: bool = True) -> bool:
        """
        Set torrent options for sequential download and first/last piece priority.
        
        Args:
            torrent_hash: Hash of the torrent to configure
            sequential_download: If True, enable sequential download
            first_last_piece_priority: If True, prioritize downloading first and last pieces first
            
        Returns:
            True if options set successfully, False otherwise
        """
        if not self._authenticated:
            if not self.connect():
                return False
        
        try:
            # Try using the qbittorrentapi method if available
            # The method name might vary by library version
            if hasattr(self.client, 'torrents_set_options'):
                self.client.torrents_set_options(
                    torrent_hashes=torrent_hash,
                    sequentialDownload=sequential_download,
                    firstLastPiecePrio=first_last_piece_priority
                )
            elif hasattr(self.client, 'torrents_set_torrent_options'):
                self.client.torrents_set_torrent_options(
                    torrent_hashes=torrent_hash,
                    sequentialDownload=sequential_download,
                    firstLastPiecePrio=first_last_piece_priority
                )
            else:
                # Fallback: use requests library directly
                # qBittorrent API endpoint: POST /api/v2/torrents/setOptions
                base_url = settings.qbittorrent_url.rstrip('/')
                api_url = f"{base_url}/api/v2/torrents/setOptions"
                
                # Create a session and login
                session = requests.Session()
                login_url = f"{base_url}/api/v2/auth/login"
                login_data = {
                    'username': settings.qbittorrent_username,
                    'password': settings.qbittorrent_password
                }
                session.post(login_url, data=login_data)
                
                # Set torrent options
                data = {
                    'hashes': torrent_hash,
                    'sequentialDownload': str(sequential_download).lower(),
                    'firstLastPiecePrio': str(first_last_piece_priority).lower()
                }
                response = session.post(api_url, data=data)
                response.raise_for_status()
            
            logger.info(f"Successfully set torrent options (sequential={sequential_download}, firstLastPrio={first_last_piece_priority}) for torrent: {torrent_hash[:8]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to set torrent options: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from qBittorrent API."""
        try:
            if self._authenticated:
                self.client.auth_log_out()
                self._authenticated = False
        except Exception as e:
            logger.warning(f"Error during disconnect: {e}")
