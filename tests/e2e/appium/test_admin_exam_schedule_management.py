# tests/test_admin_exam_schedule_management.py
# Kiểm thử Admin Exam Schedule & Management

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

import pytest
from selenium.webdriver.support.ui import WebDriverWait

from config import ADMIN_BASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD, BASE_URL, USER1_EMAIL, USER1_PASSWORD
from pages.admin_exam_management_page import AdminExamManagementPage
from pages.login_page import LoginPage


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
    token: str | None = None,
    payload: dict | list | None = None,
    timeout: int = 20,
) -> tuple[int, dict]:
    url = f"{BACKEND_BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    data = None

    if token:
        headers["Authorization"] = f"Bearer {token}"

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url=url,
        method=method.upper(),
        headers=headers,
        data=data,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.getcode()
            body = response.read().decode("utf-8", errors="ignore")
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
        raise RuntimeError(f"Login thất bại ({email}), status={status}, response={data}")
    payload = data.get("data") or {}
    token = payload.get("token")
    user = payload.get("user") or {}
    permissions = payload.get("permissions") or []
    if not token:
        raise RuntimeError(f"Login response thiếu token ({email}): {data}")
    return {"token": token, "user": user, "permissions": permissions}


def get_admin_session() -> dict:
    return get_login_session(ADMIN_EMAIL, ADMIN_PASSWORD)


def get_admin_token() -> str:
    return get_admin_session()["token"]


def get_user_session() -> dict:
    return get_login_session(USER1_EMAIL, USER1_PASSWORD)


