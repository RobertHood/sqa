from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait


class BasePage:
    def __init__(self, driver, base_url):
        self.driver = driver
        self.base_url = base_url.rstrip("/")

    def open_path(self, path):
        self.driver.get(f"{self.base_url}{path}")

    def wait_visible(self, locator, timeout=12):
        return WebDriverWait(self.driver, timeout).until(ec.visibility_of_element_located(locator))

    def wait_clickable(self, locator, timeout=12):
        return WebDriverWait(self.driver, timeout).until(ec.element_to_be_clickable(locator))

    def wait_present(self, locator, timeout=12):
        return WebDriverWait(self.driver, timeout).until(ec.presence_of_element_located(locator))

    def wait_all_present(self, locator, timeout=12):
        return WebDriverWait(self.driver, timeout).until(ec.presence_of_all_elements_located(locator))

    def click(self, locator, timeout=12):
        self.wait_clickable(locator, timeout).click()

    def type_text(self, locator, text, timeout=12, clear=True):
        element = self.wait_visible(locator, timeout)
        if clear:
            element.clear()
        element.send_keys(text)
        return element

    def visible_elements(self, locator):
        return [element for element in self.driver.find_elements(*locator) if element.is_displayed()]

    def wait_until(self, condition, timeout=12):
        return WebDriverWait(self.driver, timeout).until(condition)

