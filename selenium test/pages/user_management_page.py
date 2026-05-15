from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

from pages.base_page import BasePage
from pages.config import ADMIN_BASE_URL


class UserManagementPage(BasePage):
    SEARCH_INPUT = (By.CSS_SELECTOR, "input[type='text']")
    SELECTS = (By.CSS_SELECTOR, "select")
    APPLY_BUTTON = (By.CSS_SELECTOR, "button[class*='applyBtn']")
    RESET_BUTTON = (By.CSS_SELECTOR, "button[class*='clearBtn']")
    TABLE = (By.CSS_SELECTOR, "table")
    TABLE_ROWS = (By.CSS_SELECTOR, "tbody tr")
    DELETE_BUTTONS = (By.CSS_SELECTOR, "tbody tr button")
    TITLE = (By.CSS_SELECTOR, "h1")

    def __init__(self, driver):
        super().__init__(driver, ADMIN_BASE_URL)

    def open_users(self):
        self.open_path("/admin/users")
        self.wait_visible(self.TABLE, 20)

    def search(self, value):
        self.type_text(self.SEARCH_INPUT, value)
        self.click(self.APPLY_BUTTON)
        self.wait_present(self.TABLE)

    def reset_filters(self):
        self.click(self.RESET_BUTTON)
        self.wait_until(lambda d: self.wait_visible(self.SEARCH_INPUT).get_attribute("value") == "")

    def select_status(self, value):
        selects = self.visible_elements(self.SELECTS)
        Select(selects[1]).select_by_value(value)
        self.click(self.APPLY_BUTTON)
        self.wait_present(self.TABLE)

    def select_role(self, value):
        selects = self.visible_elements(self.SELECTS)
        Select(selects[0]).select_by_value(value)
        self.click(self.APPLY_BUTTON)
        self.wait_present(self.TABLE)

    def apply_compound_filter(self, search, role, status):
        self.type_text(self.SEARCH_INPUT, search)
        selects = self.visible_elements(self.SELECTS)
        Select(selects[0]).select_by_value(role)
        Select(selects[1]).select_by_value(status)
        self.click(self.APPLY_BUTTON)
        self.wait_present(self.TABLE)

    def row_count(self):
        return len(self.visible_elements(self.TABLE_ROWS))

    def title_text(self):
        return self.wait_visible(self.TITLE).text

    def table_headers(self):
        return self.driver.execute_script(
            """
            return [...document.querySelectorAll("thead th")]
                .map((cell) => cell.innerText.trim())
                .filter(Boolean);
            """
        )

    def search_placeholder(self):
        return self.wait_visible(self.SEARCH_INPUT).get_attribute("placeholder")

    def role_filter_options(self):
        selects = self.visible_elements(self.SELECTS)
        return [option.text for option in Select(selects[0]).options]

    def status_filter_options(self):
        selects = self.visible_elements(self.SELECTS)
        return [option.text for option in Select(selects[1]).options]

    def row_dicts(self):
        return self.driver.execute_script(
            """
            return [...document.querySelectorAll("tbody tr")].map((row) => {
                const cells = [...row.querySelectorAll("td")].map((cell) => cell.innerText.trim());
                return {
                    index: cells[0] || "",
                    name: cells[1] || "",
                    email: cells[2] || "",
                    birthday: cells[3] || "",
                    createdAt: cells[4] || "",
                    status: cells[5] || "",
                    role: cells[6] || "",
                    deleteText: cells[7] || "",
                    buttonCount: row.querySelectorAll("button").length,
                    editIconCount: [...row.querySelectorAll("span")].filter((span) => span.innerText.trim()).length,
                    rawText: row.innerText.trim(),
                };
            });
            """
        )

    def data_rows(self):
        return [row for row in self.row_dicts() if row["email"]]

    def empty_message_text(self):
        rows = self.row_dicts()
        return rows[0]["rawText"] if rows else ""

    def cancel_first_delete_confirmation(self):
        buttons = self.visible_elements(self.DELETE_BUTTONS)
        if not buttons:
            return False
        buttons[-1].click()
        alert = self.wait_until(lambda d: d.switch_to.alert)
        alert.dismiss()
        self.wait_visible(self.TABLE)
        return True
