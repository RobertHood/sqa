# tests/test_admin_subject_topic_practice_management.py
# Kiểm thử Subject, Topic & Practice (Bank) Management

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

import pytest
from selenium.webdriver.support.ui import WebDriverWait

from config import ADMIN_BASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD, USER1_EMAIL, USER1_PASSWORD
from pages.admin_subject_topic_practice_page import AdminSubjectTopicPracticePage


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

    request = urllib.request.Request(url=url, method=method.upper(), headers=headers, data=data)
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


def api_list_subjects(token: str) -> list[dict]:
    status, data = api_request("GET", "/subjects", token=token)
    if status != 200:
        raise RuntimeError(f"Lấy subjects thất bại, status={status}, response={data}")
    return data.get("data") or []


def api_create_subject(token: str, name: str, subject_type: int = 1) -> dict:
    status, data = api_request(
        "POST",
        "/subjects/create",
        token=token,
        payload={"subject_name": name, "subject_type": subject_type},
    )
    if status not in (200, 201):
        raise RuntimeError(f"Tạo subject thất bại, status={status}, response={data}")
    return data.get("data") or {}


def api_set_subject_available(token: str, subject_id: int, available: bool):
    status, data = api_request(
        "PATCH",
        f"/subjects/setAvailable/{subject_id}",
        token=token,
        payload={"available": available},
    )
    if status not in (200, 202):
        raise RuntimeError(f"Disable subject thất bại, status={status}, response={data}")


def api_delete_subject(token: str, subject_id: int):
    status, data = api_request("DELETE", f"/subjects/remove/{subject_id}", token=token)
    if status not in (200, 202, 204):
        raise RuntimeError(f"Delete subject thất bại, status={status}, response={data}")


def safe_delete_subject(token: str, subject_id: int | None):
    if not subject_id:
        return
    try:
        api_delete_subject(token, subject_id)
    except Exception:
        pass


def api_list_topics(token: str) -> list[dict]:
    status, data = api_request("GET", "/topics", token=token)
    if status != 200:
        raise RuntimeError(f"Lấy topics thất bại, status={status}, response={data}")
    return data.get("data") or []


def api_create_topic(token: str, title: str, description: str, subject_id: int) -> dict:
    status, data = api_request(
        "POST",
        "/topics/create",
        token=token,
        payload={"title": title, "description": description, "subject_id": subject_id},
    )
    if status not in (200, 201):
        raise RuntimeError(f"Tạo topic thất bại, status={status}, response={data}")
    return data.get("data") or {}


def api_delete_topic(token: str, topic_id: int):
    status, data = api_request("DELETE", f"/topics/remove/{topic_id}", token=token)
    if status not in (200, 202, 204):
        raise RuntimeError(f"Delete topic thất bại, status={status}, response={data}")


def safe_delete_topic(token: str, topic_id: int | None):
    if not topic_id:
        return
    try:
        api_delete_topic(token, topic_id)
    except Exception:
        pass


