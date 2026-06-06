"""
ORACLE.AI — Browser Agent (Phase 2)
Playwright-powered Chrome automation.
Gives ORACLE the ability to navigate, click, scrape, and interact with the web autonomously.
"""

import sys
import asyncio
from pathlib import Path

ROOT = Path(__file__).parent.parent

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class BrowserAgent:
    def __init__(self, headless=False):
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError(
                "Playwright not installed. Run: pip install playwright && playwright install chromium"
            )
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._page = None

    def start(self):
        """Launch browser session."""
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=["--start-maximized"]
        )
        context = self._browser.new_context(viewport=None)
        self._page = context.new_page()
        return self

    def stop(self):
        """Close browser session."""
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        self._page = None
        self._browser = None
        self._playwright = None

    def navigate(self, url: str) -> str:
        """Navigate to a URL."""
        if not url.startswith("http"):
            url = "https://" + url
        self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
        return f"Navigated to: {self._page.url}"

    def get_page_text(self) -> str:
        """Extract all visible text from current page."""
        text = self._page.inner_text("body")
        return text[:8000] if text else "No text found."

    def get_page_title(self) -> str:
        """Get current page title."""
        return self._page.title()

    def get_current_url(self) -> str:
        """Get current URL."""
        return self._page.url

    def click(self, selector: str) -> str:
        """Click an element by CSS selector or text."""
        try:
            self._page.click(selector, timeout=10000)
            return f"Clicked: {selector}"
        except PWTimeout:
            # Try clicking by text if selector fails
            try:
                self._page.get_by_text(selector).first.click()
                return f"Clicked by text: {selector}"
            except Exception as e:
                return f"Click failed: {e}"

    def type_text(self, selector: str, text: str) -> str:
        """Type text into an input field."""
        try:
            self._page.fill(selector, text)
            return f"Typed into {selector}: {text[:50]}"
        except Exception as e:
            return f"Type failed: {e}"

    def search(self, query: str, engine: str = "google") -> str:
        """Perform a web search and return top results text."""
        engines = {
            "google": f"https://www.google.com/search?q={query.replace(' ', '+')}",
            "bing": f"https://www.bing.com/search?q={query.replace(' ', '+')}",
            "duckduckgo": f"https://duckduckgo.com/?q={query.replace(' ', '+')}"
        }
        url = engines.get(engine.lower(), engines["google"])
        self.navigate(url)
        self._page.wait_for_timeout(2000)
        return self.get_page_text()

    def screenshot(self, filename: str = None) -> str:
        """Take a screenshot of current page."""
        if not filename:
            from datetime import datetime
            filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        path = ROOT / "Logs" / filename
        self._page.screenshot(path=str(path), full_page=False)
        return f"Screenshot saved: {path}"

    def scrape_links(self) -> list:
        """Get all links on current page."""
        links = self._page.eval_on_selector_all(
            "a[href]",
            "elements => elements.map(e => ({text: e.innerText.trim(), href: e.href}))"
        )
        return [l for l in links if l["href"].startswith("http")][:50]

    def wait_for(self, selector: str, timeout: int = 10000) -> str:
        """Wait for an element to appear."""
        try:
            self._page.wait_for_selector(selector, timeout=timeout)
            return f"Element found: {selector}"
        except PWTimeout:
            return f"Timeout waiting for: {selector}"

    def scroll_down(self, amount: int = 500) -> str:
        """Scroll down the page."""
        self._page.evaluate(f"window.scrollBy(0, {amount})")
        return f"Scrolled down {amount}px"

    def execute_js(self, script: str) -> str:
        """Execute JavaScript on the current page."""
        result = self._page.evaluate(script)
        return str(result)

    def fill_form(self, fields: dict) -> str:
        """Fill multiple form fields. fields = {selector: value}"""
        results = []
        for selector, value in fields.items():
            try:
                self._page.fill(selector, value)
                results.append(f"Filled {selector}")
            except Exception as e:
                results.append(f"Failed {selector}: {e}")
        return "\n".join(results)

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.stop()


# ── Standalone tool functions (called by executor) ───────────────────────────

def browser_navigate(url: str, headless: bool = False) -> str:
    """Single-shot navigation — opens browser, navigates, returns page text."""
    with BrowserAgent(headless=headless) as agent:
        agent.navigate(url)
        title = agent.get_page_title()
        text = agent.get_page_text()
        return f"[{title}]\n{text[:4000]}"


def browser_search(query: str, engine: str = "google", headless: bool = False) -> str:
    """Single-shot web search."""
    with BrowserAgent(headless=headless) as agent:
        text = agent.search(query, engine)
        return text[:4000]


# Global persistent session (for multi-step browsing within a session)
_active_session: BrowserAgent = None


def session_start(headless: bool = False) -> str:
    global _active_session
    if _active_session:
        return "Browser session already active."
    _active_session = BrowserAgent(headless=headless).start()
    return "Browser session started."


def session_stop() -> str:
    global _active_session
    if not _active_session:
        return "No active browser session."
    _active_session.stop()
    _active_session = None
    return "Browser session closed."


def session_navigate(url: str) -> str:
    if not _active_session:
        return "No active browser session. Call session_start first."
    return _active_session.navigate(url)


def session_get_text() -> str:
    if not _active_session:
        return "No active browser session."
    return _active_session.get_page_text()


def session_click(selector: str) -> str:
    if not _active_session:
        return "No active browser session."
    return _active_session.click(selector)


def session_type(selector: str, text: str) -> str:
    if not _active_session:
        return "No active browser session."
    return _active_session.type_text(selector, text)


def session_screenshot() -> str:
    if not _active_session:
        return "No active browser session."
    return _active_session.screenshot()
