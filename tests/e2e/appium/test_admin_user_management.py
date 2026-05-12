# tests/test_admin_user_management.py
# Kiem thu Admin User Management

import json
import time
import urllib.error
import urllib.parse
import urllib.request

import pytest
from selenium.webdriver.support.ui import WebDriverWait
from pages.admin_user_page import AdminUserPage
from pages.login_page import LoginPage
from config import (
    ADMIN_BASE_URL,
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    BASE_URL,
    SEARCH_KEYWORD_LONG,
    SEARCH_KEYWORD_SPECIAL,
)


BACKEND_BASE_URL = "http://localhost:3000"


def clear_auth_state(driver):
    for origin in (BASE_URL, ADMIN_BASE_URL):
        try:
            driver.get(origin)
        except Exception:
            continue

        try:
            driver.execute_script(
                """
                try { localStorage.clear(); } catch (e) {}
                try { sessionStorage.clear(); } catch (e) {}
                """
            )
        except Exception:
            pass

        try:
            driver.delete_all_cookies()
        except Exception:
            pass


def _parse_json(body: str) -> dict:
    if not body:
        return {}
    try:
        return json.loads(body)
    except Exception:
        return {}


def api_request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict | None = None,
    timeout: int = 25,
):
    url = f"{BACKEND_BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    data = None

    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url=url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.getcode()
            body = resp.read().decode("utf-8", errors="ignore")
            return status, _parse_json(body)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        return exc.code, _parse_json(body)


def get_login_session(email: str, password: str) -> dict:
    status, data = api_request(
        "POST",
        "/auth/login",
        payload={"email": email, "password": password},
    )
    if status != 200:
        raise RuntimeError(f"Login that bai ({email}), status={status}, response={data}")

    payload = data.get("data") or {}
    token = payload.get("token")
    user = payload.get("user") or {}
    permissions = payload.get("permissions") or []
    if not token:
        raise RuntimeError(f"Login response thieu token ({email}): {data}")

    return {"token": token, "user": user, "permissions": permissions}


def get_admin_session() -> dict:
    return get_login_session(ADMIN_EMAIL, ADMIN_PASSWORD)


def get_admin_token() -> str:
    return get_admin_session()["token"]


def api_register_user(user_name: str, email: str, password: str):
    return api_request(
        "POST",
        "/auth/register",
        payload={"user_name": user_name, "email": email, "password": password},
    )


def api_find_user_by_email(admin_token: str, email: str):
    query = urllib.parse.urlencode(
        {
            "page": 1,
            "status": "All",
            "role": "All",
            "search": email,
        }
    )
    status, data = api_request("GET", f"/users?{query}", token=admin_token)
    if status != 200:
        raise RuntimeError(f"Lay user list that bai, status={status}, response={data}")

    rows = (data.get("data") or {}).get("users") or []
    target = email.strip().lower()
    for row in rows:
        if (row.get("email") or "").strip().lower() == target:
            return row
    return None


def api_delete_user(admin_token: str, user_id: int):
    return api_request("DELETE", f"/users/remove/{user_id}", token=admin_token)


def create_temp_user(prefix: str = "autouser") -> dict:
    ts = int(time.time() * 1000)
    user = {
        "name": f"{prefix}_{ts}",
        "email": f"{prefix}+{ts}@example.com",
        "password": "User123!",
    }

    status, data = api_register_user(
        user_name=user["name"],
        email=user["email"],
        password=user["password"],
    )
    if status not in (200, 201):
        raise RuntimeError(
            f"Khong tao duoc temp user ({user['email']}), status={status}, response={data}"
        )
    return user


def login_admin_and_open_users(driver) -> AdminUserPage:
    clear_auth_state(driver)
    session = get_admin_session()
    users_page = AdminUserPage(driver)

    driver.get(ADMIN_BASE_URL)
    driver.execute_script(
        """
        document.cookie = `token=${arguments[0]}; path=/`;
        localStorage.setItem("user", JSON.stringify(arguments[1]));
        localStorage.setItem("permissions", JSON.stringify(arguments[2]));
        """,
        session["token"],
        session["user"],
        session["permissions"],
    )

    driver.get(users_page.URL)
    users_page.wait_until_loaded(timeout=20)
    assert users_page.is_user_management_page(), (
        f"Khong vao duoc trang quan ly user admin, URL hien tai: {driver.current_url}"
    )
    return users_page


def delete_user_if_exists(driver, email: str):
    try:
        admin_token = get_admin_token()
        user_row = api_find_user_by_email(admin_token, email)
        if user_row and user_row.get("user_id"):
            api_delete_user(admin_token, int(user_row["user_id"]))
    except Exception:
        pass
    finally:
        clear_auth_state(driver)


