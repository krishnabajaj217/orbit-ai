import httpx

from ..config import get_settings


class WebSearchError(RuntimeError):
    pass


async def search(query: str) -> list[dict[str, str]]:
    api_key = get_settings().tavily_api_key
    if not api_key:
        raise WebSearchError("Web search isn't configured yet. Add TAVILY_API_KEY to backend/.env.")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={"api_key": api_key, "query": query, "search_depth": "basic", "max_results": 5},
            )
            response.raise_for_status()
    except httpx.TimeoutException as error:
        raise WebSearchError("Web search timed out. Please try again.") from error
    except httpx.HTTPError as error:
        raise WebSearchError("Web search is temporarily unavailable. Please try again.") from error

    try:
        payload = response.json()
        results = [
            {"title": item["title"], "url": item["url"], "snippet": item.get("content", "")}
            for item in payload.get("results", [])
            if item.get("title") and item.get("url")
        ]
    except (ValueError, TypeError, KeyError) as error:
        raise WebSearchError("Web search returned an invalid response.") from error
    if not results:
        raise WebSearchError("Web search returned no results for that query.")
    return results
