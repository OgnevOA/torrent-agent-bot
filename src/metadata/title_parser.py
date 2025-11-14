"""Parse torrent titles to extract clean movie/TV show names."""
import re
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def parse_torrent_title(torrent_name: str) -> Dict[str, Any]:
    """
    Parse a torrent name to extract media title, year, and type.
    
    Handles common torrent naming patterns:
    - Movies: "Movie.Name.1999.1080p.BluRay" -> "Movie Name (1999)"
    - TV Shows: "Show.Name.S01E01.1080p" -> "Show Name"
    
    Args:
        torrent_name: Original torrent name
        
    Returns:
        Dict with keys: title, year, media_type, season, episode
    """
    if not torrent_name:
        return {'title': '', 'year': None, 'media_type': 'unknown', 'season': None, 'episode': None}
    
    # Clean up common separators
    name = torrent_name.replace('_', ' ').replace('.', ' ')
    
    # Try to detect TV show pattern first
    # Pattern 1: S##E## or S## E## (season and episode)
    tv_pattern_episode = r'\b[Ss](\d{1,2})[Ee](\d{1,2})\b'
    tv_match = re.search(tv_pattern_episode, name)
    
    if tv_match:
        # It's a TV show with episode
        season = int(tv_match.group(1))
        episode = int(tv_match.group(2))
        
        # Extract title (everything before S##E##)
        title_part = name[:tv_match.start()].strip()
        title = _clean_title(title_part)
        
        return {
            'title': title,
            'year': None,
            'media_type': 'tv',
            'season': season,
            'episode': episode
        }
    
    # Pattern 2: S## or Season ## (season only, no episode)
    # Look for patterns like "S05", "S5" - but NOT followed by E## (episode)
    # Match S## that is NOT part of S##E## pattern
    tv_pattern_season = r'\b[Ss](\d{1,2})\b(?!\s*[Ee]\d)'
    tv_match_season = re.search(tv_pattern_season, name)
    
    if tv_match_season:
        # It's a TV show (season only, no episode)
        season_num = int(tv_match_season.group(1))
        
        # Only accept reasonable season numbers (1-99)
        if 1 <= season_num <= 99:
            # Extract title (everything before S##)
            title_part = name[:tv_match_season.start()].strip()
            title = _clean_title(title_part)
            
            # Only treat as TV show if we have a reasonable title (not just numbers/quality)
            # Title should have at least 2 characters and not be just numbers
            if title and len(title) > 2 and not title.replace(' ', '').isdigit():
                return {
                    'title': title,
                    'year': None,
                    'media_type': 'tv',
                    'season': season_num,
                    'episode': None
                }
    
    # Try to extract year (4 digits, likely between 1900-2100)
    year_pattern = r'\b(19\d{2}|20[0-2]\d)\b'
    year_match = re.search(year_pattern, name)
    year = None
    if year_match:
        year = int(year_match.group(1))
        # Extract title (everything before the year)
        title_part = name[:year_match.start()].strip()
    else:
        # No year found, use the whole name
        title_part = name
    
    # Clean up the title
    title = _clean_title(title_part)
    
    return {
        'title': title,
        'year': year,
        'media_type': 'movie',
        'season': None,
        'episode': None
    }


def _clean_title(title: str) -> str:
    """
    Clean up a title by removing common torrent artifacts.
    
    Args:
        title: Raw title string
        
    Returns:
        Cleaned title
    """
    if not title:
        return ''
    
    # Remove common quality indicators
    quality_patterns = [
        r'\b(1080p|720p|480p|2160p|4K|UHD|HD|SD)\b',
        r'\b(BluRay|BDRip|DVDRip|WEBRip|WEB-DL|HDRip|CAM|TS|TC|R5|SCR)\b',
        r'\b(x264|x265|HEVC|AVC|H\.264|H\.265)\b',
        r'\b(AC3|DTS|AAC|MP3|FLAC)\b',
        r'\b(5\.1|7\.1|2\.0|Stereo|Mono)\b',
        r'\b(REPACK|PROPER|READNFO|NFO)\b',
        r'\b\[.*?\]',  # Remove anything in brackets
        r'\(.*?\)',  # Remove anything in parentheses (but keep year if it's there)
    ]
    
    cleaned = title
    for pattern in quality_patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    # Remove multiple spaces and trim
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    # Remove leading/trailing separators
    cleaned = re.sub(r'^[-.\s]+|[-.\s]+$', '', cleaned)
    
    return cleaned if cleaned else title.strip()

