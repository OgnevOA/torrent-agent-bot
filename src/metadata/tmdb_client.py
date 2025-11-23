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
            search_response = self.movie.search(title)
            if not search_response:
                return None
            
            # TMDB search returns a dict/object with 'results' key containing the list
            # Extract the results list
            if isinstance(search_response, dict):
                results = search_response.get('results', [])
            elif hasattr(search_response, 'results'):
                results = getattr(search_response, 'results', [])
            elif isinstance(search_response, list):
                results = search_response
            else:
                # Try to convert and extract
                response_dict = self._to_dict(search_response)
                results = response_dict.get('results', [])
                if not results and isinstance(response_dict, list):
                    results = response_dict
            
            if not results:
                return None
            
            # Convert results to list if needed
            if not isinstance(results, list):
                results = list(results) if hasattr(results, '__iter__') else []
            
            if not results:
                return None
            
            # If year is provided, try to find exact match
            if year:
                for result in results:
                    result_dict = self._to_dict(result)
                    release_date = result_dict.get('release_date', '')
                    if release_date:
                        try:
                            result_year = int(str(release_date).split('-')[0])
                            if result_year == year:
                                return self._format_movie_metadata(result_dict)
                        except (ValueError, AttributeError):
                            continue
            
            # Return first result
            return self._format_movie_metadata(self._to_dict(results[0]))
            
        except Exception as e:
            logger.error(f"Error searching for movie '{title}': {e}", exc_info=True)
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
            search_response = self.tv.search(title)
            if not search_response:
                return None
            
            # TMDB search returns a dict/object with 'results' key containing the list
            # Extract the results list
            if isinstance(search_response, dict):
                results = search_response.get('results', [])
            elif hasattr(search_response, 'results'):
                results = getattr(search_response, 'results', [])
            elif isinstance(search_response, list):
                results = search_response
            else:
                # Try to convert and extract
                response_dict = self._to_dict(search_response)
                results = response_dict.get('results', [])
                if not results and isinstance(response_dict, list):
                    results = response_dict
            
            if not results:
                return None
            
            # Convert results to list if needed
            if not isinstance(results, list):
                results = list(results) if hasattr(results, '__iter__') else []
            
            if not results:
                return None
            
            # Return first result
            return self._format_tv_metadata(self._to_dict(results[0]))
            
        except Exception as e:
            logger.error(f"Error searching for TV show '{title}': {e}", exc_info=True)
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
    
    def get_season_metadata(self, tv_id: int, season_number: int, show_title: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a specific TV season.
        
        Args:
            tv_id: TMDB TV show ID
            season_number: Season number (1-indexed)
            show_title: Optional show title for context
            
        Returns:
            Season metadata dict or None if not found
        """
        if not self.enabled:
            return None
        
        try:
            season_data = self.tv.season(tv_id, season_number)
            if not season_data:
                return None
            
            season_dict = self._to_dict(season_data)
            
            # Extract season poster
            poster_path = season_dict.get('poster_path') or ''
            poster_url = None
            if poster_path:
                poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}"
            
            # If no season poster, try to get show poster as fallback
            if not poster_url and show_title:
                try:
                    show_metadata = self.search_tv_show(show_title)
                    if show_metadata:
                        poster_url = show_metadata.get('poster_url')
                except Exception:
                    pass
            
            return {
                'poster_url': poster_url,
                'title': show_title or season_dict.get('name', ''),
                'description': season_dict.get('overview', ''),
                'rating': season_dict.get('vote_average', 0.0),
                'genres': [],  # Seasons don't have genres, use show genres if needed
                'year': None,  # Could extract from air_date if needed
                'media_type': 'tv',
                'season': season_number,
                'episode': None,
                'tmdb_id': tv_id
            }
        except Exception as e:
            logger.debug(f"Error fetching season metadata for TV ID {tv_id}, season {season_number}: {e}", exc_info=True)
            return None
    
    def get_episode_metadata(self, tv_id: int, season_number: int, episode_number: int, show_title: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a specific TV episode.
        
        Args:
            tv_id: TMDB TV show ID
            season_number: Season number (1-indexed)
            episode_number: Episode number (1-indexed)
            show_title: Optional show title for context
            
        Returns:
            Episode metadata dict or None if not found
        """
        if not self.enabled:
            return None
        
        try:
            episode_data = self.tv.episode(tv_id, season_number, episode_number)
            if not episode_data:
                return None
            
            episode_dict = self._to_dict(episode_data)
            
            # Extract episode still
            still_path = episode_dict.get('still_path') or ''
            poster_url = None
            if still_path:
                poster_url = f"https://image.tmdb.org/t/p/w500{still_path}"
            
            # Fallback to season poster if episode still not available
            if not poster_url:
                try:
                    season_metadata = self.get_season_metadata(tv_id, season_number, show_title)
                    if season_metadata:
                        poster_url = season_metadata.get('poster_url')
                except Exception:
                    pass
            
            # Fallback to show poster if still no poster
            if not poster_url and show_title:
                try:
                    show_metadata = self.search_tv_show(show_title)
                    if show_metadata:
                        poster_url = show_metadata.get('poster_url')
                except Exception:
                    pass
            
            return {
                'poster_url': poster_url,
                'title': show_title or episode_dict.get('name', ''),
                'description': episode_dict.get('overview', ''),
                'rating': episode_dict.get('vote_average', 0.0),
                'genres': [],  # Episodes don't have genres
                'year': None,  # Could extract from air_date if needed
                'media_type': 'tv',
                'season': season_number,
                'episode': episode_number,
                'tmdb_id': tv_id
            }
        except Exception as e:
            logger.debug(f"Error fetching episode metadata for TV ID {tv_id}, S{season_number}E{episode_number}: {e}", exc_info=True)
            return None
    
    def _to_dict(self, obj: Any) -> Dict[str, Any]:
        """
        Convert a TMDB object to a dictionary.
        
        Args:
            obj: TMDB object (could be dict, object with attributes, or string)
            
        Returns:
            Dictionary representation
        """
        # Skip strings - they're likely keys from iterating over a dict
        if isinstance(obj, str):
            # Don't log warning for common dict keys like 'page', 'results', etc.
            # These are expected when iterating over response wrappers
            return {}
        
        if isinstance(obj, dict):
            # Already a dict, but ensure all keys are strings
            result = {}
            for k, v in obj.items():
                result[str(k)] = v
            return result
        elif hasattr(obj, '__dict__'):
            # Object with __dict__ attribute - convert to dict with string keys
            result = {}
            for k, v in obj.__dict__.items():
                # Skip private attributes and ensure keys are strings
                if not k.startswith('_'):
                    result[str(k)] = v
            return result
        elif hasattr(obj, '__getitem__') and not isinstance(obj, str):
            # Try to convert using dict() constructor (but not strings)
            try:
                result = {}
                for k in obj:
                    result[str(k)] = obj[k]
                return result
            except (TypeError, ValueError, KeyError):
                pass
        
        # Try accessing common attributes directly
        result = {}
        for attr in ['id', 'title', 'name', 'release_date', 'first_air_date', 'poster_path', 
                     'overview', 'vote_average', 'genres', 'genre_ids', 'results', 'page', 
                     'total_pages', 'total_results']:
            try:
                if hasattr(obj, attr):
                    value = getattr(obj, attr, None)
                    if value is not None:
                        result[attr] = value
            except Exception:
                continue
        
        return result if result else {}
    
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
        poster_path = movie_data.get('poster_path') or ''
        
        if movie_id and not poster_path:
            try:
                details = self.movie.details(movie_id)
                details_dict = self._to_dict(details)
                poster_path = details_dict.get('poster_path') or ''
                # Update movie_data with full details if we got them
                if details_dict.get('genres'):
                    movie_data['genres'] = details_dict.get('genres', [])
            except Exception as e:
                logger.debug(f"Could not get movie details for ID {movie_id}: {e}")
        
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
        if 'genres' in movie_data:
            genre_list = movie_data.get('genres', [])
            for g in genre_list:
                if isinstance(g, dict):
                    genre_name = g.get('name', '')
                elif hasattr(g, 'name'):
                    genre_name = getattr(g, 'name', '')
                else:
                    continue
                if genre_name:
                    genres.append(genre_name)
        
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
        poster_path = tv_data.get('poster_path') or ''
        
        if tv_id and not poster_path:
            try:
                details = self.tv.details(tv_id)
                details_dict = self._to_dict(details)
                poster_path = details_dict.get('poster_path') or ''
                # Update tv_data with full details if we got them
                if details_dict.get('genres'):
                    tv_data['genres'] = details_dict.get('genres', [])
            except Exception as e:
                logger.debug(f"Could not get TV details for ID {tv_id}: {e}")
        
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
        if 'genres' in tv_data:
            genre_list = tv_data.get('genres', [])
            for g in genre_list:
                if isinstance(g, dict):
                    genre_name = g.get('name', '')
                elif hasattr(g, 'name'):
                    genre_name = getattr(g, 'name', '')
                else:
                    continue
                if genre_name:
                    genres.append(genre_name)
        
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