class TestAdminUserManagement:
    """User list/search/pagination, update role+status, disable+login block, special search."""

    @pytest.mark.run(order=140)
    def test_admin_can_login_and_open_user_management_page(self, driver):
        page = login_admin_and_open_users(driver)

        assert page.is_user_management_page(), (
            f"TC-ADMIN-USER-01: Sau login admin phai vao duoc /admin/users, URL: {driver.current_url}"
        )
        assert page.is_table_or_empty_visible(), (
            "TC-ADMIN-USER-01: Trang users phai hien thi table hoac empty-state"
        )
        assert page.get_user_count_on_current_page() >= 0, (
            "TC-ADMIN-USER-01: So luong user tren trang phai hop le"
        )

        if page.has_multiple_pages():
            before_page = page.get_current_page()
            moved = page.go_to_next_page()
            assert moved, "TC-ADMIN-USER-01: Khong the chuyen trang pagination"
            assert page.get_current_page() != before_page, (
                "TC-ADMIN-USER-01: Pagination phai doi trang hien tai"
            )
        else:
            assert page.get_current_page() == 1, (
                "TC-ADMIN-USER-01: Neu khong co nhieu trang thi phai o trang 1"
            )

    @pytest.mark.run(order=141)
    def test_update_user_roles_and_account_availability_status(self, driver):
        temp_user = create_temp_user(prefix="update")
        try:
            page = login_admin_and_open_users(driver)
            page.search_user(temp_user["email"])

            assert page.has_user_row(temp_user["email"], timeout=8), (
                "TC-ADMIN-USER-02: User test phai xuat hien trong danh sach admin users"
            )

            status_before, status_after = page.toggle_available_by_email(temp_user["email"])
            assert status_before != status_after, (
                "TC-ADMIN-USER-02: Toggle trang thai tai khoan phai thay doi label"
            )

            role_before, role_after = page.change_role_by_email(temp_user["email"], "ADMIN")
            assert role_before != role_after, (
                "TC-ADMIN-USER-02: Cap nhat vai tro phai doi label role tren UI"
            )
            assert "Admin" in role_after, (
                f"TC-ADMIN-USER-02: Sau update role phai la Admin, hien tai: {role_after}"
            )

            page.open_user_management()
            page.wait_until_loaded(timeout=20)
            page.search_user(temp_user["email"])

            reloaded_status = page.get_status_label_by_email(temp_user["email"])
            assert reloaded_status == status_after, (
                "TC-ADMIN-USER-02: Trang thai available phai duoc luu sau reload"
            )

            reloaded_role = page.get_role_label_by_email(temp_user["email"])
            assert "Admin" in reloaded_role, (
                "TC-ADMIN-USER-02: Role moi phai duoc luu sau reload"
            )
        finally:
            delete_user_if_exists(driver, temp_user["email"])

    @pytest.mark.run(order=142)
    def test_disable_user_and_verify_subsequent_login_block(self, driver):
        temp_user = create_temp_user(prefix="disable")
        try:
            page = login_admin_and_open_users(driver)
            page.search_user(temp_user["email"])
            assert page.has_user_row(temp_user["email"], timeout=8), (
                "TC-ADMIN-USER-03: User test phai co trong trang quan ly user"
            )

            current_status = page.get_status_label_by_email(temp_user["email"])
            if current_status != "Bi khoa":
                _, after_status = page.toggle_available_by_email(temp_user["email"])
                assert after_status in ("Bi khoa", "Bị khóa"), (
                    "TC-ADMIN-USER-03: Disable account phai doi trang thai thanh Bi khoa"
                )

            clear_auth_state(driver)
            login_page = LoginPage(driver)
            login_page.login(temp_user["email"], temp_user["password"])

            WebDriverWait(driver, 10).until(lambda d: BASE_URL in d.current_url)

            assert "/login" in driver.current_url, (
                f"TC-ADMIN-USER-03: User bi khoa khong duoc login thanh cong, URL: {driver.current_url}"
            )
            assert login_page.is_notification_visible() or "/login" in driver.current_url, (
                "TC-ADMIN-USER-03: User bi khoa phai thay loi hoac bi giu o trang login"
            )
        finally:
            delete_user_if_exists(driver, temp_user["email"])

    @pytest.mark.run(order=143)
    @pytest.mark.parametrize("keyword", [SEARCH_KEYWORD_SPECIAL, SEARCH_KEYWORD_LONG])
    def test_search_users_with_special_characters_or_long_strings(self, driver, keyword):
        page = login_admin_and_open_users(driver)
        page.search_user(keyword)

        assert page.is_user_management_page(), (
            f"TC-ADMIN-USER-04: Search voi keyword dac biet khong duoc crash trang, URL: {driver.current_url}"
        )
        assert page.is_table_or_empty_visible(), (
            "TC-ADMIN-USER-04: Sau search phai con table hoac empty-state hien thi"
        )

        page_source = driver.page_source.lower()
        forbidden_patterns = [
            "syntax error at or near",
            "sqlstate",
            "traceback",
            "internal server error",
        ]
        for pattern in forbidden_patterns:
            assert pattern not in page_source, (
                f"TC-ADMIN-USER-04: Khong duoc lo loi he thong khi search ({pattern})"
            )
