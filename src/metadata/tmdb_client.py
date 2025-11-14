"""TMDB API client for fetching movie and TV show metadata."""
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

try:
    from tmdbv3api import TMDb, Movie, TV
    TMDB_AVAILABLE = True
except ImportError:
    TMDB_AVAILABLE = False
    logger.warning("tmdbv3api not installed. TMDB metadata will be unavailable.")

from src.config.settings import settings


class TMDBClient:
    """Client for fetching metadata from The Movie Database (TMDB)."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize TMDB client.
        
        Args:
            api_key: TMDB API key (v3). If None, uses settings.tmdb_api_key
        """
        if not TMDB_AVAILABLE:
            raise ImportError("tmdbv3api library is not installed. Install it with: pip install tmdbv3api")
        
        self.api_key = api_key or getattr(settings, 'tmdb_api_key', None)
        if not self.api_key:
            logger.warning("TMDB API key not configured. Metadata lookup will be disabled.")
            self.enabled = False
            return
        
        self.enabled = True
        self.tmdb = TMDb()
        self.tmdb.api_key = self.api_key
        self.tmdb.language = 'en'  # Default to English
        
        self.movie = Movie()
        self.tv = TV()
        
        logger.info("TMDB client initialized")
    
    def search_movie(self, title: str, year: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Search for a movie by title.
        
        Args:
            title: Movie title
            year: Optional year to narrow search
            
        Returns:
            Movie metadata dict or None if not found
        """
        if not self.enabled:
            return None
        
        try:
            results = self.movie.search(title)
            if not results:
                return None
            
            # If year is provided, try to find exact match
            if year:
                for result in results:
                    release_date = result.get('release_date', '')
                    if release_date:
                        result_year = int(release_date.split('-')[0])
                        if result_year == year:
                            return self._format_movie_metadata(result)
            
            # Return first result
            return self._format_movie_metadata(results[0])
            
        except Exception as e:
            logger.error(f"Error searching for movie '{title}': {e}")
            return None
    
    def search_tv_show(self, title: str) -> Optional[Dict[str, Any]]:
        """
        Search for a TV show by title.
        
        Args:
            title: TV show title
            
        Returns:
            TV show metadata dict or None if not found
        """
        if not self.enabled:
            return None
        
        try:
            results = self.tv.search(title)
            if not results:
                return None
            
            # Return first result
            return self._format_tv_metadata(results[0])
            
        except Exception as e:
            logger.error(f"Error searching for TV show '{title}': {e}")
            return None
    
    def get_metadata(self, title: str, year: Optional[int] = None, media_type: str = 'movie') -> Optional[Dict[str, Any]]:
        """
        Get metadata for a movie or TV show.
        
        Args:
            title: Media title
            year: Optional year (for movies)
            media_type: 'movie' or 'tv'
            
        Returns:
            Metadata dict with: poster_url, title, description, rating, genres, year, media_type
        """
        if not self.enabled:
            return None
        
        if media_type == 'tv':
            return self.search_tv_show(title)
        else:
            return self.search_movie(title, year)
    
    def _format_movie_metadata(self, movie_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format movie data from TMDB into our standard format.
        
        Args:
            movie_data: Raw movie data from TMDB
            
        Returns:
            Formatted metadata dict
        """
        # Get full details for poster URL
        movie_id = movie_data.get('id')
        if movie_id:
            try:
                details = self.movie.details(movie_id)
                poster_path = details.get('poster_path', '')
            except Exception:
                poster_path = movie_data.get('poster_path', '')
        else:
            poster_path = movie_data.get('poster_path', '')
        
        # Build poster URL
        poster_url = None
        if poster_path:
            poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}"
        
        # Extract year from release_date
        release_date = movie_data.get('release_date', '')
        year = None
        if release_date:
            try:
                year = int(release_date.split('-')[0])
            except (ValueError, IndexError):
                pass
        
        # Get genres
        genres = []
        if 'genre_ids' in movie_data:
            # We have genre IDs, but not names - would need genre list
            # For now, just use empty list
            pass
        elif 'genres' in movie_data:
            genres = [g.get('name', '') for g in movie_data.get('genres', []) if g.get('name')]
        
        return {
            'poster_url': poster_url,
            'title': movie_data.get('title', ''),
            'description': movie_data.get('overview', ''),
            'rating': movie_data.get('vote_average', 0.0),
            'genres': genres,
            'year': year,
            'media_type': 'movie',
            'tmdb_id': movie_id
        }
    
    def _format_tv_metadata(self, tv_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format TV show data from TMDB into our standard format.
        
        Args:
            tv_data: Raw TV show data from TMDB
            
        Returns:
            Formatted metadata dict
        """
        # Get full details for poster URL
        tv_id = tv_data.get('id')
        if tv_id:
            try:
                details = self.tv.details(tv_id)
                poster_path = details.get('poster_path', '')
            except Exception:
                poster_path = tv_data.get('poster_path', '')
        else:
            poster_path = tv_data.get('poster_path', '')
        
        # Build poster URL
        poster_url = None
        if poster_path:
            poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}"
        
        # Extract year from first_air_date
        first_air_date = tv_data.get('first_air_date', '')
        year = None
        if first_air_date:
            try:
                year = int(first_air_date.split('-')[0])
            except (ValueError, IndexError):
                pass
        
        # Get genres
        genres = []
        if 'genre_ids' in tv_data:
            # We have genre IDs, but not names - would need genre list
            pass
        elif 'genres' in tv_data:
            genres = [g.get('name', '') for g in tv_data.get('genres', []) if g.get('name')]
        
        return {
            'poster_url': poster_url,
            'title': tv_data.get('name', ''),
            'description': tv_data.get('overview', ''),
            'rating': tv_data.get('vote_average', 0.0),
            'genres': genres,
            'year': year,
            'media_type': 'tv',
            'tmdb_id': tv_id
        }

