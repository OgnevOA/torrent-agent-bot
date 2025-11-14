"""Metadata module for enriching torrents with movie/TV show information from TMDB."""

from src.metadata.title_parser import parse_torrent_title
from src.metadata.tmdb_client import TMDBClient
from src.metadata.cache import MetadataCache

__all__ = ['parse_torrent_title', 'TMDBClient', 'MetadataCache']

