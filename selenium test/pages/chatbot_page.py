from selenium.webdriver.common.by import By

from pages.base_page import BasePage
from pages.config import USER_BASE_URL


class ChatbotPage(BasePage):
    MESSAGE_BUBBLE_SELECTOR = "div[class*='chatBox'] div[class*='user'], div[class*='chatBox'] div[class*='bot']"
    USER_MESSAGE_SELECTOR = "div[class*='chatBox'] div[class*='user']"
    BOT_MESSAGE_SELECTOR = "div[class*='chatBox'] div[class*='bot']"
    CHAT_BUTTON = (By.CSS_SELECTOR, "button[class*='chatButton']")
    CHAT_BOX = (By.CSS_SELECTOR, "div[class*='chatBox']")
    CLOSE_BUTTON = (By.CSS_SELECTOR, "button[class*='closeBtn']")
    INPUT = (By.CSS_SELECTOR, "div[class*='chatBox'] input")
    SEND_BUTTON = (By.CSS_SELECTOR, "button[class*='sendBtn']")
    MESSAGES = (By.CSS_SELECTOR, MESSAGE_BUBBLE_SELECTOR)
    USER_MESSAGES = (By.CSS_SELECTOR, "div[class*='user']")
    BOT_MESSAGES = (By.CSS_SELECTOR, "div[class*='bot']")

    def __init__(self, driver):
        super().__init__(driver, USER_BASE_URL)

    def open_home(self):
        self.open_path("/")

    def is_chat_closed(self):
        return len(self.visible_elements(self.CHAT_BOX)) == 0

    def is_open_button_visible(self):
        return len(self.visible_elements(self.CHAT_BUTTON)) > 0

    def open_chat(self):
        self.click(self.CHAT_BUTTON)
        return self.wait_visible(self.CHAT_BOX)

    def close_chat(self):
        self.click(self.CLOSE_BUTTON)
        self.wait_until(lambda d: len(self.visible_elements(self.CHAT_BOX)) == 0)

    def send_message(self, message):
        self.type_text(self.INPUT, message)
        self.click(self.SEND_BUTTON)

    def input_value(self):
        return self.wait_visible(self.INPUT).get_attribute("value")

    def input_is_disabled(self):
        return self.wait_visible(self.INPUT).get_attribute("disabled") is not None

    def send_button_is_disabled(self):
        return self.wait_visible(self.SEND_BUTTON).get_attribute("disabled") is not None

    def message_texts(self):
        return self._visible_texts(self.MESSAGE_BUBBLE_SELECTOR)

    def user_message_texts(self):
        return self._visible_texts(self.USER_MESSAGE_SELECTOR)

    def user_message_htmls(self):
        return self._visible_html(self.USER_MESSAGE_SELECTOR)

    def bot_message_count(self):
        return len(self._visible_texts(self.BOT_MESSAGE_SELECTOR))

    def _visible_texts(self, selector):
        return self.driver.execute_script(
            """
            return [...document.querySelectorAll(arguments[0])]
                .filter((element) => {
                    const style = window.getComputedStyle(element);
                    const rect = element.getBoundingClientRect();
                    return style.display !== "none"
                        && style.visibility !== "hidden"
                        && rect.width > 0
                        && rect.height > 0;
                })
                .map((element) => element.innerText);
            """,
            selector,
        )

    def _visible_html(self, selector):
        return self.driver.execute_script(
            """
            return [...document.querySelectorAll(arguments[0])]
                .filter((element) => {
                    const style = window.getComputedStyle(element);
                    const rect = element.getBoundingClientRect();
                    return style.display !== "none"
                        && style.visibility !== "hidden"
                        && rect.width > 0
                        && rect.height > 0;
                })
                .map((element) => element.innerHTML);
            """,
            selector,
        )
