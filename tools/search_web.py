from typing import TypedDict
import requests
from config import BRAVE_SEARCH_API_KEY
from langchain_core.tools import tool
import threading
import queue
import time


class SearchWebResult(TypedDict):

    title: str
    description: str
    url: str


# Global queue and worker for throttling
class SearchRequest(TypedDict):
    query: str
    page: int
    result_queue: queue.Queue


request_queue: queue.Queue = queue.Queue()


def brave_worker():
    while True:
        req: SearchRequest = request_queue.get()
        try:
            offset = req["page"] - 1
            response = requests.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "x-subscription-token": BRAVE_SEARCH_API_KEY,
                },
                params={
                    "q": req["query"],
                    "count": 10,
                    "offset": offset,
                },
            ).json()
            req["result_queue"].put(response)
        except Exception as e:
            req["result_queue"].put({"error": str(e)})
        time.sleep(1)  # Throttle to 1 request per second


# Start the worker thread
worker_thread = threading.Thread(target=brave_worker, daemon=True)
worker_thread.start()


@tool(parse_docstring=True)
def search_web(query: str, page: int = 1) -> str:
    """Search the web for information.

    Args:
        query: The query to search the web for.
        page: The page number to return. 1-based. Default is 1.

    Returns:
        A summary of the search results.
    """
    result_queue: queue.Queue = queue.Queue()
    req: SearchRequest = {"query": query, "page": page, "result_queue": result_queue}
    request_queue.put(req)
    response = result_queue.get()
    if isinstance(response, dict) and "error" in response:
        return f"Error: {response['error']}"
    # Format results as markdown
    markdown_summary = f'Search Results (page {page}) for: "{query}"\n\n'
    for i, result in enumerate(response["web"]["results"], 1):
        markdown_summary += f"- [{result['title']}]({result['url']})..\n"
        markdown_summary += f"{result['description']}\n\n\n"
    return markdown_summary.strip()
