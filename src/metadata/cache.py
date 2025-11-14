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
    
    def _make_key(self, title: str, year: Optional[int] = None) -> str:
        """
        Create a cache key from title and optional year.
        
        Args:
            title: Media title
            year: Optional year
            
        Returns:
            Cache key string
        """
        key_string = f"{title.lower().strip()}"
        if year:
            key_string += f"_{year}"
        return md5(key_string.encode('utf-8')).hexdigest()
    
    def get(self, title: str, year: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Get metadata from cache.
        
        Args:
            title: Media title
            year: Optional year
            
        Returns:
            Cached metadata dict or None if not found
        """
        key = self._make_key(title, year)
        return self._cache.get(key)
    
    def set(self, title: str, metadata: Dict[str, Any], year: Optional[int] = None) -> None:
        """
        Store metadata in cache.
        
        Args:
            title: Media title
            metadata: Metadata dict to cache
            year: Optional year
        """
        key = self._make_key(title, year)
        self._cache[key] = metadata
        logger.debug(f"Cached metadata for: {title} (year: {year})")
    
    def clear(self) -> None:
        """Clear all cached metadata."""
        self._cache.clear()
        logger.info("Metadata cache cleared")
    
    def size(self) -> int:
        """Get the number of cached items."""
        return len(self._cache)

