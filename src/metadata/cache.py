"""Simple in-memory cache for TMDB metadata to reduce API calls."""
import logging
from typing import Optional, Dict, Any
from hashlib import md5

logger = logging.getLogger(__name__)


class MetadataCache:
    """In-memory cache for movie/TV show metadata."""
    
    def __init__(self):
        """Initialize the cache."""
        self._cache: Dict[str, Dict[str, Any]] = {}
    
    def _make_key(self, title: str, year: Optional[int] = None, season: Optional[int] = None, episode: Optional[int] = None) -> str:
        """
        Create a cache key from title and optional year/season/episode.
        
        Args:
            title: Media title
            year: Optional year
            season: Optional season number
            episode: Optional episode number
            
        Returns:
            Cache key string
        """
        key_string = f"{title.lower().strip()}"
        if year:
            key_string += f"_{year}"
        if season is not None:
            key_string += f"_s{season}"
        if episode is not None:
            key_string += f"_e{episode}"
        return md5(key_string.encode('utf-8')).hexdigest()
    
    def get(self, title: str, year: Optional[int] = None, season: Optional[int] = None, episode: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Get metadata from cache.
        
        Args:
            title: Media title
            year: Optional year
            season: Optional season number
            episode: Optional episode number
            
        Returns:
            Cached metadata dict or None if not found
        """
        key = self._make_key(title, year, season, episode)
        return self._cache.get(key)
    
    def set(self, title: str, metadata: Dict[str, Any], year: Optional[int] = None, season: Optional[int] = None, episode: Optional[int] = None) -> None:
        """
        Store metadata in cache.
        
        Args:
            title: Media title
            metadata: Metadata dict to cache
            year: Optional year
            season: Optional season number
            episode: Optional episode number
        """
        key = self._make_key(title, year, season, episode)
        self._cache[key] = metadata
        cache_info = f"{title}"
        if year:
            cache_info += f" (year: {year})"
        if season is not None:
            cache_info += f" (season: {season})"
        if episode is not None:
            cache_info += f" (episode: {episode})"
        logger.debug(f"Cached metadata for: {cache_info}")
    
    def clear(self) -> None:
        """Clear all cached metadata."""
        self._cache.clear()
        logger.info("Metadata cache cleared")
    
    def size(self) -> int:
        """Get the number of cached items."""
        return len(self._cache)

