import base64
import json
import time

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from config import (
    BASE_URL,
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    EXISTING_EMAIL,
    EXPLICIT_WAIT,
    NEW_USER_PASSWORD,
    USER1_EMAIL,
    USER1_PASSWORD,
    WRONG_PASSWORD,
)


USER_APP_URL = BASE_URL.rstrip("/")
ADMIN_APP_URL = "http://localhost:3002"


class TestAuthenticationFlows:
    USER_LOGIN_EMAIL = (By.CSS_SELECTOR, "input[name='email']")
    USER_LOGIN_PASSWORD = (By.CSS_SELECTOR, "input[name='password']")
    USER_LOGIN_SUBMIT = (By.CSS_SELECTOR, "button[type='submit']")

    USER_REGISTER_NAME = (By.CSS_SELECTOR, "input[name='user_name']")
    USER_REGISTER_EMAIL = (By.CSS_SELECTOR, "input[name='email']")
    USER_REGISTER_PASSWORD = (By.CSS_SELECTOR, "input[name='password']")
    USER_REGISTER_SUBMIT = (By.CSS_SELECTOR, "button[type='submit']")

    ADMIN_LOGIN_EMAIL = (By.CSS_SELECTOR, "input[name='email']")
    ADMIN_LOGIN_PASSWORD = (By.CSS_SELECTOR, "input[name='password']")
    ADMIN_LOGIN_SUBMIT = (By.CSS_SELECTOR, "button[type='submit']")

    NOTIFICATION = (
        By.CSS_SELECTOR,
        "[class*='notification'], [class*='Notification'], "
        "[class*='toast'], [class*='Toast'], [class*='noti'], [class*='popup'], [role='alert']",
    )
    @pytest.mark.order(1)
    def test_admin_login_successful_with_valid_credentials(self, driver):
        self._clear_auth_state(driver)
        self._open_admin_login(driver)
        self._fill_login_form(
            driver,
            self.ADMIN_LOGIN_EMAIL,
            self.ADMIN_LOGIN_PASSWORD,
            self.ADMIN_LOGIN_SUBMIT,
            ADMIN_EMAIL,
            ADMIN_PASSWORD,
        )

        self._wait_for_url_contains(driver, "/admin/dashboard", timeout=10)
        assert "/admin/dashboard" in driver.current_url, (
            f"Admin hợp lệ phải vào dashboard, URL hiện tại: {driver.current_url}"
        )

    @pytest.mark.order(2)
    def test_admin_login_failed_with_incorrect_password(self, driver):
        self._clear_auth_state(driver)
        self._open_admin_login(driver)
        self._fill_login_form(
            driver,
            self.ADMIN_LOGIN_EMAIL,
            self.ADMIN_LOGIN_PASSWORD,
            self.ADMIN_LOGIN_SUBMIT,
            ADMIN_EMAIL,
            WRONG_PASSWORD,
        )

        time.sleep(1)
        assert "/admin/login" in driver.current_url, (
            "Sai mật khẩu admin phải ở lại trang admin login"
        )
        assert self._has_notification(driver), (
            "Sai mật khẩu admin phải hiển thị thông báo lỗi"
        )

    @pytest.mark.order(3)
    def test_unauthorized_access_attempt_to_admin_area_by_standard_user(self, driver):
        self._clear_auth_state(driver)
        self._open_admin_login(driver)
        self._fill_login_form(
            driver,
            self.ADMIN_LOGIN_EMAIL,
            self.ADMIN_LOGIN_PASSWORD,
            self.ADMIN_LOGIN_SUBMIT,
            USER1_EMAIL,
            USER1_PASSWORD,
        )

        time.sleep(1)
        assert "/admin/dashboard" not in driver.current_url, (
            "User thường không được vào admin dashboard"
        )
        assert (
            "/admin/login" in driver.current_url or self._has_notification(driver)
        ), "User thường phải bị giữ ở admin login hoặc hiện cảnh báo quyền"

        driver.get(f"{ADMIN_APP_URL}/admin/dashboard")
        time.sleep(2)
        assert "/admin/login" in driver.current_url, (
            f"Truy cập thẳng khu vực admin khi không đủ quyền phải quay về /admin/login, "
            f"URL hiện tại: {driver.current_url}"
        )

    @pytest.mark.order(4)
    def test_user_registration_successful_with_new_email(self, driver):
        self._clear_auth_state(driver)
        unique_email = f"autotest_{int(time.time())}@example.com"

        driver.get(f"{USER_APP_URL}/register")
        self._type(driver, self.USER_REGISTER_NAME, "Autotest User")
        self._type(driver, self.USER_REGISTER_EMAIL, unique_email)
        self._type(driver, self.USER_REGISTER_PASSWORD, NEW_USER_PASSWORD)
        self._submit_form(
            driver,
            WebDriverWait(driver, EXPLICIT_WAIT).until(
                EC.visibility_of_element_located(self.USER_REGISTER_PASSWORD)
            ),
            self.USER_REGISTER_SUBMIT,
        )

        self._wait_for_url_contains_any(
            driver,
            ["/", "/login"],
            timeout=10,
        )
        assert "/register" not in driver.current_url, (
            f"Đăng ký email mới phải thành công và rời khỏi /register, URL hiện tại: {driver.current_url}"
        )

    @pytest.mark.order(5)
    def test_registration_with_an_email_that_already_exists(self, driver):
        self._clear_auth_state(driver)
        driver.get(f"{USER_APP_URL}/register")
        self._type(driver, self.USER_REGISTER_NAME, "Duplicate User")
        self._type(driver, self.USER_REGISTER_EMAIL, EXISTING_EMAIL)
        password_input = self._type(driver, self.USER_REGISTER_PASSWORD, NEW_USER_PASSWORD)
        submit_result = self._submit_form(driver, password_input, self.USER_REGISTER_SUBMIT)
        if not submit_result.get("notification_seen"):
            submit_result = self._submit_form(driver, password_input, self.USER_REGISTER_SUBMIT)

        error_text = submit_result.get("notification_text") or self._wait_for_notification_text(
            driver,
            [
                "Email đã tồn tại. Vui lòng chọn email khác!",
                "Email đã tồn tại",
            ],
            timeout=5,
        )
        assert "/register" in driver.current_url, (
            "Email đã tồn tại phải ở lại trang register"
        )
        assert submit_result.get("notification_seen") or error_text, (
            "Email đã tồn tại phải hiển thị thông báo lỗi phù hợp"
        )

    @pytest.mark.order(6)
    def test_standard_user_login_successful_with_valid_credentials(self, driver):
        self._clear_auth_state(driver)
        self._open_user_login(driver)
        self._fill_login_form(
            driver,
            self.USER_LOGIN_EMAIL,
            self.USER_LOGIN_PASSWORD,
            self.USER_LOGIN_SUBMIT,
            USER1_EMAIL,
            USER1_PASSWORD,
        )

        self._wait_for_url_contains_any(driver, ["/", "/exam", "/document"], timeout=10)
        assert "/login" not in driver.current_url, (
            f"User hợp lệ không được ở lại /login, URL hiện tại: {driver.current_url}"
        )

    @pytest.mark.order(7)
    def test_session_expiration_handling_on_protected_screens(self, driver):
        self._clear_auth_state(driver)
        self._open_user_login(driver)
        self._fill_login_form(
            driver,
            self.USER_LOGIN_EMAIL,
            self.USER_LOGIN_PASSWORD,
            self.USER_LOGIN_SUBMIT,
            USER1_EMAIL,
            USER1_PASSWORD,
        )
        self._wait_for_url_contains_any(driver, ["/", "/exam"], timeout=10)

        expired_token = self._build_expired_jwt()
        driver.execute_script(
            """
            document.cookie = arguments[0];
            localStorage.setItem("token", arguments[1]);
            """,
            f"token={expired_token}; path=/",
            expired_token,
        )

        driver.get(f"{USER_APP_URL}/exam")
        self._wait_for_url_contains(driver, "/login", timeout=10)
        assert "/login" in driver.current_url, (
            f"Session hết hạn phải quay về /login, URL hiện tại: {driver.current_url}"
        )

    def _open_user_login(self, driver):
        driver.get(f"{USER_APP_URL}/login")

    def _open_admin_login(self, driver):
        driver.get(f"{ADMIN_APP_URL}/admin/login")

    def _fill_login_form(
        self,
        driver,
        email_locator,
        password_locator,
        submit_locator,
        email,
        password,
    ):
        self._type(driver, email_locator, email)
        password_input = self._type(driver, password_locator, password)
        self._submit_form(driver, password_input, submit_locator)

    def _type(self, driver, locator, value):
        element = WebDriverWait(driver, EXPLICIT_WAIT).until(
            EC.visibility_of_element_located(locator)
        )
        element.clear()
        element.send_keys(value)
        return element

    def _click(self, driver, locator):
        WebDriverWait(driver, EXPLICIT_WAIT).until(
            EC.element_to_be_clickable(locator)
        ).click()

    def _submit_form(self, driver, password_input, submit_locator):
        current_url = driver.current_url
        result = {
            "url_changed": False,
            "notification_seen": False,
            "notification_text": None,
        }

        try:
            password_input.send_keys(Keys.ENTER)
            result["url_changed"] = self._url_changed_from(driver, current_url, timeout=3)
            if result["url_changed"]:
                return result

            notification_text = self._capture_notification_text(driver, timeout=2)
            if notification_text:
                result["notification_seen"] = True
                result["notification_text"] = notification_text
                return result
        except Exception:
            pass

        try:
            submitted = driver.execute_script(
                """
                const field = arguments[0];
                const form = field ? field.closest("form") : null;
                if (!form) {
                    return false;
                }
                if (typeof form.requestSubmit === "function") {
                    form.requestSubmit();
                    return true;
                }
                const submitEvent = new Event("submit", { bubbles: true, cancelable: true });
                form.dispatchEvent(submitEvent);
                return true;
                """,
                password_input,
            )
            if submitted:
                result["url_changed"] = self._url_changed_from(driver, current_url, timeout=3)
                if result["url_changed"]:
                    return result

                notification_text = self._capture_notification_text(driver, timeout=2)
                if notification_text:
                    result["notification_seen"] = True
                    result["notification_text"] = notification_text
                    return result
        except Exception:
            pass

        try:
            submit_button = WebDriverWait(driver, EXPLICIT_WAIT).until(
                EC.element_to_be_clickable(submit_locator)
            )
            driver.execute_script(
                """
                const button = arguments[0];
                const form = button.closest("form");
                if (form && typeof form.requestSubmit === "function") {
                    form.requestSubmit(button);
                    return;
                }
                if (form) {
                    const submitEvent = new Event("submit", { bubbles: true, cancelable: true });
                    form.dispatchEvent(submitEvent);
                    return;
                }
                button.click();
                """,
                submit_button,
            )
            result["url_changed"] = self._url_changed_from(driver, current_url, timeout=3)
            if result["url_changed"]:
                return result

            notification_text = self._capture_notification_text(driver, timeout=2)
            if notification_text:
                result["notification_seen"] = True
                result["notification_text"] = notification_text
                return result
        except Exception:
            pass

        try:
            self._click(driver, submit_locator)
        except Exception:
            driver.execute_script(
                """
                const buttons = Array.from(document.querySelectorAll("button[type='submit'], button"));
                const target = buttons.find((button) =>
                  /dang ky|đăng ký|register/i.test((button.innerText || "").trim())
                );
                if (target) {
                  target.click();
                }
                """
            )
        notification_text = self._capture_notification_text(driver, timeout=2)
        if notification_text:
            result["notification_seen"] = True
            result["notification_text"] = notification_text
        return result

    def _is_visible(self, driver, locator, timeout=5):
        try:
            WebDriverWait(driver, timeout).until(
                EC.visibility_of_element_located(locator)
            )
            return True
        except Exception:
            return False

    def _has_notification(self, driver):
        return self._is_visible(driver, self.NOTIFICATION, timeout=5)

    def _capture_notification_text(self, driver, timeout=2):
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.visibility_of_element_located(self.NOTIFICATION)
            )
            text = (element.text or "").strip()
            return text or "notification_seen"
        except Exception:
            return None

    def _wait_for_text_in_page(self, driver, texts, timeout=5):
        def _match(d):
            try:
                source = d.page_source or ""
            except Exception:
                return False

            for text in texts:
                if text in source:
                    return text
            return False

        try:
            return WebDriverWait(driver, timeout).until(_match)
        except Exception:
            return None

    def _wait_for_notification_text(self, driver, texts=None, timeout=5):
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.visibility_of_element_located(self.NOTIFICATION)
            )
            text = (element.text or "").strip()
            if text:
                return text
        except Exception:
            pass

        if texts:
            return self._wait_for_text_in_page(driver, texts, timeout=timeout)

        try:
            source = (driver.page_source or "").lower()
        except Exception:
            return None

        if "email" in source and any(
            keyword in source for keyword in ("tá»“n táº¡i", "ton tai", "exists", "exist")
        ):
            return "email ton tai"
        return None

    def _wait_for_url_contains(self, driver, fragment, timeout=EXPLICIT_WAIT):
        WebDriverWait(driver, timeout).until(EC.url_contains(fragment))

    def _wait_for_url_contains_any(self, driver, fragments, timeout=EXPLICIT_WAIT):
        WebDriverWait(driver, timeout).until(
            lambda d: any(fragment in d.current_url for fragment in fragments)
        )

    def _url_changed_from(self, driver, old_url, timeout=3):
        try:
            WebDriverWait(driver, timeout).until(lambda d: d.current_url != old_url)
            return True
        except Exception:
            return False

    def _clear_auth_state(self, driver):
        for origin in (USER_APP_URL, ADMIN_APP_URL):
            driver.get(origin)
            driver.delete_all_cookies()
            driver.execute_script(
                """
                try { localStorage.clear(); } catch (e) {}
                try { sessionStorage.clear(); } catch (e) {}
                """
            )

    def _build_expired_jwt(self):
        header = self._base64url_encode({"alg": "HS256", "typ": "JWT"})
        payload = self._base64url_encode({"exp": 1, "email": USER1_EMAIL})
        return f"{header}.{payload}.signature"

    def _base64url_encode(self, value):
        raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")
