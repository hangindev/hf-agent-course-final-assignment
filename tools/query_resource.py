import tempfile
import os
import requests
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from web_scraper.fetch_html import fetch_html_with_patchright, TimeoutError
from web_scraper.extract_text import (
    extract_text_with_html2text,
)
from markitdown import MarkItDown
from langchain_core.messages import SystemMessage, HumanMessage
from utils import load_prompt


def extract_markdown(url: str) -> str:

    maybe_pdf = url.lower().endswith(".pdf") or "arxiv.org/pdf/" in url.lower()

    if maybe_pdf:
        md = MarkItDown()
        pdf_response = requests.get(url, timeout=10)

        if len(pdf_response.content) > 10 * 1024 * 1024:
            return "File too large"

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_file.write(pdf_response.content)
            temp_path = temp_file.name

        result = md.convert(temp_path)

        try:
            os.unlink(temp_path)
        except:
            pass

        return result

    try:
        html = fetch_html_with_patchright(url)
    except TimeoutError:
        return f"Timeout error fetching HTML: {url}"

    return extract_text_with_html2text(html)


CONTENT_QUERY_SYSTEM_PROMPT = load_prompt("content_query_system_prompt.md")


@tool(parse_docstring=True)
def query_resource(uri: str, query: str) -> str:
    """Delegate to an AI agent to answer a query based on the content of a resource, which can be a webpage or a PDF.

    Args:
        uri: The URI of the resource to fetch and analyze.
        query: The question or query to ask about the resource content.

    Returns:
        A string containing the answer to the question based on the resource content.
    """

    markdown = extract_markdown(uri)

    model = ChatOpenAI(model="gpt-4.1-mini")

    response = model.invoke(
        [
            SystemMessage(content=CONTENT_QUERY_SYSTEM_PROMPT),
            HumanMessage(
                content=f"""
<content>
{markdown}
</content>

<query>
{query}
</query>                
""",
            ),
        ],
    )

    return response.content


if __name__ == "__main__":
    print(
        extract_markdown(
            "https://www.zobodat.at/pdf/Atalanta_41_0335-0347.pdf",
        )
    )
