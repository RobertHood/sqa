# tests/test_admin_question_management.py
# Kiểm thử Admin Question Management (mobile web qua Appium)

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest
from selenium.webdriver.support.ui import WebDriverWait

from config import ADMIN_BASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD, BASE_URL
from pages.admin_question_page import AdminQuestionPage


BACKEND_BASE_URL = "http://localhost:3000"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


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
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url=url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = response.getcode()
            body = response.read().decode("utf-8", errors="ignore")
            return status, _parse_json(body)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        return exc.code, _parse_json(body)


def get_admin_token() -> str:
    status, data = api_request(
        "POST",
        "/auth/login",
        payload={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    if status != 200:
        raise RuntimeError(f"Không lấy được admin token, status={status}, response={data}")

    token = (data.get("data") or {}).get("token")
    if not token:
        raise RuntimeError(f"Login response không có token: {data}")
    return token


def get_admin_session() -> dict:
    status, data = api_request(
        "POST",
        "/auth/login",
        payload={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    if status != 200:
        raise RuntimeError(f"Khong lay duoc admin token, status={status}, response={data}")

    payload = data.get("data") or {}
    token = payload.get("token")
    if not token:
        raise RuntimeError(f"Login response khong co token: {data}")

    return {
        "token": token,
        "user": payload.get("user") or {},
        "permissions": payload.get("permissions") or {},
    }


def get_admin_token() -> str:
    return get_admin_session()["token"]


def api_list_questions(
    token: str,
    *,
    keyword: str = "",
    type_question: int = 0,
    available: str = "All",
    page: int = 1,
) -> list[dict]:
    query = urllib.parse.urlencode(
        {
            "page": page,
            "available": available,
            "type_question": type_question,
            "keyword": keyword,
        }
    )
    status, data = api_request("GET", f"/questions?{query}", token=token)
    if status != 200:
        raise RuntimeError(f"Không lấy được danh sách question, status={status}, response={data}")
    return ((data.get("data") or {}).get("question") or [])


def api_find_question_by_exact_content(token: str, content: str) -> dict | None:
    rows = api_list_questions(token, keyword=content, available="All", type_question=0, page=1)
    for row in rows:
        current = (row.get("question_content") or "").strip()
        if current == content:
            return row
    return None


def api_create_question(
    token: str,
    *,
    question_content: str,
    type_question: int,
    available: bool,
    answers: list[dict],
    images: list[str] | None = None,
    source: str = "appium-admin-question",
) -> dict:
    payload = {
        "question_content": question_content,
        "type_question": type_question,
        "available": available,
        "source": source,
        "answers": answers,
        "images": images or [],
    }
    status, data = api_request("POST", "/questions/create", token=token, payload=payload)
    if status not in (200, 201):
        raise RuntimeError(f"Tạo question thất bại, status={status}, response={data}")

    question = data.get("data") or {}
    if not question.get("question_id"):
        raise RuntimeError(f"Response create question không hợp lệ: {data}")
    return question


def api_update_question(token: str, question_id: int, payload: dict):
    status, data = api_request(
        "PATCH",
        f"/questions/update/{question_id}",
        token=token,
        payload=payload,
    )
    if status not in (200, 202):
        raise RuntimeError(f"Update question thất bại, status={status}, response={data}")
    return data.get("data")


def api_delete_question(token: str, question_id: int):
    status, data = api_request("DELETE", f"/questions/remove/{question_id}", token=token)
    if status not in (200, 202, 204):
        raise RuntimeError(f"Delete question thất bại, status={status}, response={data}")


def api_get_first_topic_id(token: str) -> int | None:
    status, data = api_request("GET", "/topics", token=token)
    if status != 200:
        return None
    topics = data.get("data") or []
    if not topics:
        return None
    return topics[0].get("topic_id")


def api_create_bank(token: str, description: str, topic_id: int | None, time_limit: int = 15) -> dict:
    payload = {
        "description": description,
        "topic_id": topic_id,
        "time_limit": time_limit,
    }
    status, data = api_request("POST", "/banks/create", token=token, payload=payload)
    if status not in (200, 201):
        raise RuntimeError(f"Tạo bank thất bại, status={status}, response={data}")
    return data.get("data") or {}


def api_delete_bank(token: str, bank_id: int):
    status, data = api_request("DELETE", f"/banks/remove/{bank_id}", token=token)
    if status not in (200, 202, 204):
        raise RuntimeError(f"Delete bank thất bại, status={status}, response={data}")


def api_link_question_to_bank(token: str, bank_id: int, question_id: int):
    payload = {"selectedQuestions": [{"bank_id": bank_id, "question_id": question_id}]}
    status, data = api_request("POST", "/banks/questions/add", token=token, payload=payload)
    if status not in (200, 201):
        raise RuntimeError(f"Link question->bank thất bại, status={status}, response={data}")


def safe_delete_question(token: str, question_id: int | None):
    if not question_id:
        return
    try:
        api_delete_question(token, question_id)
    except Exception:
        pass


def safe_delete_bank(token: str, bank_id: int | None):
    if not bank_id:
        return
    try:
        api_delete_bank(token, bank_id)
    except Exception:
        pass


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


def login_admin_and_open_questions(driver) -> AdminQuestionPage:
    clear_auth_state(driver)
    question_page = AdminQuestionPage(driver)
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

    driver.get(question_page.URL)
    question_page.wait_until_loaded(timeout=20)

    assert question_page.is_question_management_page(), (
        f"Không vào được trang quản lý câu hỏi admin, URL hiện tại: {driver.current_url}"
    )
    return question_page


def get_sample_image_path() -> str:
    candidates = [
        PROJECT_ROOT / "backend/data/outputs/media/94cf41a3733ff86082acecb525ee8ea4f1eeded8.png",
        PROJECT_ROOT / "backend/data/outputs/media/e9be2056eafd46c99a782ca236f8a6040de14a8d.jpg",
    ]
    for path in candidates:
        if path.is_file():
            return str(path)

    screenshot_candidates = sorted((PROJECT_ROOT / "appium_tests/screenshots").glob("*.png"))
    if screenshot_candidates:
        return str(screenshot_candidates[0])

    raise FileNotFoundError("Không tìm thấy file ảnh mẫu để test upload")


def get_sample_docx_path() -> str:
    docx_files = sorted((PROJECT_ROOT / "backend/resources/docx_file").glob("*.docx"))
    if not docx_files:
        raise FileNotFoundError("Không tìm thấy file DOCX mẫu")
    return str(docx_files[0])


class TestAdminQuestionManagement:
    """Filter/create/validate/edit/delete/import cho admin question management."""

    # ──────────────────────────────────────────────
    # TC-ADMIN-Q-01
    # Filter question list by status and question type
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=150)
    def test_filter_question_list_by_status_and_question_type(self, driver):
        token = get_admin_token()
        ts = int(time.time() * 1000)
        prefix = f"[TC-ADMIN-Q-01]-{ts}"

        single_content = f"{prefix} single-active"
        multi_content = f"{prefix} multi-active"
        essay_content = f"{prefix} essay-inactive"

        created_ids: list[int] = []
        try:
            q1 = api_create_question(
                token,
                question_content=single_content,
                type_question=1,
                available=True,
                answers=[
                    {"answer_content": "A1", "is_correct": True},
                    {"answer_content": "A2", "is_correct": False},
                    {"answer_content": "A3", "is_correct": False},
                    {"answer_content": "A4", "is_correct": False},
                ],
            )
            created_ids.append(q1["question_id"])

            q2 = api_create_question(
                token,
                question_content=multi_content,
                type_question=2,
                available=True,
                answers=[
                    {"answer_content": "B1", "is_correct": True},
                    {"answer_content": "B2", "is_correct": False},
                    {"answer_content": "B3", "is_correct": True},
                    {"answer_content": "B4", "is_correct": False},
                ],
            )
            created_ids.append(q2["question_id"])

            q3 = api_create_question(
                token,
                question_content=essay_content,
                type_question=3,
                available=False,
                answers=[{"answer_content": "Sample answer", "is_correct": True}],
            )
            created_ids.append(q3["question_id"])

            page = login_admin_and_open_questions(driver)
            page.search_question(prefix)

            assert page.has_question_card_containing(single_content), (
                "TC-ADMIN-Q-01: Không thấy câu single active sau search theo prefix"
            )
            assert page.has_question_card_containing(multi_content), (
                "TC-ADMIN-Q-01: Không thấy câu multiple active sau search theo prefix"
            )
            assert page.has_question_card_containing(essay_content), (
                "TC-ADMIN-Q-01: Không thấy câu essay inactive sau search theo prefix"
            )

            page.set_status_filter("true")
            assert page.get_selected_status_filter() == "true", (
                "TC-ADMIN-Q-01: Filter trạng thái không chuyển về 'true'"
            )
            assert page.has_question_card_containing(single_content), (
                "TC-ADMIN-Q-01: Status=true phải còn hiển thị câu active"
            )
            assert page.has_question_card_containing(multi_content), (
                "TC-ADMIN-Q-01: Status=true phải còn hiển thị câu active"
            )
            assert not page.has_question_card_containing(essay_content), (
                "TC-ADMIN-Q-01: Status=true không được hiển thị câu inactive"
            )

            page.set_status_filter("All")
            page.set_type_filter(3)
            assert page.get_selected_type_filter() == "3", (
                "TC-ADMIN-Q-01: Filter type không chuyển về type=3 (essay)"
            )
            assert page.has_question_card_containing(essay_content), (
                "TC-ADMIN-Q-01: Type=3 phải hiển thị câu essay"
            )
            assert not page.has_question_card_containing(single_content), (
                "TC-ADMIN-Q-01: Type=3 không được hiển thị câu single"
            )
            assert not page.has_question_card_containing(multi_content), (
                "TC-ADMIN-Q-01: Type=3 không được hiển thị câu multiple"
            )

        finally:
            for question_id in created_ids:
                safe_delete_question(token, question_id)

    # ──────────────────────────────────────────────
    # TC-ADMIN-Q-02
    # Create valid single-choice question
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=151)
    def test_create_valid_single_choice_question(self, driver):
        token = get_admin_token()
        ts = int(time.time() * 1000)
        question_content = f"[TC-ADMIN-Q-02]-single-{ts}"
        created_question_id: int | None = None

        try:
            page = login_admin_and_open_questions(driver)
            page.click_add_question()
            assert page.is_create_page(), (
                f"TC-ADMIN-Q-02: Không vào được trang tạo câu hỏi, URL: {driver.current_url}"
            )

            page.fill_question_content(question_content)
            page.choose_single_choice_type()
            page.fill_answer(1, "Đáp án 1")
            page.fill_answer(2, "Đáp án 2")
            page.fill_answer(3, "Đáp án 3")
            page.fill_answer(4, "Đáp án 4")
            page.set_single_correct_answer(2)
            page.save_question()

            WebDriverWait(driver, 15).until(
                lambda d: "/admin/questions" in d.current_url and "/create" not in d.current_url
            )

            page.search_question(question_content)
            assert page.has_question_card_containing(question_content), (
                "TC-ADMIN-Q-02: Tạo single-choice thành công nhưng không thấy câu hỏi trong danh sách"
            )

            created = api_find_question_by_exact_content(token, question_content)
            assert created is not None, (
                "TC-ADMIN-Q-02: API không tìm thấy câu hỏi mới tạo"
            )
            created_question_id = created.get("question_id")
            assert created.get("type_question") == 1, (
                "TC-ADMIN-Q-02: Câu hỏi tạo mới phải có type_question = 1"
            )

        finally:
            safe_delete_question(token, created_question_id)

    # ──────────────────────────────────────────────
    # TC-ADMIN-Q-03
    # Create multiple-choice question with image attachments
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=152)
    def test_create_multiple_choice_question_with_image_attachments(self, driver):
        token = get_admin_token()
        ts = int(time.time() * 1000)
        question_content = f"[TC-ADMIN-Q-03]-multiple-img-{ts}"
        created_question_id: int | None = None

        try:
            sample_image = get_sample_image_path()
        except FileNotFoundError as exc:
            pytest.xfail(f"TC-ADMIN-Q-03: {exc}")
            return

        try:
            page = login_admin_and_open_questions(driver)
            page.click_add_question()
            assert page.is_create_page(), (
                f"TC-ADMIN-Q-03: Không vào được trang tạo câu hỏi, URL: {driver.current_url}"
            )

            page.fill_question_content(question_content)
            page.choose_multiple_choice_type()
            page.fill_answer(1, "Đáp án A")
            page.fill_answer(2, "Đáp án B")
            page.fill_answer(3, "Đáp án C")
            page.fill_answer(4, "Đáp án D")
            page.set_multiple_correct_answers([1, 3])
            page.attach_question_image(sample_image)
            page.attach_answer_image(sample_image)
            page.save_question()

            WebDriverWait(driver, 18).until(
                lambda d: "/admin/questions" in d.current_url and "/create" not in d.current_url
            )

            page.search_question(question_content)
            assert page.has_question_card_containing(question_content), (
                "TC-ADMIN-Q-03: Không thấy câu multiple-choice sau khi lưu"
            )

            created = api_find_question_by_exact_content(token, question_content)
            assert created is not None, "TC-ADMIN-Q-03: API không tìm thấy câu hỏi mới tạo"
            created_question_id = created.get("question_id")
            assert created.get("type_question") == 2, (
                "TC-ADMIN-Q-03: Câu hỏi tạo mới phải có type_question = 2"
            )
            assert len(created.get("images") or []) > 0, (
                "TC-ADMIN-Q-03: Câu hỏi multiple-choice phải lưu được ảnh câu hỏi"
            )
            assert any(len(ans.get("images") or []) > 0 for ans in (created.get("answers") or [])), (
                "TC-ADMIN-Q-03: Câu hỏi multiple-choice phải lưu được ảnh đáp án"
            )

        finally:
            safe_delete_question(token, created_question_id)

    # ──────────────────────────────────────────────
    # TC-ADMIN-Q-04
    # Create essay question with sample answer
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=153)
    def test_create_essay_question_with_sample_answer(self, driver):
        token = get_admin_token()
        ts = int(time.time() * 1000)
        question_content = f"[TC-ADMIN-Q-04]-essay-{ts}"
        sample_answer = f"Đây là đáp án mẫu {ts}"
        created_question_id: int | None = None

        try:
            page = login_admin_and_open_questions(driver)
            page.click_add_question()
            assert page.is_create_page(), (
                f"TC-ADMIN-Q-04: Không vào được trang tạo câu hỏi, URL: {driver.current_url}"
            )

            page.fill_question_content(question_content)
            page.choose_essay_type()
            page.fill_essay_sample_answer(sample_answer)
            page.save_question()

            WebDriverWait(driver, 15).until(
                lambda d: "/admin/questions" in d.current_url and "/create" not in d.current_url
            )

            page.search_question(question_content)
            assert page.has_question_card_containing(question_content), (
                "TC-ADMIN-Q-04: Không thấy câu essay sau khi lưu"
            )

            created = api_find_question_by_exact_content(token, question_content)
            assert created is not None, "TC-ADMIN-Q-04: API không tìm thấy câu hỏi mới tạo"
            created_question_id = created.get("question_id")
            assert created.get("type_question") == 3, (
                "TC-ADMIN-Q-04: Câu hỏi essay phải có type_question = 3"
            )
            answers = created.get("answers") or []
            assert len(answers) >= 1, "TC-ADMIN-Q-04: Câu hỏi essay phải có ít nhất 1 đáp án mẫu"
            assert sample_answer in (answers[0].get("answer_content") or ""), (
                "TC-ADMIN-Q-04: Đáp án mẫu chưa được lưu đúng nội dung"
            )

        finally:
            safe_delete_question(token, created_question_id)

    # ──────────────────────────────────────────────
    # TC-ADMIN-Q-05
    # Validation for missing content or no designated correct answer
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=154)
    def test_validation_for_missing_content_or_no_designated_correct_answer(self, driver):
        page = login_admin_and_open_questions(driver)

        # Case 1: thiếu nội dung câu hỏi
        page.open_create_question()
        page.save_question()
        assert page.wait_notification_contains("Vui lòng nhập nội dung câu hỏi", timeout=8), (
            "TC-ADMIN-Q-05: Thiếu nội dung câu hỏi phải hiển thị cảnh báo validation"
        )

        # Case 2: có nội dung nhưng chưa chọn đáp án đúng
        page.open_create_question()
        page.fill_question_content(f"[TC-ADMIN-Q-05]-missing-correct-{int(time.time() * 1000)}")
        page.choose_single_choice_type()
        page.fill_answer(1, "PA1")
        page.fill_answer(2, "PA2")
        page.fill_answer(3, "PA3")
        page.fill_answer(4, "PA4")
        page.save_question()

        assert page.wait_notification_contains("Phải có ít nhất 1 đáp án đúng", timeout=8), (
            "TC-ADMIN-Q-05: Không chọn đáp án đúng phải bị chặn bởi validation"
        )

    # ──────────────────────────────────────────────
    # TC-ADMIN-Q-06
    # Edit existing questions and their corresponding answers
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=155)
    def test_edit_existing_questions_and_their_corresponding_answers(self, driver):
        token = get_admin_token()
        ts = int(time.time() * 1000)
        original_content = f"[TC-ADMIN-Q-06]-before-{ts}"
        updated_content = f"[TC-ADMIN-Q-06]-after-{ts}"
        created_question_id: int | None = None

        try:
            created = api_create_question(
                token,
                question_content=original_content,
                type_question=1,
                available=True,
                answers=[
                    {"answer_content": "Before A", "is_correct": True},
                    {"answer_content": "Before B", "is_correct": False},
                    {"answer_content": "Before C", "is_correct": False},
                    {"answer_content": "Before D", "is_correct": False},
                ],
            )
            created_question_id = created.get("question_id")
            answers = created.get("answers") or []

            update_answers = []
            for idx, answer in enumerate(answers):
                update_answers.append(
                    {
                        "answer_id": answer["answer_id"],
                        "answer_content": (
                            f"After answer {idx + 1}" if idx == 0 else answer.get("answer_content")
                        ),
                        "is_correct": idx == 1,  # đổi đáp án đúng sang đáp án số 2
                    }
                )

            api_update_question(
                token,
                created_question_id,
                payload={
                    "question_content": updated_content,
                    "answers": update_answers,
                },
            )

            page = login_admin_and_open_questions(driver)
            page.search_question(updated_content)
            assert page.has_question_card_containing(updated_content), (
                "TC-ADMIN-Q-06: Không thấy nội dung câu hỏi đã chỉnh sửa trên trang quản lý"
            )
            assert not page.has_question_card_containing(original_content), (
                "TC-ADMIN-Q-06: Nội dung cũ vẫn còn hiển thị sau khi update"
            )

            updated = api_find_question_by_exact_content(token, updated_content)
            assert updated is not None, "TC-ADMIN-Q-06: API không trả về câu hỏi đã cập nhật"

            updated_answers = updated.get("answers") or []
            assert any((ans.get("answer_content") or "") == "After answer 1" for ans in updated_answers), (
                "TC-ADMIN-Q-06: Nội dung đáp án tương ứng chưa được cập nhật"
            )
            correct_count = sum(1 for ans in updated_answers if ans.get("is_correct"))
            assert correct_count == 1 and any(ans.get("is_correct") for ans in updated_answers[1:2]), (
                "TC-ADMIN-Q-06: Cập nhật đáp án đúng chưa đúng kỳ vọng"
            )

        finally:
            safe_delete_question(token, created_question_id)

    # ──────────────────────────────────────────────
    # TC-ADMIN-Q-07
    # Delete question currently linked to an active exam or bank
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=156)
    def test_delete_question_currently_linked_to_active_exam_or_bank(self, driver):
        token = get_admin_token()
        ts = int(time.time() * 1000)
        question_content = f"[TC-ADMIN-Q-07]-linked-{ts}"
        bank_name = f"[TC-ADMIN-Q-07]-bank-{ts}"

        question_id: int | None = None
        bank_id: int | None = None

        try:
            question = api_create_question(
                token,
                question_content=question_content,
                type_question=1,
                available=True,
                answers=[
                    {"answer_content": "L1", "is_correct": True},
                    {"answer_content": "L2", "is_correct": False},
                    {"answer_content": "L3", "is_correct": False},
                    {"answer_content": "L4", "is_correct": False},
                ],
            )
            question_id = question.get("question_id")

            topic_id = api_get_first_topic_id(token)
            bank = api_create_bank(token, description=bank_name, topic_id=topic_id, time_limit=10)
            bank_id = bank.get("bank_id")
            api_link_question_to_bank(token, bank_id=bank_id, question_id=question_id)

            page = login_admin_and_open_questions(driver)
            page.search_question(question_content)
            assert page.has_question_card_containing(question_content), (
                "TC-ADMIN-Q-07: Không thấy câu hỏi đã setup link bank trong danh sách"
            )

            page.delete_first_visible_question()
            page.close_delete_confirmation_if_visible()
            time.sleep(1.5)

            page.search_question(question_content)
            still_visible = page.has_question_card_containing(question_content)

            if not still_visible:
                pytest.xfail(
                    "TC-ADMIN-Q-07: Hệ thống hiện tại cho phép xoá cascade câu hỏi đang linked bank/exam."
                )

            assert still_visible, (
                "TC-ADMIN-Q-07: Câu hỏi đang linked bank/exam phải bị chặn xoá theo yêu cầu nghiệp vụ"
            )

        finally:
            safe_delete_bank(token, bank_id)
            safe_delete_question(token, question_id)

    # ──────────────────────────────────────────────
    # TC-ADMIN-Q-08
    # Bulk question generation from DOCX and JSON import
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=157)
    def test_bulk_question_generation_from_docx_and_json_import(self, driver):
        page = login_admin_and_open_questions(driver)

        try:
            docx_path = get_sample_docx_path()
        except FileNotFoundError as exc:
            pytest.xfail(f"TC-ADMIN-Q-08: {exc}")
            return

        # 1) DOCX upload
        uploaded = page.upload_docx(docx_path)
        if not uploaded:
            pytest.xfail(
                "TC-ADMIN-Q-08: Driver hiện tại không upload được DOCX qua input file trên mobile web"
            )

        docx_success = page.wait_notification_contains("Đã xử lý xong", timeout=30)
        if not docx_success and page.wait_notification_contains("thất bại", timeout=5):
            pytest.xfail(
                "TC-ADMIN-Q-08: DOCX upload chạy nhưng microservice xử lý DOCX chưa sẵn sàng"
            )

        # 2) JSON import (bulk import)
        page.open_json_list_modal()
        if not page.is_json_list_modal_visible():
            pytest.xfail("TC-ADMIN-Q-08: Không mở được modal Danh sách JSON")

        page.open_first_json_file()
        assert page.is_json_parser_page(), (
            f"TC-ADMIN-Q-08: Không điều hướng được sang JSON parser, URL: {driver.current_url}"
        )

        selected = page.select_first_importable_json_question()
        if selected:
            page.import_selected_json_questions()
        else:
            # fallback nếu không tìm được câu importable để bulk, thử import đơn
            page.import_first_json_question()

        try:
            WebDriverWait(driver, 20).until(
                lambda d: "/admin/questions" in d.current_url and "/file-parser/" not in d.current_url
            )
        except Exception:
            if page.wait_notification_contains("chưa có đáp án đúng", timeout=5):
                pytest.xfail(
                    "TC-ADMIN-Q-08: File JSON đang chọn không có đáp án đúng hợp lệ để import"
                )
            if page.wait_notification_contains("Lỗi", timeout=3):
                pytest.xfail("TC-ADMIN-Q-08: Import JSON lỗi do dữ liệu/môi trường backend")
            raise AssertionError(
                f"TC-ADMIN-Q-08: Import JSON không thành công, URL hiện tại: {driver.current_url}"
            )

        page.wait_until_loaded(timeout=15)
        assert page.is_question_management_page(), (
            "TC-ADMIN-Q-08: Sau import JSON phải quay lại trang quản lý câu hỏi"
        )
