"""Selenium scaffold — the ONLY module allowed to import `selenium`.

Lazy connect: nothing launches until `open()` is called. Headless Chrome via
selenium-manager (no chromedriver path needed).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SeleniumPage:
    url: str
    title: str
    text: str


class SeleniumDriver:
    """One headless-Chrome session; `open(url)` navigates and snapshots text."""

    def __init__(self, headless: bool = True) -> None:
        self._headless = headless
        self._driver = None

    def _connect(self):
        if self._driver is not None:
            return self._driver
        from selenium import webdriver

        options = webdriver.ChromeOptions()
        if self._headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        self._driver = webdriver.Chrome(options=options)
        return self._driver

    def open(self, url: str) -> SeleniumPage:
        """Navigate to `url` and return its title + visible text."""
        driver = self._connect()
        driver.get(url)
        text = driver.execute_script("return document.body ? document.body.innerText : '';")
        return SeleniumPage(url=driver.current_url, title=driver.title, text=(text or "")[:4000])

    def close(self) -> None:
        if self._driver is not None:
            self._driver.quit()
            self._driver = None
