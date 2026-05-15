from selenium.webdriver.common.by import By

from pages.base_page import BasePage
from pages.config import ADMIN_BASE_URL, USER_BASE_URL


class UserLoginPage(BasePage):
    EMAIL = (By.NAME, "email")
    PASSWORD = (By.NAME, "password")
    SUBMIT = (By.CSS_SELECTOR, "button[type='submit']")

    def __init__(self, driver):
        super().__init__(driver, USER_BASE_URL)

    def login(self, email, password):
        self.open_path("/login")
        self.type_text(self.EMAIL, email)
        self.type_text(self.PASSWORD, password)
        self.click(self.SUBMIT)
        self.wait_until(lambda d: d.get_cookie("token") is not None or "/login" not in d.current_url, 15)


class AdminLoginPage(BasePage):
    EMAIL = (By.NAME, "email")
    PASSWORD = (By.NAME, "password")
    SUBMIT = (By.CSS_SELECTOR, "button[type='submit']")

    def __init__(self, driver):
        super().__init__(driver, ADMIN_BASE_URL)

    def login(self, email, password):
        self.open_path("/admin/login")
        self.type_text(self.EMAIL, email)
        self.type_text(self.PASSWORD, password)
        self.click(self.SUBMIT)
        self.wait_until(lambda d: d.get_cookie("token") is not None or "/admin/login" not in d.current_url, 15)

