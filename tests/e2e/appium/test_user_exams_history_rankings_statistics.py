# tests/test_user_exams_history_rankings_statistics.py
# Kiểm thử Exams, History, Rankings & User Statistics cho user

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

from config import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    BASE_URL,
    USER1_EMAIL,
    USER1_PASSWORD,
)
from pages.login_page import LoginPage
from pages.user_exam_history_rankings_stats_page import UserExamHistoryRankingsStatsPage


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
    token: str | None = None,
    payload: dict | list | None = None,
    timeout: int = 25,
) -> tuple[int, dict]:
    url = f"{BACKEND_BASE_URL}{path}"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    data = None

    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url=url, headers=headers, data=data, method=method.upper())
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
        raise RuntimeError(f"Login thất bại ({email}), status={status}, response={data}")
    payload = data.get("data") or {}
    token = payload.get("token")
    user = payload.get("user") or {}
    if not token:
        raise RuntimeError(f"Login response thiếu token ({email}): {data}")
    return {"token": token, "user": user}


def get_admin_token() -> str:
    return get_login_session(ADMIN_EMAIL, ADMIN_PASSWORD)["token"]


def to_local_input(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M")


def clear_auth_state(driver):
    try:
        driver.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")
    except Exception:
        pass
    try:
        driver.delete_all_cookies()
    except Exception:
        pass


def login_user(driver, email: str, password: str):
    clear_auth_state(driver)
    login_page = LoginPage(driver)
    login_page.login(email, password)
    WebDriverWait(driver, 12).until(lambda d: BASE_URL in d.current_url)


def api_get_users_admin(
    admin_token: str,
    *,
    search: str | None = None,
    status: str = "All",
    role: str = "All",
    page: int = 1,
) -> tuple[list[dict], dict]:
    query_params: dict[str, str | int] = {
        "page": page,
        "status": status,
        "role": role,
    }
    if search:
        query_params["search"] = search
    query = urllib.parse.urlencode(query_params)
    code, data = api_request("GET", f"/users?{query}", token=admin_token)
    if code != 200:
        raise RuntimeError(f"Lấy user list thất bại, status={code}, response={data}")
    payload = data.get("data") or {}
    return payload.get("users") or [], payload


def api_find_user_by_email(admin_token: str, email: str) -> dict | None:
    target = email.strip().lower()
    for page in range(1, 11):
        rows, payload = api_get_users_admin(
            admin_token,
            search=None,
            status="All",
            role="All",
            page=page,
        )
        for row in rows:
            if (row.get("email") or "").strip().lower() == target:
                return row

        if not rows:
            break

        total_pages = int(payload.get("totalPages") or payload.get("total_pages") or 0)
        if total_pages and page >= total_pages:
            break
    return None


def api_update_user(token: str, user_id: int, payload: dict) -> tuple[int, dict]:
    return api_request("PUT", f"/users/update/{user_id}", token=token, payload=payload)


def api_register_user(user_name: str, email: str, password: str) -> tuple[int, dict]:
    return api_request(
        "POST",
        "/auth/register",
        payload={"user_name": user_name, "email": email, "password": password},
    )


def ensure_user_active(admin_token: str, email: str, password: str) -> dict:
    if (email or "").strip().lower() == (ADMIN_EMAIL or "").strip().lower():
        return get_login_session(email, password)

    row = api_find_user_by_email(admin_token, email)
    if not row:
        user_name = email.split("@")[0].replace(".", " ").title()
        reg_code, reg_data = api_register_user(user_name, email, password)
        if reg_code not in (200, 201):
            raise RuntimeError(
                f"Không tìm thấy và không register được user={email}, "
                f"status={reg_code}, response={reg_data}"
            )
        row = api_find_user_by_email(admin_token, email)
        if not row:
            raise RuntimeError(f"Register thành công nhưng không tìm thấy user={email}")

    user_id = int(row["user_id"])
    if not bool(row.get("available")):
        code, data = api_update_user(admin_token, user_id, {"available": True})
        if code != 200:
            raise RuntimeError(f"Không active được user={email}, status={code}, response={data}")
    return get_login_session(email, password)


def api_get_subjects(token: str) -> list[dict]:
    status, data = api_request("GET", "/subjects", token=token)
    if status != 200:
        raise RuntimeError(f"Lấy subjects thất bại, status={status}, response={data}")
    return data.get("data") or []


def api_get_topics(token: str) -> list[dict]:
    status, data = api_request("GET", "/topics", token=token)
    if status != 200:
        raise RuntimeError(f"Lấy topics thất bại, status={status}, response={data}")
    return data.get("data") or []


def api_create_schedule(token: str, *, start_local: str, end_local: str) -> dict:
    status, data = api_request(
        "POST",
        "/exams/schedule/create",
        token=token,
        payload={"start_time": start_local, "end_time": end_local},
    )
    if status not in (200, 201):
        raise RuntimeError(f"Tạo schedule thất bại, status={status}, response={data}")
    return data.get("data") or {}


def api_delete_schedule(token: str, schedule_id: int):
    status, data = api_request("DELETE", f"/exams/schedule/remove/{schedule_id}", token=token)
    if status not in (200, 202, 204):
        raise RuntimeError(f"Xóa schedule thất bại, status={status}, response={data}")


def safe_delete_schedule(token: str, schedule_id: int | None):
    if not schedule_id:
        return
    try:
        api_delete_schedule(token, schedule_id)
    except Exception:
        pass


def api_create_exam(
    token: str,
    *,
    exam_name: str,
    topic_id: int,
    exam_schedule_id: int,
    description: str = "Auto test user exam module",
    time_limit: int = 3,
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
        raise RuntimeError(f"Xóa exam thất bại, status={status}, response={data}")


def safe_delete_exam(token: str, exam_id: int | None):
    if not exam_id:
        return
    try:
        api_delete_exam(token, exam_id)
    except Exception:
        pass


def api_create_question(token: str, *, question_content: str) -> dict:
    status, data = api_request(
        "POST",
        "/questions/create",
        token=token,
        payload={
            "question_content": question_content,
            "type_question": 1,
            "available": True,
            "source": "appium-user-exam",
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
        raise RuntimeError(f"Xóa question thất bại, status={status}, response={data}")


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
            {"exam_id": exam_id, "question_id": qid} for qid in question_ids
        ]
    }
    status, data = api_request("POST", "/exams/questions/add", token=token, payload=payload)
    if status not in (200, 201):
        raise RuntimeError(f"Gán question vào exam thất bại, status={status}, response={data}")


def api_get_exam_detail(token: str, exam_id: int) -> dict:
    status, data = api_request("GET", f"/exams/{exam_id}", token=token)
    if status != 200:
        raise RuntimeError(f"Lấy exam detail thất bại, status={status}, response={data}")
    return data.get("data") or {}


def api_list_exams(
    token: str,
    *,
    page: int = 1,
    available: str = "All",
    keyword: str = "",
    subject_id: int | None = None,
    topic_id: int | None = None,
) -> list[dict]:
    params: dict[str, str | int] = {"page": page, "available": available}
    if keyword:
        params["keyword"] = keyword
    if subject_id is not None:
        params["subject_id"] = subject_id
    if topic_id is not None:
        params["topic_ids"] = topic_id

    query = urllib.parse.urlencode(params)
    status, data = api_request("GET", f"/exams?{query}", token=token)
    if status != 200:
        raise RuntimeError(f"Lấy exam list thất bại, status={status}, response={data}")
    return (data.get("data") or {}).get("exams") or []


def api_check_do_exam(token: str, exam_id: int) -> dict:
    status, data = api_request("GET", f"/exams/check/do/user?exam_id={exam_id}", token=token)
    if status != 200:
        raise RuntimeError(f"checkDoExam thất bại, status={status}, response={data}")
    return data.get("data") or {}


def api_submit_exam(
    token: str,
    *,
    exam_id: int,
    subject_type: int,
    user_name: str,
    do_exam: list[dict],
    time_test: int = 120000,
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
        raise RuntimeError(f"Submit exam thất bại, status={status}, response={data}")
    return data.get("data") or {}


def api_get_user_exam_history(token: str) -> list[dict]:
    status, data = api_request("GET", "/exams/exam-history", token=token)
    if status != 200:
        raise RuntimeError(f"Lấy exam history thất bại, status={status}, response={data}")
    return (data.get("data") or {}).get("history") or []


def api_get_user_answer(token: str, *, exam_id: int, history_exam_id: int) -> tuple[int, dict]:
    return api_request(
        "GET",
        f"/exams/user-answer?exam_id={exam_id}&history_exam_id={history_exam_id}",
        token=token,
    )


def api_get_exam_ranking(token: str, *, exam_id: int, user_name: str, page: int = 1) -> dict:
    query = urllib.parse.urlencode({"user_name": user_name, "page": page})
    status, data = api_request("GET", f"/exams/{exam_id}/ranking?{query}", token=token)
    if status != 200:
        raise RuntimeError(f"Lấy ranking thất bại, status={status}, response={data}")
    return data.get("data") or {}


def pick_topic_for_setup(admin_token: str) -> dict:
    topics = api_get_topics(admin_token)
    if not topics:
        raise RuntimeError("Không có topic để setup exam test")
    return topics[0]


def create_exam_bundle(
    admin_token: str,
    *,
    exam_name: str,
    topic_id: int,
    start_dt: datetime,
    end_dt: datetime,
    time_limit: int = 3,
) -> dict:
    schedule = api_create_schedule(
        admin_token,
        start_local=to_local_input(start_dt),
        end_local=to_local_input(end_dt),
    )
    schedule_id = int(schedule["exam_schedule_id"])

    exam = api_create_exam(
        admin_token,
        exam_name=exam_name,
        topic_id=topic_id,
        exam_schedule_id=schedule_id,
        time_limit=time_limit,
    )
    exam_id = int(exam["exam_id"])

    question = api_create_question(
        admin_token,
        question_content=f"{exam_name}-Q1-{int(time.time() * 1000)}",
    )
    question_id = int(question["question_id"])

    correct_answer_id: int | None = None
    wrong_answer_id: int | None = None
    for ans in question.get("answers") or []:
        answer_id = ans.get("answer_id")
        if answer_id is None:
            continue
        if ans.get("is_correct") and correct_answer_id is None:
            correct_answer_id = int(answer_id)
        if not ans.get("is_correct") and wrong_answer_id is None:
            wrong_answer_id = int(answer_id)

    if correct_answer_id is None:
        raise RuntimeError("Question setup không có đáp án đúng")
    if wrong_answer_id is None:
        raise RuntimeError("Question setup không có đáp án sai")

    try:
        api_assign_questions_to_exam(admin_token, exam_id, [question_id])
    except RuntimeError as exc:
        if 'question_exam' in str(exc).lower():
            pytest.xfail(
                "Backend/DB hien tai thieu bang question_exam, nen khong the setup exam co cau hoi de chay test."
            )
        raise

    return {
        "schedule_id": schedule_id,
        "exam_id": exam_id,
        "exam_name": exam_name,
        "time_limit": int(exam.get("time_limit") or time_limit),
        "question_id": question_id,
        "correct_answer_id": correct_answer_id,
        "wrong_answer_id": wrong_answer_id,
    }


def safe_cleanup_bundle(admin_token: str, bundle: dict | None):
    if not bundle:
        return
    safe_delete_exam(admin_token, bundle.get("exam_id"))
    safe_delete_schedule(admin_token, bundle.get("schedule_id"))
    safe_delete_question(admin_token, bundle.get("question_id"))


def find_history_item_by_exam_id(history: list[dict], exam_id: int) -> dict | None:
    for item in history:
        try:
            if int(item.get("exam_id")) == int(exam_id):
                return item
        except Exception:
            continue
    return None


def extract_float(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)", text or "")
    if not match:
        return None
    try:
        return float(match.group(1))
    except Exception:
        return None


class TestUserExamsHistoryRankingsStatistics:
    """User exam list, do exam, ranking, history và analytics."""

    # ──────────────────────────────────────────────
    # TC-USER-EXAM-01
    # User views available exam list and applies filters
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=200)
    def test_user_views_available_exam_list_and_applies_filters(self, driver):
        admin_token = get_admin_token()
        user_session = ensure_user_active(admin_token, ADMIN_EMAIL, ADMIN_PASSWORD)
        user_token = user_session["token"]

        topics = api_get_topics(admin_token)
        if not topics:
            pytest.xfail("TC-USER-EXAM-01: Không có topic để test filter exam list")
            return

        subjects = api_get_subjects(admin_token)
        subject_map = {int(s["subject_id"]): s.get("subject_name") or "" for s in subjects if s.get("subject_id")}

        primary_topic = topics[0]
        primary_topic_id = int(primary_topic["topic_id"])
        primary_subject_id = int(primary_topic["subject_id"])
        primary_topic_title = (primary_topic.get("title") or "").strip()
        primary_subject_name = (subject_map.get(primary_subject_id) or "").strip()

        if not primary_topic_title or not primary_subject_name:
            pytest.xfail(
                "TC-USER-EXAM-01: Thiếu dữ liệu subject/topic title để thao tác filter trên UI."
            )
            return

        secondary_topic = next((t for t in topics if int(t["topic_id"]) != primary_topic_id), None)

        now = datetime.now()
        bundle_target: dict | None = None
        bundle_other: dict | None = None
        ts = int(time.time() * 1000)
        target_exam_name = f"[TC-USER-EXAM-01]-target-{ts}"
        other_exam_name = f"[TC-USER-EXAM-01]-other-{ts}"

        try:
            bundle_target = create_exam_bundle(
                admin_token,
                exam_name=target_exam_name,
                topic_id=primary_topic_id,
                start_dt=now - timedelta(minutes=20),
                end_dt=now + timedelta(hours=2),
                time_limit=3,
            )

            if secondary_topic is not None:
                bundle_other = create_exam_bundle(
                    admin_token,
                    exam_name=other_exam_name,
                    topic_id=int(secondary_topic["topic_id"]),
                    start_dt=now - timedelta(minutes=15),
                    end_dt=now + timedelta(hours=2),
                    time_limit=3,
                )

            page = UserExamHistoryRankingsStatsPage(driver)
            login_user(driver, ADMIN_EMAIL, ADMIN_PASSWORD)
            page.open_exam_list()

            assert page.is_visible(page.SEARCH_INPUT, timeout=8), (
                "TC-USER-EXAM-01: Không hiển thị ô search trên danh sách đề thi"
            )
            assert page.is_visible(page.FILTER_TOGGLE, timeout=8), (
                "TC-USER-EXAM-01: Không hiển thị panel filter trên danh sách đề thi"
            )

            page.search_exam(target_exam_name)
            assert page.has_exam_card(target_exam_name, timeout=10), (
                "TC-USER-EXAM-01: Search theo exam_name không trả về exam cần tìm"
            )

            page.ensure_filter_open()
            page.choose_filter_subject(primary_subject_name)
            page.choose_filter_topic(primary_topic_title)
            page.apply_filter()

            assert page.has_exam_card(target_exam_name, timeout=10), (
                "TC-USER-EXAM-01: Sau khi áp dụng filter subject/topic, exam mục tiêu không hiển thị"
            )

            filtered_rows = api_list_exams(
                user_token,
                page=1,
                available="All",
                subject_id=primary_subject_id,
                topic_id=primary_topic_id,
            )
            assert any((row.get("exam_name") or "").strip() == target_exam_name for row in filtered_rows), (
                "TC-USER-EXAM-01: API filter danh sách exam không chứa exam mục tiêu"
            )

            if bundle_other is not None:
                if int(secondary_topic["topic_id"]) != primary_topic_id:
                    assert not page.has_exam_card(other_exam_name, timeout=4), (
                        "TC-USER-EXAM-01: Exam khác topic vẫn hiển thị sau khi filter theo topic cụ thể"
                    )
        finally:
            safe_cleanup_bundle(admin_token, bundle_other)
            safe_cleanup_bundle(admin_token, bundle_target)

    # ──────────────────────────────────────────────
    # TC-USER-EXAM-02
    # Access exam within valid time window (pre/in/post schedule)
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=201)
    def test_access_exam_within_valid_time_window_pre_in_post_schedule(self, driver):
        admin_token = get_admin_token()
        user_session = ensure_user_active(admin_token, ADMIN_EMAIL, ADMIN_PASSWORD)
        user_token = user_session["token"]

        topic = pick_topic_for_setup(admin_token)
        topic_id = int(topic["topic_id"])

        ts = int(time.time() * 1000)
        now = datetime.now()
        bundle_pre: dict | None = None
        bundle_in: dict | None = None
        bundle_post: dict | None = None

        try:
            bundle_pre = create_exam_bundle(
                admin_token,
                exam_name=f"[TC-USER-EXAM-02]-pre-{ts}",
                topic_id=topic_id,
                start_dt=now + timedelta(hours=1),
                end_dt=now + timedelta(hours=2),
                time_limit=3,
            )
            bundle_in = create_exam_bundle(
                admin_token,
                exam_name=f"[TC-USER-EXAM-02]-in-{ts}",
                topic_id=topic_id,
                start_dt=now - timedelta(minutes=30),
                end_dt=now + timedelta(hours=2),
                time_limit=3,
            )
            bundle_post = create_exam_bundle(
                admin_token,
                exam_name=f"[TC-USER-EXAM-02]-post-{ts}",
                topic_id=topic_id,
                start_dt=now - timedelta(hours=3),
                end_dt=now - timedelta(hours=1),
                time_limit=3,
            )

            page = UserExamHistoryRankingsStatsPage(driver)
            login_user(driver, ADMIN_EMAIL, ADMIN_PASSWORD)

            in_check = api_check_do_exam(user_token, bundle_in["exam_id"])
            assert bool(in_check.get("check")) is True, (
                f"TC-USER-EXAM-02: Exam trong thời gian hợp lệ phải được phép vào làm, check={in_check}"
            )

            in_subject_type = int(api_get_exam_detail(user_token, bundle_in["exam_id"]).get("subject_type") or 1)
            page.set_exam_context(
                exam_id=bundle_in["exam_id"],
                exam_name=bundle_in["exam_name"],
                time_limit=bundle_in["time_limit"],
                subject_type=in_subject_type,
            )
            page.open_exam_review_rank(bundle_in["exam_id"])
            page.click_start_exam()
            page.wait_do_page_loaded(bundle_in["exam_id"], timeout=15)
            assert f"/exam/{bundle_in['exam_id']}/do" in driver.current_url, (
                "TC-USER-EXAM-02: Exam đang trong thời gian thi phải điều hướng vào trang làm bài"
            )

            post_check = api_check_do_exam(user_token, bundle_post["exam_id"])
            assert bool(post_check.get("check")) is False, (
                f"TC-USER-EXAM-02: Exam đã hết hạn phải bị chặn, check={post_check}"
            )
            assert (post_check.get("reason") or "").upper() == "EXPIRED", (
                f"TC-USER-EXAM-02: Lý do exam hết hạn phải là EXPIRED, check={post_check}"
            )

            post_subject_type = int(api_get_exam_detail(user_token, bundle_post["exam_id"]).get("subject_type") or 1)
            page.set_exam_context(
                exam_id=bundle_post["exam_id"],
                exam_name=bundle_post["exam_name"],
                time_limit=bundle_post["time_limit"],
                subject_type=post_subject_type,
            )
            page.open_exam_review_rank(bundle_post["exam_id"])
            page.click_start_exam()
            time.sleep(1.2)
            assert f"/exam/{bundle_post['exam_id']}/do" not in driver.current_url, (
                "TC-USER-EXAM-02: Exam hết hạn không được cho vào trang làm bài"
            )

            pre_check = api_check_do_exam(user_token, bundle_pre["exam_id"])
            if bool(pre_check.get("check")):
                pytest.xfail(
                    "TC-USER-EXAM-02: Hệ thống hiện chưa chặn truy cập exam trước start_time (chỉ check end_time)."
                )

            reason = (pre_check.get("reason") or "").upper()
            assert reason in {"NOT_STARTED", "NOT_IN_WINDOW", "PRE_SCHEDULE", "START_TIME_NOT_REACHED"}, (
                f"TC-USER-EXAM-02: Exam trước giờ thi phải trả về reason phù hợp, check={pre_check}"
            )
        finally:
            safe_cleanup_bundle(admin_token, bundle_post)
            safe_cleanup_bundle(admin_token, bundle_in)
            safe_cleanup_bundle(admin_token, bundle_pre)

    # ──────────────────────────────────────────────
    # TC-USER-EXAM-03
    # Complete and submit exam within the time limit
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=202)
    def test_complete_and_submit_exam_within_time_limit(self, driver):
        admin_token = get_admin_token()
        user_session = ensure_user_active(admin_token, ADMIN_EMAIL, ADMIN_PASSWORD)
        user_token = user_session["token"]

        topic = pick_topic_for_setup(admin_token)
        ts = int(time.time() * 1000)
        now = datetime.now()
        bundle: dict | None = None

        try:
            bundle = create_exam_bundle(
                admin_token,
                exam_name=f"[TC-USER-EXAM-03]-{ts}",
                topic_id=int(topic["topic_id"]),
                start_dt=now - timedelta(minutes=10),
                end_dt=now + timedelta(hours=2),
                time_limit=3,
            )

            subject_type = int(api_get_exam_detail(user_token, bundle["exam_id"]).get("subject_type") or 1)
            page = UserExamHistoryRankingsStatsPage(driver)

            login_user(driver, ADMIN_EMAIL, ADMIN_PASSWORD)
            page.set_exam_context(
                exam_id=bundle["exam_id"],
                exam_name=bundle["exam_name"],
                time_limit=bundle["time_limit"],
                subject_type=subject_type,
            )
            page.open_exam_do_page(bundle["exam_id"])
            page.answer_first_single_choice()
            page.submit_exam()
            page.confirm_submit_if_needed()
            page.wait_result_page_loaded(bundle["exam_id"], timeout=20)

            history = api_get_user_exam_history(user_token)
            item = find_history_item_by_exam_id(history, bundle["exam_id"])
            assert item is not None, (
                "TC-USER-EXAM-03: Submit exam thành công nhưng không thấy lịch sử làm bài tương ứng"
            )
            assert item.get("history_exam_id"), (
                "TC-USER-EXAM-03: Lịch sử làm bài không có history_exam_id"
            )
        finally:
            safe_cleanup_bundle(admin_token, bundle)

    # ──────────────────────────────────────────────
    # TC-USER-EXAM-04
    # System auto-submits exam when timer reaches zero
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=203)
    def test_system_auto_submits_exam_when_timer_reaches_zero(self, driver):
        admin_token = get_admin_token()
        user_session = ensure_user_active(admin_token, ADMIN_EMAIL, ADMIN_PASSWORD)
        user_token = user_session["token"]
        user_name = ((user_session.get("user") or {}).get("user_name") or "user1").strip()

        topic = pick_topic_for_setup(admin_token)
        ts = int(time.time() * 1000)
        now = datetime.now()
        bundle: dict | None = None

        try:
            bundle = create_exam_bundle(
                admin_token,
                exam_name=f"[TC-USER-EXAM-04]-{ts}",
                topic_id=int(topic["topic_id"]),
                start_dt=now - timedelta(minutes=5),
                end_dt=now + timedelta(hours=2),
                time_limit=1,
            )

            subject_type = int(api_get_exam_detail(user_token, bundle["exam_id"]).get("subject_type") or 1)
            page = UserExamHistoryRankingsStatsPage(driver)

            login_user(driver, ADMIN_EMAIL, ADMIN_PASSWORD)
            page.set_exam_context(
                exam_id=bundle["exam_id"],
                exam_name=bundle["exam_name"],
                time_limit=bundle["time_limit"],
                subject_type=subject_type,
            )
            page.open_exam_do_page(bundle["exam_id"])

            page.set_exam_resume_state(
                exam_id=bundle["exam_id"],
                answers={},
                time_left=8,
                user_name=user_name,
            )
            driver.refresh()
            WebDriverWait(driver, 8).until(lambda d: f"/exam/{bundle['exam_id']}/do" in d.current_url)

            page.wait_result_page_loaded(bundle["exam_id"], timeout=30)

            history = api_get_user_exam_history(user_token)
            item = find_history_item_by_exam_id(history, bundle["exam_id"])
            assert item is not None, (
                "TC-USER-EXAM-04: Hết giờ auto-submit nhưng không ghi nhận lịch sử làm bài"
            )
        finally:
            safe_cleanup_bundle(admin_token, bundle)

    # ──────────────────────────────────────────────
    # TC-USER-EXAM-05
    # Check retake restrictions for the same exam (if applicable)
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=204)
    def test_check_retake_restrictions_for_same_exam(self, driver):
        admin_token = get_admin_token()
        user_session = ensure_user_active(admin_token, ADMIN_EMAIL, ADMIN_PASSWORD)
        user_token = user_session["token"]
        user_name = ((user_session.get("user") or {}).get("user_name") or "user1").strip()

        topic = pick_topic_for_setup(admin_token)
        ts = int(time.time() * 1000)
        now = datetime.now()
        bundle: dict | None = None

        try:
            bundle = create_exam_bundle(
                admin_token,
                exam_name=f"[TC-USER-EXAM-05]-{ts}",
                topic_id=int(topic["topic_id"]),
                start_dt=now - timedelta(minutes=6),
                end_dt=now + timedelta(hours=2),
                time_limit=3,
            )
            subject_type = int(api_get_exam_detail(user_token, bundle["exam_id"]).get("subject_type") or 1)

            api_submit_exam(
                user_token,
                exam_id=bundle["exam_id"],
                subject_type=subject_type,
                user_name=user_name,
                do_exam=[{"question_id": bundle["question_id"], "user_answer": [bundle["correct_answer_id"]]}],
                time_test=110000,
            )

            check = api_check_do_exam(user_token, bundle["exam_id"])
            assert bool(check.get("check")) is False, (
                f"TC-USER-EXAM-05: User đã làm bài rồi phải bị chặn retake, check={check}"
            )
            assert (check.get("reason") or "").upper() == "ALREADY_DONE", (
                f"TC-USER-EXAM-05: Lý do retake restriction phải là ALREADY_DONE, check={check}"
            )

            page = UserExamHistoryRankingsStatsPage(driver)
            login_user(driver, ADMIN_EMAIL, ADMIN_PASSWORD)
            page.set_exam_context(
                exam_id=bundle["exam_id"],
                exam_name=bundle["exam_name"],
                time_limit=bundle["time_limit"],
                subject_type=subject_type,
            )
            page.open_exam_review_rank(bundle["exam_id"])
            page.click_start_exam()
            time.sleep(1.2)
            assert f"/exam/{bundle['exam_id']}/do" not in driver.current_url, (
                "TC-USER-EXAM-05: User đã làm bài không được phép vào lại trang làm bài"
            )
        finally:
            safe_cleanup_bundle(admin_token, bundle)

    # ──────────────────────────────────────────────
    # TC-USER-EXAM-06
    # Handle disconnection or app exit during an active exam
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=205)
    def test_handle_disconnection_or_app_exit_during_active_exam(self, driver):
        admin_token = get_admin_token()
        user_session = ensure_user_active(admin_token, ADMIN_EMAIL, ADMIN_PASSWORD)
        user_token = user_session["token"]

        topic = pick_topic_for_setup(admin_token)
        ts = int(time.time() * 1000)
        now = datetime.now()
        bundle: dict | None = None

        try:
            bundle = create_exam_bundle(
                admin_token,
                exam_name=f"[TC-USER-EXAM-06]-{ts}",
                topic_id=int(topic["topic_id"]),
                start_dt=now - timedelta(minutes=5),
                end_dt=now + timedelta(hours=2),
                time_limit=3,
            )
            subject_type = int(api_get_exam_detail(user_token, bundle["exam_id"]).get("subject_type") or 1)

            page = UserExamHistoryRankingsStatsPage(driver)
            login_user(driver, ADMIN_EMAIL, ADMIN_PASSWORD)
            page.set_exam_context(
                exam_id=bundle["exam_id"],
                exam_name=bundle["exam_name"],
                time_limit=bundle["time_limit"],
                subject_type=subject_type,
            )
            page.open_exam_do_page(bundle["exam_id"])
            page.answer_first_single_choice()
            time.sleep(1.3)

            before_state = page.get_exam_resume_state(bundle["exam_id"])
            before_answers = before_state.get("answers") or {}
            before_time_left = int(before_state.get("timeLeft") or 0)
            assert before_answers, (
                "TC-USER-EXAM-06: Trạng thái làm bài chưa được autosave trước khi simulate mất kết nối"
            )
            assert before_time_left > 0, (
                "TC-USER-EXAM-06: Trạng thái autosave phải có timeLeft > 0"
            )

            driver.refresh()
            page.wait_do_page_loaded(bundle["exam_id"], timeout=15)
            time.sleep(1.0)

            after_state = page.get_exam_resume_state(bundle["exam_id"])
            after_answers = after_state.get("answers") or {}
            after_time_left = int(after_state.get("timeLeft") or 0)

            assert after_answers == before_answers, (
                "TC-USER-EXAM-06: Sau reload/disconnect, đáp án đã làm chưa được restore đúng"
            )
            assert 0 < after_time_left <= before_time_left, (
                "TC-USER-EXAM-06: Sau reconnect, timer phải tiếp tục từ trạng thái đã lưu"
            )
            assert page.is_first_single_choice_checked(), (
                "TC-USER-EXAM-06: Option đã chọn trước khi ngắt kết nối chưa được khôi phục trên UI"
            )
        finally:
            safe_cleanup_bundle(admin_token, bundle)

    # ──────────────────────────────────────────────
    # TC-USER-EXAM-07
    # Verify accuracy of exam results and automated scoring
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=206)
    def test_verify_accuracy_of_exam_results_and_automated_scoring(self, driver):
        admin_token = get_admin_token()
        user_session = ensure_user_active(admin_token, ADMIN_EMAIL, ADMIN_PASSWORD)
        user_token = user_session["token"]
        user_name = ((user_session.get("user") or {}).get("user_name") or "user1").strip()

        topic = pick_topic_for_setup(admin_token)
        ts = int(time.time() * 1000)
        now = datetime.now()
        bundle: dict | None = None

        try:
            bundle = create_exam_bundle(
                admin_token,
                exam_name=f"[TC-USER-EXAM-07]-{ts}",
                topic_id=int(topic["topic_id"]),
                start_dt=now - timedelta(minutes=8),
                end_dt=now + timedelta(hours=2),
                time_limit=3,
            )
            subject_type = int(api_get_exam_detail(user_token, bundle["exam_id"]).get("subject_type") or 1)

            submit = api_submit_exam(
                user_token,
                exam_id=bundle["exam_id"],
                subject_type=subject_type,
                user_name=user_name,
                do_exam=[{"question_id": bundle["question_id"], "user_answer": [bundle["correct_answer_id"]]}],
                time_test=90000,
            )
            history_exam_id = int(submit["history_exam_id"])
            score_submit = float(submit.get("score") or 0)
            assert abs(score_submit - 0.25) < 0.0001, (
                f"TC-USER-EXAM-07: Chấm điểm tự động sai, expected=0.25, actual={score_submit}"
            )

            status_answer, data_answer = api_get_user_answer(
                user_token,
                exam_id=bundle["exam_id"],
                history_exam_id=history_exam_id,
            )
            assert status_answer == 200, (
                f"TC-USER-EXAM-07: Không lấy được bài làm để verify score, status={status_answer}, response={data_answer}"
            )
            score_api = float(((data_answer.get("data") or {}).get("score")) or 0)
            assert abs(score_api - 0.25) < 0.0001, (
                f"TC-USER-EXAM-07: Score từ endpoint user-answer không khớp expected=0.25, actual={score_api}"
            )

            page = UserExamHistoryRankingsStatsPage(driver)
            login_user(driver, ADMIN_EMAIL, ADMIN_PASSWORD)
            driver.get(f"{BASE_URL}/exam/{bundle['exam_id']}/result/{history_exam_id}")
            page.wait_result_page_loaded(bundle["exam_id"], timeout=15)

            score_text = page.get_result_score_text()
            ui_score = extract_float(score_text)
            assert ui_score is not None and abs(ui_score - 0.25) < 0.0001, (
                f"TC-USER-EXAM-07: Điểm hiển thị trên UI không chính xác, text={score_text!r}"
            )
        finally:
            safe_cleanup_bundle(admin_token, bundle)

    # ──────────────────────────────────────────────
    # TC-USER-EXAM-08
    # View leaderboard and rankings after submission
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=207)
    def test_view_leaderboard_and_rankings_after_submission(self, driver):
        admin_token = get_admin_token()
        user1_session = ensure_user_active(admin_token, ADMIN_EMAIL, ADMIN_PASSWORD)
        user2_session = ensure_user_active(admin_token, USER1_EMAIL, USER1_PASSWORD)
        user1_token = user1_session["token"]
        user2_token = user2_session["token"]
        user1_name = ((user1_session.get("user") or {}).get("user_name") or "user1").strip()
        user2_name = ((user2_session.get("user") or {}).get("user_name") or "user2").strip()

        topic = pick_topic_for_setup(admin_token)
        ts = int(time.time() * 1000)
        now = datetime.now()
        bundle: dict | None = None

        try:
            bundle = create_exam_bundle(
                admin_token,
                exam_name=f"[TC-USER-EXAM-08]-{ts}",
                topic_id=int(topic["topic_id"]),
                start_dt=now - timedelta(minutes=8),
                end_dt=now + timedelta(hours=2),
                time_limit=3,
            )
            subject_type = int(api_get_exam_detail(user1_token, bundle["exam_id"]).get("subject_type") or 1)

            api_submit_exam(
                user2_token,
                exam_id=bundle["exam_id"],
                subject_type=subject_type,
                user_name=user2_name,
                do_exam=[{"question_id": bundle["question_id"], "user_answer": [bundle["wrong_answer_id"]]}],
                time_test=100000,
            )
            api_submit_exam(
                user1_token,
                exam_id=bundle["exam_id"],
                subject_type=subject_type,
                user_name=user1_name,
                do_exam=[{"question_id": bundle["question_id"], "user_answer": [bundle["correct_answer_id"]]}],
                time_test=90000,
            )

            ranking_data = api_get_exam_ranking(
                user1_token,
                exam_id=bundle["exam_id"],
                user_name=user1_name,
                page=1,
            )
            ranking = (ranking_data.get("ranking") or {}).get("rank") or []
            my_rank = (ranking_data.get("ranking") or {}).get("my_rank")

            assert len(ranking) > 0, (
                "TC-USER-EXAM-08: Sau submit phải có dữ liệu leaderboard/ranking"
            )
            assert my_rank is not None, (
                "TC-USER-EXAM-08: Ranking response phải có my_rank cho user đã submit"
            )

            page = UserExamHistoryRankingsStatsPage(driver)
            login_user(driver, ADMIN_EMAIL, ADMIN_PASSWORD)
            page.set_exam_context(
                exam_id=bundle["exam_id"],
                exam_name=bundle["exam_name"],
                time_limit=bundle["time_limit"],
                subject_type=subject_type,
            )
            page.open_exam_review_rank(bundle["exam_id"])
            page.wait_ranking_loaded(timeout=12)

            assert page.wait_text_in_page(user1_name, timeout=8) or page.wait_text_in_page(user2_name, timeout=8), (
                "TC-USER-EXAM-08: UI leaderboard không hiển thị tên user đã submit"
            )
            assert page.is_visible(page.MY_RANK_TITLE, timeout=8), (
                "TC-USER-EXAM-08: UI ranking không hiển thị block 'Thành tích của bạn'"
            )
        finally:
            safe_cleanup_bundle(admin_token, bundle)

    # ──────────────────────────────────────────────
    # TC-USER-EXAM-09
    # View exam history and reopen detailed results
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=208)
    def test_view_exam_history_and_reopen_detailed_results(self, driver):
        admin_token = get_admin_token()
        user_session = ensure_user_active(admin_token, ADMIN_EMAIL, ADMIN_PASSWORD)
        user_token = user_session["token"]
        user_name = ((user_session.get("user") or {}).get("user_name") or "user1").strip()

        topic = pick_topic_for_setup(admin_token)
        ts = int(time.time() * 1000)
        now = datetime.now()
        bundle: dict | None = None

        try:
            bundle = create_exam_bundle(
                admin_token,
                exam_name=f"[TC-USER-EXAM-09]-{ts}",
                topic_id=int(topic["topic_id"]),
                start_dt=now - timedelta(minutes=8),
                end_dt=now + timedelta(hours=2),
                time_limit=3,
            )
            subject_type = int(api_get_exam_detail(user_token, bundle["exam_id"]).get("subject_type") or 1)
            submit = api_submit_exam(
                user_token,
                exam_id=bundle["exam_id"],
                subject_type=subject_type,
                user_name=user_name,
                do_exam=[{"question_id": bundle["question_id"], "user_answer": [bundle["correct_answer_id"]]}],
                time_test=95000,
            )
            history_exam_id = int(submit["history_exam_id"])

            page = UserExamHistoryRankingsStatsPage(driver)
            login_user(driver, ADMIN_EMAIL, ADMIN_PASSWORD)
            page.open_history_page()

            assert page.is_visible(page.HISTORY_TITLE, timeout=10), (
                "TC-USER-EXAM-09: Không hiển thị section lịch sử làm bài"
            )
            assert page.has_history_exam_card(bundle["exam_name"], timeout=12), (
                "TC-USER-EXAM-09: Không thấy bản ghi exam mới trong lịch sử làm bài"
            )

            page.click_history_exam_card(bundle["exam_name"])
            page.wait_result_page_loaded(bundle["exam_id"], timeout=15)
            assert f"/exam/{bundle['exam_id']}/result/{history_exam_id}" in driver.current_url, (
                "TC-USER-EXAM-09: Click exam history không mở đúng trang chi tiết kết quả"
            )
        finally:
            safe_cleanup_bundle(admin_token, bundle)

    # ──────────────────────────────────────────────
    # TC-USER-EXAM-10
    # View personal statistics (Data vs. No Data states)
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=209)
    def test_view_personal_statistics_data_vs_no_data_states(self, driver):
        admin_token = get_admin_token()
        user_session = ensure_user_active(admin_token, ADMIN_EMAIL, ADMIN_PASSWORD)
        user_token = user_session["token"]

        page = UserExamHistoryRankingsStatsPage(driver)
        login_user(driver, ADMIN_EMAIL, ADMIN_PASSWORD)
        page.open_analytics_page()

        assert page.is_visible(page.ANALYTICS_HEADING, timeout=8), (
            "TC-USER-EXAM-10: Trang analytics không hiển thị heading"
        )
        assert page.is_visible(page.ANALYTICS_PLACEHOLDER, timeout=8), (
            "TC-USER-EXAM-10: Trang analytics không hiển thị trạng thái placeholder hiện tại"
        )

        has_history = len(api_get_user_exam_history(user_token)) > 0
        if has_history:
            pytest.xfail(
                "TC-USER-EXAM-10: Analytics chưa triển khai state hiển thị thống kê khi user đã có dữ liệu."
            )
        pytest.xfail(
            "TC-USER-EXAM-10: Analytics chưa triển khai state 'No Data' theo yêu cầu nghiệp vụ."
        )
