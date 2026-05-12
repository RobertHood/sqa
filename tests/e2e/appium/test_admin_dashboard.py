# tests/test_admin_dashboard.py
# Kiem thu Admin Dashboard (mobile web qua Appium)

import json
import urllib.error
import urllib.request

import pytest

from pages.admin_dashboard_page import AdminDashboardPage
from config import ADMIN_BASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD


BACKEND_BASE_URL = "http://localhost:3000"


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
    payload: dict | None = None,
    timeout: int = 25,
):
    url = f"{BACKEND_BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    data = None

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


def get_admin_session() -> dict:
    status, data = api_request(
        "POST",
        "/auth/login",
        payload={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    if status != 200:
        raise RuntimeError(f"Khong lay duoc admin session, status={status}, response={data}")

    payload = data.get("data") or {}
    token = payload.get("token")
    user = payload.get("user") or {}
    permissions = payload.get("permissions") or []
    if not token:
        raise RuntimeError(f"Login response thieu token: {data}")

    return {"token": token, "user": user, "permissions": permissions}


def clear_auth_state(driver):
    try:
        driver.get(ADMIN_BASE_URL)
    except Exception:
        return

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


@pytest.fixture(scope="module", autouse=True)
def ensure_admin_logged_in(driver):
    """Dang nhap admin truoc khi chay test dashboard."""
    dashboard_page = AdminDashboardPage(driver)
    session = get_admin_session()

    clear_auth_state(driver)
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
    driver.get(dashboard_page.URL)
    dashboard_page.wait_until_loaded(timeout=20)

    if not dashboard_page.is_dashboard_page():
        error_msg = driver.current_url
        pytest.skip(f"Khong dang nhap duoc admin hoac khong vao dashboard: {error_msg}")


class TestAdminDashboard:
    """Cac testcase chinh cho Admin Dashboard."""

    @pytest.mark.run(order=130)
    def test_overview_dashboard_data_loading_after_admin_login(self, driver):
        page = AdminDashboardPage(driver)
        page.open_dashboard()
        page.wait_until_loaded(timeout=20)

        assert page.is_dashboard_page(), (
            f"TC-ADMIN-DB-01: Sau login phai o /admin/dashboard, URL: {driver.current_url}"
        )
        assert not page.is_visible(AdminDashboardPage.LOADING_TEXT, timeout=2), (
            "TC-ADMIN-DB-01: Dashboard khong duoc ket o trang thai loading"
        )
        assert page.has_required_sections(), (
            "TC-ADMIN-DB-01: Dashboard phai hien thi du cac section chinh"
        )
        assert page.has_required_kpi_cards(), (
            "TC-ADMIN-DB-01: Dashboard phai hien thi du KPI card o phan Tong quan"
        )

        values = page.get_kpi_values()
        assert len(values) >= 6, (
            f"TC-ADMIN-DB-01: Can it nhat 6 KPI values, hien co: {len(values)}"
        )

    @pytest.mark.run(order=131)
    def test_dashboard_chart_blocks_render_data_or_empty_state(self, driver):
        page = AdminDashboardPage(driver)
        page.open_dashboard()
        page.wait_until_loaded(timeout=20)

        assert page.has_required_sections(), (
            "TC-ADMIN-DB-02: Dashboard phai co day du cac section chart va table"
        )
        assert page.chart_and_table_blocks_have_valid_content_state(), (
            "TC-ADMIN-DB-02: Moi khoi line/bar/pie/table phai render chart-bang "
            "hoac empty-state hop le"
        )

    @pytest.mark.run(order=133)
    def test_dashboard_responsive_layout_and_scrolling_on_mobile_devices(self, driver):
        page = AdminDashboardPage(driver)
        page.open_dashboard()
        page.wait_until_loaded(timeout=20)

        metrics_before = page.get_viewport_metrics()
        viewport_width = metrics_before.get("innerWidth", 0)
        if viewport_width > 900:
            pytest.xfail(
                f"TC-ADMIN-DB-04: Viewport hien tai khong phai mobile (width={viewport_width})"
            )

        assert metrics_before.get("scrollHeight", 0) >= metrics_before.get("innerHeight", 0), (
            "TC-ADMIN-DB-04: Dashboard phai co chieu cao noi dung hop le"
        )

        if metrics_before.get("scrollHeight", 0) <= metrics_before.get("innerHeight", 0) + 20:
            pytest.skip("TC-ADMIN-DB-04: Noi dung chua du dai de kiem tra scrolling")

        page.scroll_to_bottom()
        metrics_after = page.get_viewport_metrics()

        assert metrics_after.get("scrollY", 0) > metrics_before.get("scrollY", 0), (
            "TC-ADMIN-DB-04: Sau thao tac scroll, vi tri cuon phai thay doi"
        )
        assert page.is_visible(AdminDashboardPage.TITLE_TABLE, timeout=8), (
            "TC-ADMIN-DB-04: Scroll xuong phai xem duoc section cuoi (Thong ke theo ngay)"
        )
        assert metrics_after.get("scrollWidth", 0) <= metrics_after.get("innerWidth", 0) + 24, (
            "TC-ADMIN-DB-04: Khong duoc vo layout gay tran ngang tren mobile"
        )
