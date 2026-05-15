from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

from pages.base_page import BasePage
from pages.config import USER_BASE_URL


class FlashcardPage(BasePage):
    CREATE_DECK_CARD = (By.CSS_SELECTOR, "div[class*='createDeck']")
    CREATE_DECK_MODAL = (By.CSS_SELECTOR, "div[class*='modalContent']")
    DECK_TITLE_INPUT = (By.CSS_SELECTOR, "div[class*='modalContent'] input[name='title']")
    DECK_DESCRIPTION_TEXTAREA = (By.CSS_SELECTOR, "div[class*='modalContent'] textarea[name='description']")
    SAVE_BUTTON = (By.CSS_SELECTOR, "div[class*='modalContent'] button[type='submit']")
    DECK_CARDS = (By.CSS_SELECTOR, "div[class*='flashcardDeck']")
    ADD_FLASHCARD_BUTTON = (By.CSS_SELECTOR, "button[class*='btn_add']")
    CARD_FRONT_INPUT = (By.CSS_SELECTOR, "input[class*='inputField']")
    CARD_BACK_TEXTAREA = (By.CSS_SELECTOR, "textarea[class*='textareaField']")
    CARD_SAVE_BUTTON = (By.CSS_SELECTOR, "button[class*='saveButton']")
    REVIEW_LINK = (By.CSS_SELECTOR, "a[href*='/review']")
    QUIZ_LINK = (By.CSS_SELECTOR, "a[href*='/quiz']")
    QUIZ_OPTION_GROUPS = "div[class*='card']"

    def __init__(self, driver):
        super().__init__(driver, USER_BASE_URL)

    def open_decks(self):
        self.open_path("/flashcards")
        self.wait_visible(self.CREATE_DECK_CARD)

    def open_create_deck_modal(self):
        self.click(self.CREATE_DECK_CARD)
        self.wait_visible(self.CREATE_DECK_MODAL)
        self.wait_visible(self.DECK_TITLE_INPUT)

    def create_deck(self, title, description):
        self.open_create_deck_modal()
        self.type_text(self.DECK_TITLE_INPUT, title)
        self.type_text(self.DECK_DESCRIPTION_TEXTAREA, description)
        self.click(self.SAVE_BUTTON)
        self.wait_until(lambda d: title in d.page_source, 20)

    def submit_create_deck_with_current_auth(self, title, description):
        self.open_create_deck_modal()
        self.type_text(self.DECK_TITLE_INPUT, title)
        self.type_text(self.DECK_DESCRIPTION_TEXTAREA, description)
        self.click(self.SAVE_BUTTON)

    def try_submit_empty_deck_title(self):
        self.open_create_deck_modal()
        self.type_text(self.DECK_TITLE_INPUT, "")
        self.click(self.SAVE_BUTTON)
        return self.wait_visible(self.DECK_TITLE_INPUT).get_attribute("validationMessage")

    def accept_alert_if_present(self, timeout=8):
        alert = WebDriverWait(self.driver, timeout).until(ec.alert_is_present())
        text = alert.text
        alert.accept()
        return text

    def open_deck_by_title(self, title):
        title_locator = (By.XPATH, f"//h3[normalize-space()={self._xpath_literal(title)}]")
        self.click(title_locator)
        self.wait_until(lambda d: "/flashcards/" in d.current_url, 15)

    def open_add_flashcard_modal(self):
        self.click(self.ADD_FLASHCARD_BUTTON)
        self.wait_visible(self.CARD_FRONT_INPUT)

    def add_flashcard(self, front, back):
        self.open_add_flashcard_modal()
        self.type_text(self.CARD_FRONT_INPUT, front)
        self.type_text(self.CARD_BACK_TEXTAREA, back)
        self.click(self.CARD_SAVE_BUTTON)
        self.wait_until(lambda d: front in d.page_source and back in d.page_source, 20)

    def open_quiz(self):
        self.click(self.QUIZ_LINK)
        self.wait_until(lambda d: "/quiz" in d.current_url, 10)

    def quiz_option_groups(self):
        return self.driver.execute_script(
            """
            return [...document.querySelectorAll(arguments[0])]
                .map((card) => [...card.querySelectorAll("button[class*='option']")]
                    .map((button) => button.innerText.trim())
                    .filter(Boolean))
                .filter((options) => options.length > 0);
            """,
            self.QUIZ_OPTION_GROUPS,
        )

    def wait_for_quiz_options(self):
        return self.wait_until(lambda d: len(self.quiz_option_groups()) > 0, 15)

    def detail_actions_are_visible(self):
        return (
            self.wait_visible(self.ADD_FLASHCARD_BUTTON).is_displayed()
            and self.wait_visible(self.REVIEW_LINK).is_displayed()
            and self.wait_visible(self.QUIZ_LINK).is_displayed()
        )

    @staticmethod
    def _xpath_literal(value):
        if "'" not in value:
            return f"'{value}'"
        if '"' not in value:
            return f'"{value}"'
        parts = value.split("'")
        return "concat(" + ', "\'", '.join(f"'{part}'" for part in parts) + ")"
