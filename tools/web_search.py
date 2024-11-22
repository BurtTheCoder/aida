# tools/web_search.py
import httpx
from utils import logging
from typing import Optional, Dict, Any
from config.settings import settings
import asyncio

class WebSearchService:
    """Web search service using Perplexity API"""
    def __init__(self):
        self.api_key = settings.PERPLEXITY_API_KEY
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.base_url = "https://api.perplexity.ai/chat/completions"

    async def search(self, query: str) -> str:
        """Execute web search query"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    json={
                        "model": "llama-3.1-sonar-small-128k-online",
                        "messages": [{
                            "role": "user",
                            "content": query
                        }],
                    },
                    timeout=30.0
                )

                if response.status_code != 200:
                    raise Exception(f"Search failed with status code: {response.status_code}")

                result = response.json()
                response_text = result['choices'][0]['message']['content']

                # Truncate long responses
                if len(response_text) > 1000:
                    response_text = response_text[:1000] + "..."

                return response_text

        except Exception as e:
            error_msg = f"Web search error: {str(e)}"
            logging.error(error_msg)
            return error_msg

    async def format_search_result(self, query: str, result: str) -> Dict[str, Any]:
        """Format search results for assistant consumption"""
        return {
            "query": query,
            "result": result,
            "status": "success" if not result.startswith("Web search error:") else "error"
        }

    async def enhanced_search(self, query: str) -> Dict[str, Any]:
        """Enhanced search with additional context and formatting"""
        raw_result = await self.search(query)
        return await self.format_search_result(query, raw_result)

# Optional: Advanced features for the WebSearchService

    async def batch_search(self, queries: list[str]) -> list[str]:
        """Execute multiple searches in parallel"""
        async with httpx.AsyncClient() as client:
            tasks = [
                self.search(query)
                for query in queries
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle any errors in the results
            processed_results = []
            for result in results:
                if isinstance(result, Exception):
                    processed_results.append(f"Search error: {str(result)}")
                else:
                    processed_results.append(result)

            return processed_results

    async def search_with_retry(self, query: str, max_retries: int = 3) -> str:
        """Execute search with automatic retry on failure"""
        for attempt in range(max_retries):
            try:
                result = await self.search(query)
                if not result.startswith("Web search error:"):
                    return result

                if attempt < max_retries - 1:
                    await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff

            except Exception as e:
                if attempt == max_retries - 1:
                    return f"Web search error after {max_retries} attempts: {str(e)}"
                logging.warning(f"Search attempt {attempt + 1} failed: {str(e)}")

        return f"Web search failed after {max_retries} attempts"
