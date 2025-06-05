from arxiv import Client, SortCriterion, Search, Result
from langchain_core.tools import tool


def format_arxiv_results(results: list[Result]) -> str:
    formatted = []
    for r in results:
        authors = ", ".join([a.name for a in r.authors])
        entry = (
            f"## {r.title}\n\n"
            f"**By {authors}**, published on {r.published.strftime('%B %d, %Y')} \n"
            f"\n_Abstract_  \n{r.summary}\n --- \n"
            f"{f'**PDF:** {r.pdf_url}  \n' if r.pdf_url else ''}"
        )
        formatted.append(entry)
    return "\n".join(formatted)


client = Client()


@tool(parse_docstring=True)
def search_arxiv(query: str) -> str:
    """Search the arXiv for the most recent papers matching the query as a tool for the agent system.

    Args:
        query: The search query to use. Use a less specific or shorter search term to maximize the result set. Do not include special characters.

    Returns:
        A formatted string containing the most recent arXiv papers matching the query, including title, authors, publication date, abstract, and PDF link if available.
    """

    search = Search(
        query=query,
        max_results=10,
        sort_by=SortCriterion.Relevance,
    )
    results = client.results(search)
    return format_arxiv_results(results)


if __name__ == "__main__":
    search = Search(
        query="The Population of the Galactic Center Filaments",
        max_results=10,
        sort_by=SortCriterion.Relevance,
    )
    results = client.results(search)
    print(format_arxiv_results(results))
