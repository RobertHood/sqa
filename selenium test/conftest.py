import os
from pathlib import Path

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.firefox.options import Options as FirefoxOptions


def _is_truthy(value: str | None) -> bool:
    return str(value).lower() in {"1", "true", "yes", "y", "on"}


def _build_driver():
    browser = os.getenv("BROWSER", "edge").lower()
    headless = _is_truthy(os.getenv("HEADLESS"))

    if browser == "edge":
        options = EdgeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1440,1000")

        edge_binary = _find_edge_binary()
        if edge_binary:
            options.binary_location = str(edge_binary)

        driver_path = _find_local_driver("EDGE_DRIVER_PATH", "msedgedriver.exe")
        if driver_path:
            return webdriver.Edge(service=EdgeService(str(driver_path)), options=options)

        return webdriver.Edge(options=options)

    if browser == "firefox":
        options = FirefoxOptions()
        if headless:
            options.add_argument("-headless")
        driver = webdriver.Firefox(options=options)
        driver.set_window_size(1440, 1000)
        return driver

    options = ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,1000")
    options.add_argument("--disable-gpu")
    return webdriver.Chrome(options=options)


def _find_local_driver(env_var, executable_name):
    configured = os.getenv(env_var)
    if configured and Path(configured).is_file():
        return Path(configured)

    local_driver = Path(__file__).resolve().parent / "drivers" / executable_name
    if local_driver.is_file():
        return local_driver

    return None


def _find_edge_binary():
    candidates = [
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Edge/Application/msedge.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


@pytest.fixture
def driver():
    driver = _build_driver()
    driver.implicitly_wait(0)
    yield driver
    driver.quit()
