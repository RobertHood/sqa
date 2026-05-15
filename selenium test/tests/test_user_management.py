import pytest

from pages.auth_pages import AdminLoginPage
from pages.config import ADMIN_BASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD
from pages.user_management_page import UserManagementPage


@pytest.fixture
def admin_users(driver):
    AdminLoginPage(driver).login(ADMIN_EMAIL, ADMIN_PASSWORD)
    page = UserManagementPage(driver)
    page.open_users()
    return page


@pytest.mark.user_management
def test_user_management_01_user_table_loads(admin_users):
    # Source: System UM-ADLIST-01.
    # Purpose: Verify the admin user-management table loads after admin login.
    page = admin_users

    assert page.wait_visible(page.TABLE).is_displayed()


@pytest.mark.user_management
def test_user_management_02_search_filter_accepts_query(admin_users):
    # Source: System UM-ADLIST-11.
    # Purpose: Verify the search filter can be applied without breaking the user table.
    page = admin_users

    page.search("admin")

    assert page.wait_visible(page.SEARCH_INPUT).get_attribute("value") == "admin"
    assert page.wait_visible(page.TABLE).is_displayed()


@pytest.mark.user_management
def test_user_management_03_reset_filter_clears_search(admin_users):
    # Source: System UM-ADLIST-15.
    # Purpose: Verify resetting filters clears the search box.
    page = admin_users

    page.search("admin")
    page.reset_filters()

    assert page.wait_visible(page.SEARCH_INPUT).get_attribute("value") == ""


@pytest.mark.user_management
def test_user_management_04_status_filter_can_be_applied(admin_users):
    # Source: System UM-ADLIST-13.
    # Purpose: Verify the status filter can be changed and applied.
    page = admin_users

    page.select_status("true")

    assert page.wait_visible(page.TABLE).is_displayed()


@pytest.mark.user_management
def test_user_management_05_delete_confirmation_can_be_cancelled(admin_users):
    # Source: System UM-ACT-06.
    # Purpose: Verify the delete action shows a confirmation and can be cancelled safely.
    page = admin_users
    before = page.row_count()

    clicked = page.cancel_first_delete_confirmation()

    if not clicked:
        pytest.skip("No user rows with delete buttons are available.")
    assert page.row_count() == before


@pytest.mark.user_management
def test_user_management_acb_01_admin_users_requires_authentication(driver):
    # Source: System UM-ADLIST-17.
    # Purpose: Verify the admin users page is protected when no admin token is present.
    driver.get(f"{ADMIN_BASE_URL}/admin/users")

    page = UserManagementPage(driver)
    page.wait_until(lambda d: "/admin/login" in d.current_url or "/admin/users" not in d.current_url, 10)

    assert "/admin/login" in driver.current_url


@pytest.mark.user_management
def test_user_management_acb_02_special_character_search_does_not_crash(admin_users):
    # Source: Additional Selenium case outside the provided system/unit files.
    # Purpose: Verify special-character search input does not expose server errors or break the table.
    page = admin_users

    page.search("' OR 1=1 -- <script>alert(1)</script>")

    source = page.driver.page_source.lower()
    assert page.wait_visible(page.TABLE).is_displayed()
    assert "internal server error" not in source
    assert "syntax error" not in source


@pytest.mark.user_management
def test_user_management_acb_03_role_filter_can_be_applied(admin_users):
    # Source: System UM-ADLIST-12.
    # Purpose: Verify the role filter can be changed and applied without breaking the page.
    page = admin_users

    page.select_role("1")

    assert page.wait_visible(page.TABLE).is_displayed()


@pytest.mark.user_management
def test_user_management_um_adlist_01_header_title_is_visible(admin_users):
    # Source: System UM-ADLIST-01.
    # Purpose: Verify the admin user-management page title is rendered.
    page = admin_users

    assert page.title_text().strip()
    assert "NG" in page.title_text().upper()


@pytest.mark.user_management
def test_user_management_um_adlist_02_table_headers_are_complete(admin_users):
    # Source: System UM-ADLIST-02.
    # Purpose: Verify the user table exposes the expected semantic columns.
    page = admin_users
    headers = page.table_headers()

    assert headers[0] == "STT"
    assert "Email" in headers
    assert len(headers) == 8


@pytest.mark.user_management
def test_user_management_um_adlist_04_role_and_status_filter_options(admin_users):
    # Source: System UM-ADLIST-04 / UM-ADLIST-13.
    # Purpose: Verify role and status filters expose all expected option groups.
    page = admin_users

    assert len(page.role_filter_options()) == 3
    assert len(page.status_filter_options()) == 3


@pytest.mark.user_management
def test_user_management_um_adlist_08_empty_search_renders_empty_state(admin_users):
    # Source: System UM-ADLIST-08.
    # Purpose: Verify a search with no matching users renders an empty table state.
    page = admin_users

    page.search("selenium-no-user-zzzz")

    assert not page.data_rows()
    assert page.empty_message_text()


@pytest.mark.user_management
def test_user_management_um_adlist_14_compound_filter_returns_matching_rows(admin_users):
    # Source: System UM-ADLIST-14.
    # Purpose: Verify search, role, and status filters can be applied together.
    page = admin_users

    page.apply_compound_filter("admin", "2", "true")
    rows = page.data_rows()

    assert rows
    assert all("Admin" in row["role"] for row in rows)


@pytest.mark.user_management
def test_user_management_um_act_07_admin_rows_have_no_mutation_controls(admin_users):
    # Source: System UM-ACT-07.
    # Purpose: Verify admin rows do not expose edit or delete controls that can alter admin integrity.
    page = admin_users

    page.search(ADMIN_EMAIL)
    admin_rows = [row for row in page.data_rows() if "Admin" in row["role"]]

    if not admin_rows:
        pytest.skip("No admin row is visible for the configured admin account.")

    assert all(row["editIconCount"] == 0 and row["buttonCount"] == 0 for row in admin_rows), admin_rows