def api_create_question(token: str, question_content: str) -> dict:
    status, data = api_request(
        "POST",
        "/questions/create",
        token=token,
        payload={
            "question_content": question_content,
            "type_question": 1,
            "available": True,
            "source": "appium-subject-topic-practice",
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


def api_create_bank(token: str, description: str, topic_id: int, time_limit: int = 20) -> dict:
    status, data = api_request(
        "POST",
        "/banks/create",
        token=token,
        payload={
            "description": description,
            "topic_id": topic_id,
            "time_limit": time_limit,
        },
    )
    if status not in (200, 201):
        raise RuntimeError(f"Tạo practice(bank) thất bại, status={status}, response={data}")
    return data.get("data") or {}


def api_delete_bank(token: str, bank_id: int):
    status, data = api_request("DELETE", f"/banks/remove/{bank_id}", token=token)
    if status not in (200, 202, 204):
        raise RuntimeError(f"Delete practice(bank) thất bại, status={status}, response={data}")


def safe_delete_bank(token: str, bank_id: int | None):
    if not bank_id:
        return
    try:
        api_delete_bank(token, bank_id)
    except Exception:
        pass


def api_assign_questions_to_bank(token: str, bank_id: int, question_ids: list[int]):
    payload = {
        "selectedQuestions": [
            {"bank_id": bank_id, "question_id": question_id} for question_id in question_ids
        ]
    }
    status, data = api_request("POST", "/banks/questions/add", token=token, payload=payload)
    if status not in (200, 201):
        raise RuntimeError(f"Gán question cho practice(bank) thất bại, status={status}, response={data}")


def api_get_bank_question_ids(token: str, bank_id: int) -> list[int]:
    status, data = api_request("GET", f"/banks/{bank_id}/questions", token=token)
    if status != 200:
        raise RuntimeError(f"Lấy question IDs của bank thất bại, status={status}, response={data}")
    return data.get("data") or []


def api_get_bank_detail(token: str, bank_id: int) -> dict:
    status, data = api_request("GET", f"/banks/{bank_id}", token=token)
    if status != 200:
        raise RuntimeError(f"Lấy chi tiết bank thất bại, status={status}, response={data}")
    return data.get("data") or {}


def api_update_bank(token: str, bank_id: int, *, description: str, topic_id: int):
    status, data = api_request(
        "PATCH",
        f"/banks/update/{bank_id}",
        token=token,
        payload={"description": description, "topic_id": topic_id},
    )
    if status not in (200, 202):
        raise RuntimeError(f"Update practice(bank) thất bại, status={status}, response={data}")


def api_list_banks(token: str, *, keyword: str = "", available: str = "All", page: int = 1) -> list[dict]:
    query = urllib.parse.urlencode(
        {
            "page": page,
            "keyword": keyword,
            "available": available,
        }
    )
    status, data = api_request("GET", f"/banks?{query}", token=token)
    if status != 200:
        raise RuntimeError(f"Lấy bank list thất bại, status={status}, response={data}")
    return (data.get("data") or {}).get("banks") or []


def api_find_bank_by_description(token: str, description: str) -> dict | None:
    rows = api_list_banks(token, keyword=description, available="All", page=1)
    for row in rows:
        if (row.get("description") or "").strip() == description:
            return row
    return None


def api_submit_bank(
    token: str,
    *,
    bank_id: int,
    subject_type: int,
    user_name: str,
    do_bank: list[dict],
    time_test: int = 111,
) -> dict:
    query = urllib.parse.urlencode(
        {
            "bank_id": bank_id,
            "subject_type": subject_type,
            "time_test": time_test,
            "user_name": user_name,
        }
    )
    status, data = api_request("POST", f"/banks/submit?{query}", token=token, payload={"do_bank": do_bank})
    if status != 200:
        raise RuntimeError(f"Submit practice(bank) thất bại, status={status}, response={data}")
    return data.get("data") or {}


def api_get_user_bank_history(token: str) -> list[dict]:
    status, data = api_request("GET", "/banks/user/bank-history", token=token)
    if status != 200:
        raise RuntimeError(f"Lấy user bank history thất bại, status={status}, response={data}")
    return (data.get("data") or {}).get("history") or []


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


def login_admin_and_open_topic_subject(driver) -> AdminSubjectTopicPracticePage:
    clear_auth_state(driver)
    page = AdminSubjectTopicPracticePage(driver)
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
    driver.get(page.TOPIC_SUBJECT_URL)
    page.wait_for_url_contains("/admin/topic_subject")
    page.wait_for_visible(page.PAGE_TITLE, timeout=20)
    assert page.is_topic_subject_page(), (
        f"Không vào được trang admin topic_subject, URL hiện tại: {driver.current_url}"
    )
    return page


def login_admin_and_open_practice(driver) -> AdminSubjectTopicPracticePage:
    clear_auth_state(driver)
    page = AdminSubjectTopicPracticePage(driver)
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
    driver.get(page.PRACTICE_URL)
    page.wait_for_url_contains("/admin/bank")
    page.wait_for_visible(page.PRACTICE_TITLE, timeout=20)
    assert page.is_practice_management_page(), (
        f"Không vào được trang admin practice(bank), URL hiện tại: {driver.current_url}"
    )
    return page


class TestAdminSubjectTopicPracticeManagement:
    """Subject/Topic CRUD và Practice(bank) create-edit-delete với history."""

    # ──────────────────────────────────────────────
    # TC-ADMIN-STP-01
    # Create a new subject successfully
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=170)
    def test_create_new_subject_successfully(self, driver):
        token = get_admin_token()
        subject_name = f"[TC-ADMIN-STP-01]-subject-{int(time.time() * 1000)}"
        created_subject_id: int | None = None

        try:
            page = login_admin_and_open_topic_subject(driver)
            page.switch_to_subject_tab()
            page.create_subject(subject_name, subject_type=1)

            assert page.has_subject_row(subject_name, timeout=8), (
                "TC-ADMIN-STP-01: Tạo subject xong nhưng không thấy dòng subject trên UI"
            )

            subjects = api_list_subjects(token)
            created = next((s for s in subjects if (s.get("subject_name") or "").strip() == subject_name), None)
            assert created is not None, "TC-ADMIN-STP-01: API không trả về subject vừa tạo"
            created_subject_id = created.get("subject_id")
        finally:
            safe_delete_subject(token, created_subject_id)

    # ──────────────────────────────────────────────
    # TC-ADMIN-STP-02
    # Disable/Delete subject and check cascade impact on related topics
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=171)
    def test_disable_delete_subject_and_check_cascade_impact_on_related_topics(self, driver):
        token = get_admin_token()
        ts = int(time.time() * 1000)

        subject = api_create_subject(token, f"[TC-ADMIN-STP-02]-subject-{ts}", subject_type=1)
        subject_id = subject.get("subject_id")
        assert subject_id, "TC-ADMIN-STP-02: Không tạo được subject setup"

        topic = api_create_topic(
            token,
            title=f"[TC-ADMIN-STP-02]-topic-{ts}",
            description="topic for cascade check",
            subject_id=subject_id,
        )
        topic_id = topic.get("topic_id")
        assert topic_id, "TC-ADMIN-STP-02: Không tạo được topic setup"

        # Disable subject
        api_set_subject_available(token, subject_id, available=False)
        subjects_after_disable = api_list_subjects(token)
        assert all(int(s.get("subject_id")) != int(subject_id) for s in subjects_after_disable), (
            "TC-ADMIN-STP-02: Subject disable xong nhưng vẫn hiển thị trong danh sách subjects"
        )

        # Topic vẫn còn khi mới disable subject
        topics_after_disable = api_list_topics(token)
        assert any(int(t.get("topic_id")) == int(topic_id) for t in topics_after_disable), (
            "TC-ADMIN-STP-02: Disable subject không được làm mất topic liên quan ngay lập tức"
        )

        # Delete subject -> service sẽ xoá topic liên quan
        api_delete_subject(token, subject_id)
        topics_after_delete = api_list_topics(token)
        assert all(int(t.get("topic_id")) != int(topic_id) for t in topics_after_delete), (
            "TC-ADMIN-STP-02: Xoá subject phải cascade xoá topic liên quan"
        )

    # ──────────────────────────────────────────────
    # TC-ADMIN-STP-03
    # Create a topic under a specific subject
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=172)
    def test_create_topic_under_specific_subject(self, driver):
        token = get_admin_token()
        ts = int(time.time() * 1000)

        subject = api_create_subject(token, f"[TC-ADMIN-STP-03]-subject-{ts}", subject_type=1)
        subject_id = subject.get("subject_id")
        assert subject_id, "TC-ADMIN-STP-03: Không tạo được subject setup"

        topic_title = f"[TC-ADMIN-STP-03]-topic-{ts}"
        topic_desc = "topic create by UI"
        created_topic_id: int | None = None

        try:
            page = login_admin_and_open_topic_subject(driver)
            page.switch_to_topic_tab()
            page.create_topic(topic_title, topic_desc, subject_id=subject_id)

            assert page.has_topic_row(topic_title, timeout=8), (
                "TC-ADMIN-STP-03: Tạo topic xong nhưng không thấy dòng topic trên UI"
            )

            topics = api_list_topics(token)
            created = next((t for t in topics if (t.get("title") or "").strip() == topic_title), None)
            assert created is not None, "TC-ADMIN-STP-03: API không trả về topic vừa tạo"
            created_topic_id = created.get("topic_id")
            assert int(created.get("subject_id")) == int(subject_id), (
                "TC-ADMIN-STP-03: Topic chưa được gán đúng subject"
            )
        finally:
            safe_delete_topic(token, created_topic_id)
            safe_delete_subject(token, subject_id)

    # ──────────────────────────────────────────────
    # TC-ADMIN-STP-04
    # Create practice set with at least 1 valid question
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=173)
    def test_create_practice_set_with_at_least_one_valid_question(self, driver):
        token = get_admin_token()
        ts = int(time.time() * 1000)

        subject = api_create_subject(token, f"[TC-ADMIN-STP-04]-subject-{ts}", subject_type=1)
        subject_id = subject.get("subject_id")
        topic = api_create_topic(
            token,
            title=f"[TC-ADMIN-STP-04]-topic-{ts}",
            description="topic for practice create",
            subject_id=subject_id,
        )
        topic_id = topic.get("topic_id")
        question = api_create_question(token, question_content=f"[TC-ADMIN-STP-04]-question-{ts}")
        question_id = question.get("question_id")
        question_content = question.get("question_content") or f"[TC-ADMIN-STP-04]-question-{ts}"

        bank_id: int | None = None
        description = f"[TC-ADMIN-STP-04]-practice-{ts}"

        try:
            page = login_admin_and_open_practice(driver)
            page.open_create_practice()
            page.fill_practice_form(
                description=description,
                time_limit=20,
                subject_id=subject_id,
                topic_id=topic_id,
            )
            page.submit_create_practice()

            WebDriverWait(driver, 15).until(
                lambda d: "/admin/bank/create/" in d.current_url and "/questions" in d.current_url
            )
            match = re.search(r"/admin/bank/create/(\d+)/questions", driver.current_url)
            assert match, (
                f"TC-ADMIN-STP-04: URL sau tạo practice không đúng format, URL: {driver.current_url}"
            )
            bank_id = int(match.group(1))

            page.search_question_to_assign(question_content)
            selected = page.select_question_for_assignment(question_content)
            assert selected, "TC-ADMIN-STP-04: Không chọn được câu hỏi hợp lệ để gán vào practice"
            page.complete_question_assignment()

            WebDriverWait(driver, 15).until(lambda d: f"/admin/bank/detail/{bank_id}" in d.current_url)
            assert page.is_practice_detail_page(bank_id), (
                f"TC-ADMIN-STP-04: Không điều hướng được sang detail practice, URL: {driver.current_url}"
            )
            page.wait_practice_detail_loaded(timeout=12)
            assert page.page_contains_text(question_content), (
                "TC-ADMIN-STP-04: Detail practice không hiển thị câu hỏi vừa gán"
            )

            ids = api_get_bank_question_ids(token, bank_id)
            assert question_id in ids, (
                "TC-ADMIN-STP-04: API practice detail không chứa question vừa gán"
            )
        finally:
            safe_delete_bank(token, bank_id)
            safe_delete_question(token, question_id)
            safe_delete_topic(token, topic_id)
            safe_delete_subject(token, subject_id)

    # ──────────────────────────────────────────────
    # TC-ADMIN-STP-05
    # Edit practice set: change topic, time limit, or question list
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=174)
    def test_edit_practice_set_change_topic_or_question_list(self, driver):
        token = get_admin_token()
        ts = int(time.time() * 1000)

        subject = api_create_subject(token, f"[TC-ADMIN-STP-05]-subject-{ts}", subject_type=1)
        subject_id = subject.get("subject_id")
        topic1 = api_create_topic(
            token,
            title=f"[TC-ADMIN-STP-05]-topic1-{ts}",
            description="topic1",
            subject_id=subject_id,
        )
        topic2 = api_create_topic(
            token,
            title=f"[TC-ADMIN-STP-05]-topic2-{ts}",
            description="topic2",
            subject_id=subject_id,
        )
        topic1_id = topic1.get("topic_id")
        topic2_id = topic2.get("topic_id")

        bank = api_create_bank(
            token,
            description=f"[TC-ADMIN-STP-05]-practice-before-{ts}",
            topic_id=topic1_id,
            time_limit=25,
        )
        bank_id = bank.get("bank_id")

        q1 = api_create_question(token, question_content=f"[TC-ADMIN-STP-05]-q1-{ts}")
        q2 = api_create_question(token, question_content=f"[TC-ADMIN-STP-05]-q2-{ts}")
        q1_id = q1.get("question_id")
        q2_id = q2.get("question_id")

        try:
            api_assign_questions_to_bank(token, bank_id, [q1_id])

            updated_desc = f"[TC-ADMIN-STP-05]-practice-after-{ts}"
            api_update_bank(
                token,
                bank_id,
                description=updated_desc,
                topic_id=topic2_id,
            )
            # Thay danh sách câu hỏi sang q2
            api_assign_questions_to_bank(token, bank_id, [q2_id])

            updated_bank = api_find_bank_by_description(token, updated_desc)
            assert updated_bank is not None, "TC-ADMIN-STP-05: Không tìm thấy practice sau khi update"
            assert int(updated_bank.get("topic_id")) == int(topic2_id), (
                "TC-ADMIN-STP-05: Chỉnh sửa topic cho practice chưa được lưu"
            )

            ids = api_get_bank_question_ids(token, bank_id)
            assert q2_id in ids and q1_id not in ids, (
                "TC-ADMIN-STP-05: Chỉnh sửa question list cho practice chưa đúng"
            )

            page = login_admin_and_open_practice(driver)
            page.search_practice(updated_desc)
            assert page.has_practice_row(updated_desc, timeout=8), (
                "TC-ADMIN-STP-05: UI chưa hiển thị thông tin practice đã chỉnh sửa"
            )
        finally:
            safe_delete_bank(token, bank_id)
            safe_delete_question(token, q1_id)
            safe_delete_question(token, q2_id)
            safe_delete_topic(token, topic1_id)
            safe_delete_topic(token, topic2_id)
            safe_delete_subject(token, subject_id)

    # ──────────────────────────────────────────────
    # TC-ADMIN-STP-06
    # Delete practice set containing existing user history
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=175)
    def test_delete_practice_set_containing_existing_user_history(self, driver):
        admin_token = get_admin_token()
        user_session = get_user_session()
        user_token = user_session["token"]
        user_name = (user_session["user"] or {}).get("user_name") or "user1"
        ts = int(time.time() * 1000)

        subject = api_create_subject(admin_token, f"[TC-ADMIN-STP-06]-subject-{ts}", subject_type=1)
        subject_id = subject.get("subject_id")
        topic = api_create_topic(
            admin_token,
            title=f"[TC-ADMIN-STP-06]-topic-{ts}",
            description="topic for delete with history",
            subject_id=subject_id,
        )
        topic_id = topic.get("topic_id")

        description = f"[TC-ADMIN-STP-06]-practice-{ts}"
        bank = api_create_bank(admin_token, description=description, topic_id=topic_id, time_limit=15)
        bank_id = bank.get("bank_id")
        question = api_create_question(admin_token, question_content=f"[TC-ADMIN-STP-06]-question-{ts}")
        question_id = question.get("question_id")

        correct_answer_id = None
        for ans in question.get("answers") or []:
            if ans.get("is_correct"):
                correct_answer_id = ans.get("answer_id")
                break
        assert correct_answer_id is not None, "TC-ADMIN-STP-06: Không tìm thấy đáp án đúng setup"

        try:
            api_assign_questions_to_bank(admin_token, bank_id, [question_id])

            detail = api_get_bank_detail(user_token, bank_id)
            subject_type = int(detail.get("subject_type") or 1)

            submit = api_submit_bank(
                user_token,
                bank_id=bank_id,
                subject_type=subject_type,
                user_name=user_name,
                do_bank=[{"question_id": question_id, "user_answer": [int(correct_answer_id)]}],
                time_test=120,
            )
            assert submit.get("history_bank_id"), (
                "TC-ADMIN-STP-06: Submit practice không tạo lịch sử làm bài"
            )

            history_before = api_get_user_bank_history(user_token)
            assert any(int(item.get("bank_id")) == int(bank_id) for item in history_before if item.get("bank_id") is not None), (
                "TC-ADMIN-STP-06: Chưa thấy lịch sử practice trước khi xoá"
            )

            page = login_admin_and_open_practice(driver)
            page.search_practice(description)
            assert page.has_practice_row(description, timeout=8), (
                "TC-ADMIN-STP-06: Không tìm thấy practice cần xoá trên UI admin"
            )
            page.delete_practice_by_description(description)

            time.sleep(1.2)
            bank_after = api_find_bank_by_description(admin_token, description)
            assert bank_after is None, (
                "TC-ADMIN-STP-06: Xoá practice thất bại, practice vẫn còn"
            )

            history_after = api_get_user_bank_history(user_token)
            assert all(int(item.get("bank_id")) != int(bank_id) for item in history_after if item.get("bank_id") is not None), (
                "TC-ADMIN-STP-06: Sau xoá practice, lịch sử liên quan phải được dọn theo cascade"
            )
        finally:
            safe_delete_bank(admin_token, bank_id)
            safe_delete_question(admin_token, question_id)
            safe_delete_topic(admin_token, topic_id)
            safe_delete_subject(admin_token, subject_id)
