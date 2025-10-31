"""Rutracker.org scraper with custom implementation."""
import time
import logging
from typing import List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from src.config.settings import settings
from src.scrapers.models import TorrentResult

logger = logging.getLogger(__name__)


class RutrackerScraper:
    """Scraper for rutracker.org torrent site."""
    
    BASE_URL = "https://rutracker.org"
    LOGIN_URL = "https://rutracker.org/forum/login.php"
    SEARCH_URL = "https://rutracker.org/forum/tracker.php"
    
    def __init__(self):
        """Initialize scraper with session."""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        })
        self._authenticated = False
    
    def login(self) -> bool:
        """
        Authenticate with rutracker.org.
        
        Returns:
            True if login successful, False otherwise
        """
        if self._authenticated:
            return True
        
        try:
            # Get login page first to get any CSRF tokens if needed
            logger.debug("Fetching login page...")
            login_page = self.session.get(self.LOGIN_URL, timeout=10)
            login_page.raise_for_status()
            
            # Parse login form
            soup = BeautifulSoup(login_page.text, "html.parser")
            
            # Find login form - rutracker uses different form names
            login_form = soup.find("form", {"name": "login"}) or soup.find("form", action=lambda x: x and "login.php" in x)
            
            if not login_form:
                logger.warning("Could not find login form, trying default login data")
            
            # Prepare login data
            login_data = {
                "login_username": settings.rutracker_username,
                "login_password": settings.rutracker_password,
                "login": "Вход"  # "Login" in Russian
            }
            
            # Submit login form
            logger.debug("Submitting login credentials...")
            response = self.session.post(
                self.LOGIN_URL,
                data=login_data,
                allow_redirects=True,
                timeout=10
            )
            response.raise_for_status()
            
            # Check if login was successful
            # Successful login usually redirects away from login.php
            # and response will contain user info or logout link
            if "login.php" not in response.url.lower() or "logout.php" in response.text or "bb_session" in response.text:
                self._authenticated = True
                logger.info("Successfully logged in to rutracker.org")
                return True
            else:
                # Check for error messages
                soup = response.content and BeautifulSoup(response.text, "html.parser")
                error_msg = soup.find("div", class_="error") or soup.find("div", class_="alert")
                if error_msg:
                    logger.error(f"Login error: {error_msg.get_text(strip=True)}")
                else:
                    logger.error("Login failed - check credentials")
                return False
                
        except requests.RequestException as e:
            logger.error(f"Login request failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during login: {e}", exc_info=True)
            return False
    
    def search(self, query: str, max_results: int = 10) -> List[TorrentResult]:
        """
        Search for torrents on rutracker.org.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            
        Returns:
            List of TorrentResult objects
        """
        if not self._authenticated:
            if not self.login():
                logger.error("Cannot search - authentication failed")
                return []
        
        try:
            # Prepare search parameters
            search_params = {
                "nm": query,  # Search query parameter
            }
            
            search_data = {
                "o": "10",  # Sort by seeds (descending)
                "s": "2"    # Sort order: 2 = desc
            }
            
            # Perform search
            response = self.session.post(
                self.SEARCH_URL,
                params=search_params,
                data=search_data,
                timeout=15
            )
            response.raise_for_status()
            
            # Parse results
            soup = BeautifulSoup(response.text, "html.parser")
            results = self._parse_search_results(soup, max_results)
            
            logger.info(f"Found {len(results)} torrents for query: {query}")
            return results
            
        except requests.RequestException as e:
            logger.error(f"Search request failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error during search: {e}", exc_info=True)
            return []
    
    def _parse_search_results(self, soup: BeautifulSoup, max_results: int) -> List[TorrentResult]:
        """
        Parse HTML search results into TorrentResult objects.
        
        Args:
            soup: BeautifulSoup object of search results page
            max_results: Maximum number of results to return
            
        Returns:
            List of TorrentResult objects
        """
        results = []
        
        try:
            # Find the results table - rutracker uses specific table classes
            results_table = soup.find("table", {"class": "forumline"}) or \
                          soup.find("table", {"id": "tor-tbl"}) or \
                          soup.find("table", {"class": "vf-result"})
            
            if not results_table:
                logger.warning("Could not find results table")
                # Try to find any table with torrent links
                tables = soup.find_all("table")
                for table in tables:
                    if table.find("a", href=lambda x: x and "viewtopic.php?t=" in str(x)):
                        results_table = table
                        break
            
            if not results_table:
                logger.warning("No torrent results found on page")
                return results
            
            # Find all result rows
            rows = results_table.find_all("tr", class_=lambda x: x and ("tCenter" in x or "hl-tr" in x), limit=max_results * 2)
            
            for row in rows[:max_results]:
                try:
                    torrent = self._parse_torrent_row(row)
                    if torrent and torrent.title:  # Only add if we have a valid title
                        results.append(torrent)
                except Exception as e:
                    logger.debug(f"Failed to parse torrent row: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error parsing search results: {e}", exc_info=True)
        
        return results
    
    def _parse_torrent_row(self, row) -> Optional[TorrentResult]:
        """
        Parse a single torrent row from search results.
        
        Args:
            row: BeautifulSoup row element
            
        Returns:
            TorrentResult object or None if parsing fails
        """
        try:
            # Find title cell (usually contains link)
            title_link = row.find("a", href=lambda x: x and "viewtopic.php?t=" in str(x), class_="med") or \
                        row.find("a", href=lambda x: x and "viewtopic.php?t=" in str(x))
            
            if not title_link:
                return None
            
            title = title_link.get_text(strip=True)
            url = urljoin(self.BASE_URL, title_link.get("href", ""))
            
            # Extract topic ID from URL
            topic_id = None
            if "t=" in url:
                topic_id = url.split("t=")[1].split("&")[0]
            
            # Extract size, seeders, leechers from other cells
            cells = row.find_all("td")
            size = None
            seeders = None
            leechers = None
            
            for cell in cells:
                text = cell.get_text(strip=True)
                
                # Size is usually in a specific column or contains "GB", "MB", etc.
                if any(unit in text.upper() for unit in ["GB", "MB", "KB", "TB", "ГБ", "МБ", "КБ", "ТБ"]) and not size:
                    size = text
                
                # Seeders and leechers are usually numbers in specific columns
                if text.isdigit():
                    num = int(text)
                    if seeders is None:
                        seeders = num
                    elif leechers is None and num != seeders:
                        leechers = num
            
            # Get magnet link from torrent page
            magnet = None
            if topic_id:
                try:
                    magnet = self._get_magnet_link(topic_id)
                except Exception as e:
                    logger.debug(f"Could not get magnet link for topic {topic_id}: {e}")
            
            return TorrentResult(
                title=title,
                size=size,
                seeders=seeders,
                leechers=leechers,
                url=url,
                magnet=magnet,
                download_url=None
            )
            
        except Exception as e:
            logger.debug(f"Error parsing torrent row: {e}")
            return None
    
    def _get_magnet_link(self, topic_id: str) -> Optional[str]:
        """
        Get magnet link for a torrent topic.
        
        Args:
            topic_id: Topic ID of the torrent
            
        Returns:
            Magnet link or None if not found
        """
        try:
            topic_url = f"{self.BASE_URL}/forum/viewtopic.php?t={topic_id}"
            response = self.session.get(topic_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Find magnet link
            magnet_link = soup.find("a", href=lambda x: x and x.startswith("magnet:"))
            if magnet_link:
                return magnet_link.get("href")
            
            # Alternative: try to extract from script tags or data attributes
            scripts = soup.find_all("script")
            for script in scripts:
                if script.string and "magnet:" in script.string:
                    import re
                    match = re.search(r'magnet:\?[^\s"\']+', script.string)
                    if match:
                        return match.group(0)
            
            return None
            
        except Exception as e:
            logger.debug(f"Error getting magnet link: {e}")
            return None
    
    def get_torrent_download_url(self, torrent_url: str) -> Optional[str]:
        """
        Get download URL or magnet link for a torrent.
        
        Args:
            torrent_url: URL to torrent page
            
        Returns:
            Download URL or magnet link, or None if not found
        """
        try:
            response = self.session.get(torrent_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Look for magnet link first
            magnet_link = soup.find("a", href=lambda x: x and x.startswith("magnet:"))
            if magnet_link:
                return magnet_link.get("href")
            
            # Look for download link
            download_link = soup.find("a", href=lambda x: x and ".torrent" in str(x).lower() or "dl.php" in str(x))
            if download_link:
                return urljoin(self.BASE_URL, download_link.get("href", ""))
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting torrent download URL: {e}")
            return None
    
    def __del__(self):
        """Clean up session on deletion."""
        if hasattr(self, "session"):
            self.session.close()
