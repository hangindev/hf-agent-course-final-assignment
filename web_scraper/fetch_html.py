from trafilatura import fetch_url
from patchright.sync_api import sync_playwright, Error as PatchrightError


class TimeoutError(Exception):
    pass


def fetch_html_with_patchright(url: str) -> str:
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url)
        except PatchrightError as e:
            raise TimeoutError(f"Timeout error")
        html = page.content()
        browser.close()
    return html


def fetch_html_with_trafilatura(url: str) -> str:
    html = fetch_url(url)
    return html
