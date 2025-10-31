"""Torrent result data models."""
from pydantic import BaseModel, Field
from typing import Optional


class TorrentResult(BaseModel):
    """Represents a single torrent search result."""
    title: str = Field(..., description="Torrent title/name")
    size: Optional[str] = Field(None, description="File size (e.g., '2.5 GB')")
    seeders: Optional[int] = Field(None, description="Number of seeders")
    leechers: Optional[int] = Field(None, description="Number of leechers")
    url: Optional[str] = Field(None, description="URL to torrent page")
    magnet: Optional[str] = Field(None, description="Magnet link")
    download_url: Optional[str] = Field(None, description="Direct download URL for .torrent file")
    category: Optional[str] = Field(None, description="Torrent category")
    
    def __str__(self) -> str:
        """Human-readable string representation."""
        parts = [self.title]
        if self.size:
            parts.append(f"Size: {self.size}")
        if self.seeders is not None:
            parts.append(f"Seeders: {self.seeders}")
        if self.leechers is not None:
            parts.append(f"Leechers: {self.leechers}")
        return " | ".join(parts)


class SearchQuery(BaseModel):
    """Parsed search query from natural language."""
    query: str = Field(..., description="Main search terms")
    min_seeders: Optional[int] = Field(None, description="Minimum seeders")
    category: Optional[str] = Field(None, description="Category filter")
    max_results: int = Field(10, description="Maximum number of results to return")
