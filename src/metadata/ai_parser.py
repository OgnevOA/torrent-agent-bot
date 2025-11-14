"""AI-powered title parser using Gemini to extract clean movie/TV show names."""
import json
import logging
import re
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# In-memory cache for AI extraction results keyed by torrent hash
_ai_extraction_cache: Dict[str, Optional[Dict[str, Any]]] = {}

# Try to import Gemini, but make it optional
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.prompts import ChatPromptTemplate
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("langchain_google_genai not available. AI title parsing will be disabled.")

from src.config.settings import settings


TITLE_EXTRACTION_PROMPT = """You are a helpful assistant that extracts clean movie or TV show titles from messy torrent filenames.

Your task is to identify the actual movie or TV show name from a torrent filename, which often contains:
- Quality indicators (1080p, 720p, BluRay, WEB-DL, etc.)
- Release groups and encoding info (x264, x265, etc.)
- Season/episode numbers (S01E01, S05, etc.)
- Audio/video codec information
- Other metadata

Extract the clean title that would be used to search in a movie/TV database like TMDB.

Examples:
- "The.Matrix.1999.1080p.BluRay.x264" -> {{"title": "The Matrix", "year": 1999, "media_type": "movie"}}
- "Castle.S05.720p.WEB-DL.FoxLife" -> {{"title": "Castle", "season": 5, "media_type": "tv"}}
- "Game.of.Thrones.S01E01.1080p" -> {{"title": "Game of Thrones", "season": 1, "episode": 1, "media_type": "tv"}}
- "Indiana.Jones.and.the.Last.Crusade.BDRemux.mkv" -> {{"title": "Indiana Jones and the Last Crusade", "media_type": "movie"}}

Respond ONLY with valid JSON in this format:
{{
    "title": "Clean title for database search",
    "media_type": "movie" or "tv",
    "year": <year number or null>,
    "season": <season number or null>,
    "episode": <episode number or null>
}}

Torrent filename: {torrent_name}"""


def extract_title_with_ai(torrent_name: str, torrent_hash: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Use AI (Gemini) to extract clean movie/TV show title from a messy torrent filename.
    
    Args:
        torrent_name: Messy torrent filename
        torrent_hash: Optional torrent hash for caching (prevents duplicate AI calls)
        
    Returns:
        Dict with title, media_type, year, season, episode or None if failed
    """
    if not GEMINI_AVAILABLE:
        logger.debug("Gemini not available for AI title extraction")
        return None
    
    if not torrent_name or not torrent_name.strip():
        return None
    
    # Check cache first using torrent hash (preferred) or torrent name (fallback)
    cache_key = torrent_hash if torrent_hash else torrent_name
    if cache_key in _ai_extraction_cache:
        cached_result = _ai_extraction_cache[cache_key]
        logger.debug(f"Using cached AI extraction result for {'hash' if torrent_hash else 'name'}: {cache_key[:16] if torrent_hash else cache_key[:50]}...")
        return cached_result
    
    # Check if Google API key is configured
    if not settings.google_api_key:
        logger.debug("Google API key not configured, skipping AI title extraction")
        return None
    
    try:
        logger.info(f"🤖 AI Title Extraction Request: '{torrent_name}'")
        
        # Initialize Gemini
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=settings.google_api_key,
            temperature=0.1,  # Very low temperature for consistent extraction
            convert_system_message_to_human=True
        )
        
        # Create prompt
        prompt_template = ChatPromptTemplate.from_template(TITLE_EXTRACTION_PROMPT)
        prompt = prompt_template.format_messages(torrent_name=torrent_name)
        
        logger.debug(f"AI Prompt created for: {torrent_name}")
        
        # Get response from AI
        logger.debug("Sending request to Gemini AI...")
        response = llm.invoke(prompt)
        content = response.content.strip()
        
        logger.info(f"🤖 AI Response (raw): {content[:200]}{'...' if len(content) > 200 else ''}")
        
        # Remove markdown code blocks if present
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1]) if len(lines) > 2 else content
            logger.debug("Removed markdown code blocks from AI response")
        
        # Try to extract JSON
        parsed = None
        try:
            parsed = json.loads(content)
            logger.debug("Successfully parsed AI response as JSON")
        except json.JSONDecodeError:
            # Try to find JSON in the response
            logger.debug("Direct JSON parse failed, searching for JSON in response...")
            json_match = re.search(r'\{[^}]*\}', content, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group())
                    logger.debug("Found and parsed JSON from response")
                except json.JSONDecodeError as e:
                    logger.warning(f"Could not parse extracted JSON: {e}")
            else:
                logger.warning(f"Could not find JSON in AI response. Full response: {content}")
                return None
        
        if not parsed:
            logger.warning("Failed to parse AI response")
            return None
        
        # Validate and return
        title = parsed.get('title', '').strip()
        if not title:
            logger.warning(f"AI returned empty title. Parsed data: {parsed}")
            return None
        
        result = {
            'title': title,
            'media_type': parsed.get('media_type', 'movie'),
            'year': parsed.get('year'),
            'season': parsed.get('season'),
            'episode': parsed.get('episode')
        }
        
        logger.info(f"✅ AI Extraction Result: title='{result['title']}', type={result['media_type']}, year={result['year']}, season={result['season']}, episode={result['episode']}")
        
        # Cache the result (cache None results too to avoid repeated failed attempts)
        _ai_extraction_cache[cache_key] = result
        logger.debug(f"Cached AI extraction result for {'hash' if torrent_hash else 'name'}: {cache_key[:16] if torrent_hash else cache_key[:50]}...")
        
        return result
        
    except Exception as e:
        logger.debug(f"Error in AI title extraction: {e}", exc_info=True)
        # Cache None to avoid repeated failed attempts
        _ai_extraction_cache[cache_key] = None
        return None

