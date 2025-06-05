from trafilatura import extract
import html2text


def extract_text_with_trafilatura(html: str) -> str:
    text = extract(html, include_links=True)
    return text


def extract_text_with_html2text(html: str) -> str:
    text = html2text.html2text(html)
    return text