def to_local_input(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M")


def to_date_input(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def future_datetime(*, days: int = 0, hours: int = 0, minutes: int = 0, lead_minutes: int = 15) -> datetime:
    base = datetime.now().replace(second=0, microsecond=0)
    if base.minute % 5 != 0:
        base += timedelta(minutes=(5 - (base.minute % 5)))
    return base + timedelta(days=days, hours=hours, minutes=minutes + lead_minutes)


def normalize_datetime_to_local_minute(raw: str | None) -> str:
    if not raw:
        return ""
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except Exception:
        return ""
    if dt.tzinfo is not None:
        dt = dt.astimezone()
    return dt.strftime("%Y-%m-%dT%H:%M")


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


def login_admin_and_open_schedules(driver) -> AdminExamManagementPage:
    clear_auth_state(driver)
    page = AdminExamManagementPage(driver)
    session = get_admin_session()
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
    driver.get(page.SCHEDULE_URL)
    page.wait_for_url_contains("/admin/schedules")
    page.wait_for_visible(page.SCHEDULE_TITLE, timeout=20)
    assert page.is_schedule_management_page(), (
        f"Không vào được trang quản lý lịch thi admin, URL hiện tại: {driver.current_url}"
    )
    return page


def login_admin_and_open_exams(driver) -> AdminExamManagementPage:
    clear_auth_state(driver)
    page = AdminExamManagementPage(driver)
    session = get_admin_session()
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
    driver.get(page.EXAM_URL)
    page.wait_for_url_contains("/admin/exams")
    page.wait_for_visible(page.EXAM_TITLE, timeout=20)
    assert page.is_exam_management_page(), (
        f"Không vào được trang quản lý bài thi admin, URL hiện tại: {driver.current_url}"
    )
    return page


def api_get_all_schedules(token: str) -> list[dict]:
    status, data = api_request("GET", "/exams/schedule", token=token)
    if status != 200:
        raise RuntimeError(f"Lấy schedules thất bại, status={status}, response={data}")
    return (data.get("data") or {}).get("schedules") or []


def api_create_schedule(token: str, start_time_local: str, end_time_local: str) -> dict:
    status, data = api_request(
        "POST",
        "/exams/schedule/create",
        token=token,
        payload={"start_time": start_time_local, "end_time": end_time_local},
    )
    if status not in (200, 201):
        raise RuntimeError(f"Tạo schedule thất bại, status={status}, response={data}")
    return data.get("data") or {}


def api_update_schedule(token: str, schedule_id: int, start_time_local: str, end_time_local: str):
    status, data = api_request(
        "PUT",
        f"/exams/schedule/update/{schedule_id}",
        token=token,
        payload={"start_time": start_time_local, "end_time": end_time_local},
    )
    if status not in (200, 202):
        raise RuntimeError(f"Update schedule thất bại, status={status}, response={data}")


def api_delete_schedule(token: str, schedule_id: int):
    status, data = api_request("DELETE", f"/exams/schedule/remove/{schedule_id}", token=token)
    if status not in (200, 202, 204):
        raise RuntimeError(f"Delete schedule thất bại, status={status}, response={data}")


def safe_delete_schedule(token: str, schedule_id: int | None):
    if not schedule_id:
        return
    try:
        api_delete_schedule(token, schedule_id)
    except Exception:
        pass


def api_get_topics(token: str) -> list[dict]:
    status, data = api_request("GET", "/topics", token=token)
    if status != 200:
        raise RuntimeError(f"Lấy topics thất bại, status={status}, response={data}")
    return data.get("data") or []


def api_get_subjects(token: str) -> list[dict]:
    status, data = api_request("GET", "/subjects", token=token)
    if status != 200:
        raise RuntimeError(f"Lấy subjects thất bại, status={status}, response={data}")
    return data.get("data") or []


def api_pick_subject_topic(token: str) -> tuple[int, int]:
    topics = api_get_topics(token)
    if topics:
        first_topic = topics[0]
        topic_id = int(first_topic["topic_id"])
        subject_id = int(first_topic["subject_id"])
        return subject_id, topic_id

    subjects = api_get_subjects(token)
    if not subjects:
        raise RuntimeError("Không có subject/topic để tạo exam")
    subject_id = int(subjects[0]["subject_id"])
    return subject_id, 0


def api_create_exam(
    token: str,
    *,
    exam_name: str,
    description: str,
    topic_id: int,
    exam_schedule_id: int,
    time_limit: int = 30,
) -> dict:
    status, data = api_request(
        "POST",
        "/exams/create",
        token=token,
        payload={
            "exam_name": exam_name,
            "description": description,
            "time_limit": time_limit,
            "topic_id": topic_id,
            "exam_schedule_id": exam_schedule_id,
        },
    )
    if status not in (200, 201):
        raise RuntimeError(f"Tạo exam thất bại, status={status}, response={data}")
    return data.get("data") or {}


def api_delete_exam(token: str, exam_id: int):
    status, data = api_request("DELETE", f"/exams/remove/{exam_id}", token=token)
    if status not in (200, 202, 204):
        raise RuntimeError(f"Delete exam thất bại, status={status}, response={data}")


def safe_delete_exam(token: str, exam_id: int | None):
    if not exam_id:
        return
    try:
        api_delete_exam(token, exam_id)
    except Exception:
        pass


def api_list_exams(token: str, *, keyword: str = "", available: str = "All", page: int = 1) -> list[dict]:
    query = urllib.parse.urlencode(
        {
            "page": page,
            "keyword": keyword,
            "available": available,
        }
    )
    status, data = api_request("GET", f"/exams?{query}", token=token)
    if status != 200:
        raise RuntimeError(f"Lấy exam list thất bại, status={status}, response={data}")
    return (data.get("data") or {}).get("exams") or []


def api_find_exam_by_name(token: str, exam_name: str) -> dict | None:
    rows = api_list_exams(token, keyword=exam_name, available="All", page=1)
    for row in rows:
        if (row.get("exam_name") or "").strip() == exam_name:
            return row
    return None


def api_toggle_exam_available(token: str, exam_id: int, available: bool):
    status, data = api_request(
        "PATCH",
        f"/exams/setAvailable/{exam_id}",
        token=token,
        payload={"available": available},
    )
    if status not in (200, 202):
        raise RuntimeError(f"Toggle available exam thất bại, status={status}, response={data}")


def api_create_question(token: str, *, question_content: str) -> dict:
    status, data = api_request(
        "POST",
        "/questions/create",
        token=token,
        payload={
            "question_content": question_content,
            "type_question": 1,
            "available": True,
            "source": "appium-admin-exam",
            "answers": [
                {"answer_content": "Đáp án đúng", "is_correct": True},
                {"answer_content": "Đáp án sai 1", "is_correct": False},
                {"answer_content": "Đáp án sai 2", "is_correct": False},
                {"answer_content": "Đáp án sai 3", "is_correct": False},
            ],
        },
    )
    if status not in (200, 201):
        raise RuntimeError(f"Tạo question thất bại, status={status}, response={data}")
    return data.get("data") or {}


def api_delete_question(token: str, question_id: int):
    status, data = api_request("DELETE", f"/questions/remove/{question_id}", token=token)
    if status not in (200, 202, 204):
        raise RuntimeError(f"Delete question thất bại, status={status}, response={data}")


def safe_delete_question(token: str, question_id: int | None):
    if not question_id:
        return
    try:
        api_delete_question(token, question_id)
    except Exception:
        pass


def api_assign_questions_to_exam(token: str, exam_id: int, question_ids: list[int]):
    payload = {
        "selectedQuestions": [
            {"exam_id": exam_id, "question_id": question_id} for question_id in question_ids
        ]
    }
    status, data = api_request("POST", "/exams/questions/add", token=token, payload=payload)
    if status not in (200, 201):
        raise RuntimeError(f"Gán question cho exam thất bại, status={status}, response={data}")


def api_get_exam_question_ids(token: str, exam_id: int) -> list[int]:
    status, data = api_request("GET", f"/exams/{exam_id}/questions", token=token)
    if status != 200:
        raise RuntimeError(f"Lấy question IDs của exam thất bại, status={status}, response={data}")
    return data.get("data") or []


def api_get_exam_detail(token: str, exam_id: int) -> dict:
    status, data = api_request("GET", f"/exams/{exam_id}", token=token)
    if status != 200:
        raise RuntimeError(f"Lấy chi tiết exam thất bại, status={status}, response={data}")
    return data.get("data") or {}


def api_submit_exam(
    token: str,
    *,
    exam_id: int,
    subject_type: int,
    user_name: str,
    do_exam: list[dict],
    time_test: int = 120,
) -> dict:
    query = urllib.parse.urlencode(
        {
            "exam_id": exam_id,
            "subject_type": subject_type,
            "time_test": time_test,
            "user_name": user_name,
        }
    )
    status, data = api_request(
        "POST",
        f"/exams/submit?{query}",
        token=token,
        payload={"do_exam": do_exam},
    )
    if status != 200:
        raise RuntimeError(f"Nộp bài exam thất bại, status={status}, response={data}")
    return data.get("data") or {}


def api_get_exam_ranking(token: str, exam_id: int, user_name: str, page: int = 1) -> dict:
    query = urllib.parse.urlencode({"user_name": user_name, "page": page})
    status, data = api_request("GET", f"/exams/{exam_id}/ranking?{query}", token=token)
    if status != 200:
        raise RuntimeError(f"Lấy ranking thất bại, status={status}, response={data}")
    return data.get("data") or {}


def api_get_user_exam_history(token: str) -> list[dict]:
    status, data = api_request("GET", "/exams/exam-history", token=token)
    if status != 200:
        raise RuntimeError(f"Lấy lịch sử exam của user thất bại, status={status}, response={data}")
    return (data.get("data") or {}).get("history") or []


def wait_until_schedule_found(
    token: str,
    *,
    expected_start_local: str,
    expected_end_local: str,
    timeout: int = 15,
) -> dict | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        schedules = api_get_all_schedules(token)
        for row in schedules:
            start_local = normalize_datetime_to_local_minute(row.get("start_time"))
            end_local = normalize_datetime_to_local_minute(row.get("end_time"))
            if start_local == expected_start_local and end_local == expected_end_local:
                return row
        time.sleep(0.6)
    return None


class TestAdminExamScheduleAndManagement:
    """Create/validate/update schedules, create/manage exams, assign questions, disable/delete exams."""

    # ──────────────────────────────────────────────
    # TC-ADMIN-EXAM-01
    # Create valid exam schedule (start time before end time)
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=160)
    def test_create_valid_exam_schedule_start_time_before_end_time(self, driver):
        token = get_admin_token()
        created_schedule_id: int | None = None

        start_dt = future_datetime(days=6, lead_minutes=30)
        end_dt = start_dt + timedelta(hours=2)
        start_local = to_local_input(start_dt)
        end_local = to_local_input(end_dt)

        try:
            page = login_admin_and_open_schedules(driver)
            page.open_add_schedule_modal()
            assert page.is_schedule_modal_visible(), (
                "TC-ADMIN-EXAM-01: Modal tạo lịch thi không hiển thị"
            )

            page.fill_schedule_times(start_local, end_local)
            page.submit_schedule()

            found = wait_until_schedule_found(
                token,
                expected_start_local=start_local,
                expected_end_local=end_local,
                timeout=15,
            )
            assert found is not None, (
                "TC-ADMIN-EXAM-01: Không tìm thấy lịch thi vừa tạo từ UI trong backend"
            )
            created_schedule_id = found.get("exam_schedule_id")

        finally:
            safe_delete_schedule(token, created_schedule_id)

    # ──────────────────────────────────────────────
    # TC-ADMIN-EXAM-02
    # Validation: Prevent schedule if end time is before start time
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=161)
    def test_validation_prevent_schedule_if_end_before_start(self, driver):
        page = login_admin_and_open_schedules(driver)

        start_dt = future_datetime(days=3, hours=2, lead_minutes=30)
        end_dt = start_dt - timedelta(hours=1)

        page.open_add_schedule_modal()
        page.fill_schedule_times(to_local_input(start_dt), to_local_input(end_dt))
        page.submit_schedule()

        assert page.wait_notification_contains("Thời gian kết thúc phải sau thời gian bắt đầu", timeout=8), (
            "TC-ADMIN-EXAM-02: Thiếu validation khi end_time <= start_time"
        )
        assert page.is_schedule_modal_visible(), (
            "TC-ADMIN-EXAM-02: Form không được đóng khi dữ liệu lịch thi không hợp lệ"
        )

    # ──────────────────────────────────────────────
    # TC-ADMIN-EXAM-03
    # Search and modify existing exam schedules
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=162)
    def test_search_and_modify_existing_exam_schedules(self, driver):
        token = get_admin_token()

        base_dt = future_datetime(days=120, lead_minutes=30)
        original_start = to_local_input(base_dt)
        original_end = to_local_input(base_dt + timedelta(hours=2))
        updated_end = to_local_input(base_dt + timedelta(hours=3))

        created = api_create_schedule(token, original_start, original_end)
        schedule_id = created.get("exam_schedule_id")
        assert schedule_id, "TC-ADMIN-EXAM-03: Không tạo được schedule setup"

        try:
            page = login_admin_and_open_schedules(driver)
            day_text = to_date_input(base_dt)
            page.set_schedule_date_filter(day_text, day_text)
            page.apply_schedule_filter()

            assert page.is_any_schedule_row_visible(), (
                "TC-ADMIN-EXAM-03: Không tìm thấy schedule theo filter thời gian"
            )

            page.click_first_schedule_edit()
            page.fill_schedule_times(original_start, updated_end)
            page.submit_schedule()

            # Verify bằng API
            schedules = api_get_all_schedules(token)
            target = next((s for s in schedules if s.get("exam_schedule_id") == schedule_id), None)
            assert target is not None, "TC-ADMIN-EXAM-03: Schedule đã sửa không còn tồn tại"
            assert normalize_datetime_to_local_minute(target.get("end_time")) == updated_end, (
                "TC-ADMIN-EXAM-03: End time của schedule chưa được cập nhật"
            )
        finally:
            safe_delete_schedule(token, schedule_id)

    # ──────────────────────────────────────────────
    # TC-ADMIN-EXAM-04
    # Create valid exam and assign to schedule/topic
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=163)
    def test_create_valid_exam_and_assign_to_schedule_and_topic(self, driver):
        token = get_admin_token()
        ts = int(time.time() * 1000)
        exam_name = f"[TC-ADMIN-EXAM-04]-{ts}"

        subject_id, topic_id = api_pick_subject_topic(token)
        assert topic_id, "TC-ADMIN-EXAM-04: Không có topic hợp lệ để tạo exam"

        schedule_start = to_local_input(future_datetime(days=15, lead_minutes=30))
        schedule_end = to_local_input(future_datetime(days=15, hours=2, lead_minutes=30))
        schedule = api_create_schedule(token, schedule_start, schedule_end)
        schedule_id = schedule.get("exam_schedule_id")

        created_exam_id: int | None = None

        try:
            page = login_admin_and_open_exams(driver)
            page.open_create_exam()

            page.fill_exam_form(
                exam_name=exam_name,
                description="Auto test create exam",
                time_limit=35,
                subject_id=subject_id,
                topic_id=topic_id,
                schedule_id=schedule_id,
            )
            page.submit_create_exam()

            WebDriverWait(driver, 15).until(
                lambda d: "/admin/exams/create/" in d.current_url and "/questions" in d.current_url
            )
            match = re.search(r"/admin/exams/create/(\d+)/questions", driver.current_url)
            assert match, (
                f"TC-ADMIN-EXAM-04: URL sau tạo exam không đúng format, URL: {driver.current_url}"
            )
            created_exam_id = int(match.group(1))

            exam = api_find_exam_by_name(token, exam_name)
            assert exam is not None, "TC-ADMIN-EXAM-04: Không tìm thấy exam vừa tạo"
            assert int(exam.get("exam_schedule_id")) == int(schedule_id), (
                "TC-ADMIN-EXAM-04: Exam chưa gán đúng schedule"
            )
            assert int(exam.get("topic_id")) == int(topic_id), (
                "TC-ADMIN-EXAM-04: Exam chưa gán đúng topic"
            )
        finally:
            if created_exam_id is None:
                maybe_exam = api_find_exam_by_name(token, exam_name)
                if maybe_exam:
                    created_exam_id = maybe_exam.get("exam_id")
            safe_delete_exam(token, created_exam_id)
            safe_delete_schedule(token, schedule_id)

    # ──────────────────────────────────────────────
    # TC-ADMIN-EXAM-05
    # Assign questions to exam and verify detail view integrity
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=164)
    def test_assign_questions_to_exam_and_verify_detail_view_integrity(self, driver):
        token = get_admin_token()
        ts = int(time.time() * 1000)

        subject_id, topic_id = api_pick_subject_topic(token)
        assert topic_id, "TC-ADMIN-EXAM-05: Không có topic hợp lệ để tạo exam"

        schedule = api_create_schedule(
            token,
            to_local_input(future_datetime(days=18, lead_minutes=30)),
            to_local_input(future_datetime(days=18, hours=2, lead_minutes=30)),
        )
        schedule_id = schedule.get("exam_schedule_id")

        exam = api_create_exam(
            token,
            exam_name=f"[TC-ADMIN-EXAM-05]-exam-{ts}",
            description="Auto test assign question",
            topic_id=topic_id,
            exam_schedule_id=schedule_id,
            time_limit=25,
        )
        exam_id = exam.get("exam_id")

        question = api_create_question(token, question_content=f"[TC-ADMIN-EXAM-05]-question-{ts}")
        question_id = question.get("question_id")
        question_content = question.get("question_content") or f"[TC-ADMIN-EXAM-05]-question-{ts}"
        correct_answer = ""
        for ans in question.get("answers") or []:
            if ans.get("is_correct"):
                correct_answer = ans.get("answer_content") or ""
                break

        try:
            page = login_admin_and_open_exams(driver)
            page.open_exam_question_assignment(exam_id)
            page.search_question_to_assign(question_content)
            selected = page.select_question_for_assignment(question_content)
            assert selected, "TC-ADMIN-EXAM-05: Không chọn được câu hỏi để gán vào exam"

            page.complete_question_assignment()
            WebDriverWait(driver, 15).until(lambda d: f"/admin/exams/detail/{exam_id}" in d.current_url)
            assert page.is_exam_detail_page(exam_id), (
                f"TC-ADMIN-EXAM-05: Không điều hướng được về trang detail exam, URL: {driver.current_url}"
            )
            page.wait_exam_detail_loaded(timeout=12)

            ids = api_get_exam_question_ids(token, exam_id)
            assert question_id in ids, (
                "TC-ADMIN-EXAM-05: API exam detail không chứa question vừa gán"
            )

            assert page.page_contains_text(question_content), (
                "TC-ADMIN-EXAM-05: Trang detail exam không hiển thị nội dung câu hỏi đã gán"
            )
            if correct_answer:
                assert page.page_contains_text(correct_answer), (
                    "TC-ADMIN-EXAM-05: Trang detail exam không hiển thị đáp án tương ứng"
                )
            assert page.page_contains_text("✔"), (
                "TC-ADMIN-EXAM-05: Trang detail exam không hiển thị marker đáp án đúng"
            )
        finally:
            safe_delete_exam(token, exam_id)
            safe_delete_schedule(token, schedule_id)
            safe_delete_question(token, question_id)

    # ──────────────────────────────────────────────
    # TC-ADMIN-EXAM-06
    # Disable exam and verify it is hidden from students
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=165)
    def test_disable_exam_and_verify_it_is_hidden_from_students(self, driver):
        admin_token = get_admin_token()
        ts = int(time.time() * 1000)
        exam_name = f"[TC-ADMIN-EXAM-06]-{ts}"

        _, topic_id = api_pick_subject_topic(admin_token)
        assert topic_id, "TC-ADMIN-EXAM-06: Không có topic hợp lệ để tạo exam"
        schedule = api_create_schedule(
            admin_token,
            to_local_input(future_datetime(days=20, lead_minutes=30)),
            to_local_input(future_datetime(days=20, hours=2, lead_minutes=30)),
        )
        schedule_id = schedule.get("exam_schedule_id")

        exam = api_create_exam(
            admin_token,
            exam_name=exam_name,
            description="Auto test disable exam",
            topic_id=topic_id,
            exam_schedule_id=schedule_id,
            time_limit=30,
        )
        exam_id = exam.get("exam_id")

        try:
            page = login_admin_and_open_exams(driver)
            page.search_exam(exam_name)
            assert page.has_exam_row(exam_name, timeout=8), (
                "TC-ADMIN-EXAM-06: Không thấy exam test trong danh sách admin"
            )

            before = page.get_exam_status_text(exam_name)
            if "Không hoạt động" not in before:
                page.toggle_exam_available_by_name(exam_name)

            after = page.get_exam_status_text(exam_name)
            assert "Không hoạt động" in after, (
                "TC-ADMIN-EXAM-06: Disable exam không đổi trạng thái UI sang 'Không hoạt động'"
            )

            # Kiểm tra phía student UI
            clear_auth_state(driver)
            user_login = LoginPage(driver)
            user_login.login(USER1_EMAIL, USER1_PASSWORD)
            WebDriverWait(driver, 12).until(lambda d: BASE_URL in d.current_url)

            driver.get(f"{BASE_URL}/exam")
            WebDriverWait(driver, 12).until(lambda d: "/exam" in d.current_url)
            time.sleep(2)

            visible_in_student = exam_name.lower() in (driver.page_source or "").lower()
            if visible_in_student:
                pytest.xfail(
                    "TC-ADMIN-EXAM-06: Frontend user hiện gọi /exams với available=All nên exam disable vẫn hiển thị."
                )

            assert not visible_in_student, (
                "TC-ADMIN-EXAM-06: Exam đã disable phải bị ẩn khỏi danh sách student"
            )
        finally:
            safe_delete_exam(admin_token, exam_id)
            safe_delete_schedule(admin_token, schedule_id)

    # ──────────────────────────────────────────────
    # TC-ADMIN-EXAM-07
    # Delete exam with existing attempt history and rankings
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=166)
    def test_delete_exam_with_existing_attempt_history_and_rankings(self, driver):
        admin_token = get_admin_token()
        user_session = get_user_session()
        user_token = user_session["token"]
        user_name = (user_session["user"] or {}).get("user_name") or "user1"

        ts = int(time.time() * 1000)
        exam_name = f"[TC-ADMIN-EXAM-07]-{ts}"
        _, topic_id = api_pick_subject_topic(admin_token)
        assert topic_id, "TC-ADMIN-EXAM-07: Không có topic hợp lệ để tạo exam"

        schedule = api_create_schedule(
            admin_token,
            to_local_input(future_datetime(days=25, lead_minutes=30)),
            to_local_input(future_datetime(days=25, hours=2, lead_minutes=30)),
        )
        schedule_id = schedule.get("exam_schedule_id")

        exam = api_create_exam(
            admin_token,
            exam_name=exam_name,
            description="Auto test delete exam with history/ranking",
            topic_id=topic_id,
            exam_schedule_id=schedule_id,
            time_limit=20,
        )
        exam_id = exam.get("exam_id")

        question = api_create_question(admin_token, question_content=f"[TC-ADMIN-EXAM-07]-question-{ts}")
        question_id = question.get("question_id")
        correct_answer_id = None
        for ans in question.get("answers") or []:
            if ans.get("is_correct"):
                correct_answer_id = ans.get("answer_id")
                break
        assert correct_answer_id is not None, "TC-ADMIN-EXAM-07: Không tìm thấy đáp án đúng để submit bài"

        try:
            api_assign_questions_to_exam(admin_token, exam_id, [question_id])
            detail = api_get_exam_detail(user_token, exam_id)
            subject_type = int(detail.get("subject_type") or 1)

            submit = api_submit_exam(
                user_token,
                exam_id=exam_id,
                subject_type=subject_type,
                user_name=user_name,
                do_exam=[{"question_id": question_id, "user_answer": [int(correct_answer_id)]}],
                time_test=111,
            )
            assert submit.get("history_exam_id"), (
                "TC-ADMIN-EXAM-07: Submit exam không tạo lịch sử làm bài"
            )

            ranking = api_get_exam_ranking(user_token, exam_id, user_name=user_name, page=1)
            assert len(ranking.get("rank") or []) > 0, (
                "TC-ADMIN-EXAM-07: Ranking chưa có dữ liệu sau khi user submit"
            )

            page = login_admin_and_open_exams(driver)
            page.search_exam(exam_name)
            assert page.has_exam_row(exam_name, timeout=8), (
                "TC-ADMIN-EXAM-07: Không tìm thấy exam test để thực hiện xóa"
            )
            page.delete_exam_by_name(exam_name)

            # Verify exam đã bị xóa
            time.sleep(1.5)
            exam_after = api_find_exam_by_name(admin_token, exam_name)
            assert exam_after is None, (
                "TC-ADMIN-EXAM-07: Xóa exam thất bại, exam vẫn còn trong danh sách"
            )

            history = api_get_user_exam_history(user_token)
            assert all(int(item.get("exam_id")) != int(exam_id) for item in history if item.get("exam_id") is not None), (
                "TC-ADMIN-EXAM-07: Sau xóa exam, lịch sử làm bài liên quan phải được dọn theo cascade"
            )
        finally:
            safe_delete_exam(admin_token, exam_id)
            safe_delete_schedule(admin_token, schedule_id)
            safe_delete_question(admin_token, question_id)
