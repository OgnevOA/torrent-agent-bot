"""LangChain agent for natural language query interpretation."""
import json
import logging
from typing import Dict, Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

from src.config.settings import settings
from src.scrapers.models import SearchQuery

logger = logging.getLogger(__name__)


class TorrentSearchAgent:
    """LangChain agent that interprets natural language queries for torrent search."""
    
    def __init__(self):
        """Initialize the agent with Google Gemini 2.5 Flash."""
        # Using gemini-2.0-flash-exp (experimental, free)
        # Alternatives: "gemini-1.5-flash" (stable free) or "gemini-1.5-pro"
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",  # Experimental free model
            google_api_key=settings.google_api_key,
            temperature=0.3,  # Lower temperature for more consistent extraction
            convert_system_message_to_human=True
        )
        self._setup_prompt()
    
    def _setup_prompt(self):
        """Set up the prompt template for query interpretation."""
        from src.agent.prompts import SEARCH_QUERY_PROMPT
        
        self.prompt_template = ChatPromptTemplate.from_template(SEARCH_QUERY_PROMPT)
    
    def parse_query(self, user_query: str) -> SearchQuery:
        """
        Parse natural language query into structured search parameters.
        
        Args:
            user_query: Natural language search query from user
            
        Returns:
            SearchQuery object with extracted parameters
        """
        try:
            # Build the prompt
            prompt = self.prompt_template.format_messages(user_query=user_query)
            
            # Get response from LLM
            response = self.llm.invoke(prompt)
            
            # Parse JSON response
            content = response.content.strip()
            
            # Remove markdown code blocks if present
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1]) if len(lines) > 2 else content
            
            # Try to extract JSON
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                # Try to find JSON in the response
                import re
                json_match = re.search(r'\{[^}]*\}', content, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                else:
                    # Fallback: use the query as-is
                    logger.warning(f"Could not parse JSON from LLM response: {content}")
                    parsed = {"query": user_query, "max_results": 10}
            
            # Create SearchQuery object
            search_query = SearchQuery(
                query=parsed.get("query", user_query),
                min_seeders=parsed.get("min_seeders"),
                category=parsed.get("category"),
                max_results=parsed.get("max_results", 10)
            )
            
            logger.info(f"Parsed query: {user_query} -> {search_query}")
            return search_query
            
        except Exception as e:
            logger.error(f"Error parsing query with agent: {e}")
            # Fallback: return basic search query
            return SearchQuery(query=user_query, max_results=10)
    
    def format_results(self, results: list, query: str) -> str:
        """
        Format search results into a human-readable message.
        
        Args:
            results: List of TorrentResult objects
            query: Original search query
            
        Returns:
            Formatted message string
        """
        if not results:
            return f"❌ No torrents found for: {query}"
        
        message = f"🔍 Found {len(results)} torrent(s) for: *{query}*\n\n"
        
        for i, result in enumerate(results, 1):
            message += f"*{i}. {result.title}*\n"
            if result.size:
                message += f"   💾 Size: {result.size}\n"
            if result.seeders is not None:
                message += f"   ⬆️ Seeders: {result.seeders}\n"
            if result.leechers is not None:
                message += f"   ⬇️ Leechers: {result.leechers}\n"
            message += "\n"
        
        return message
