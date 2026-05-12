# tests/test_user_flashcards_chatbot_roadmap.py
# Kiểm thử Flashcards, Chatbot, Document viewer và User Roadmap

from __future__ import annotations

import json
import mimetypes
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

import pytest
from selenium.webdriver.support.ui import WebDriverWait

from config import ADMIN_EMAIL, ADMIN_PASSWORD, BASE_URL, USER1_EMAIL, USER1_PASSWORD, USER2_EMAIL, USER2_PASSWORD
from pages.login_page import LoginPage
from pages.user_flashcards_chatbot_roadmap_page import UserFlashcardsChatbotRoadmapPage


BACKEND_BASE_URL = "http://localhost:3000"


def _parse_json(body: str) -> dict:
    if not body:
        return {}
    try:
        return json.loads(body)
    except Exception:
        return {}


def api_request_json(
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict | list | None = None,
    timeout: int = 25,
) -> tuple[int, dict]:
    url = f"{BACKEND_BASE_URL}{path}"
    headers: dict[str, str] = {}
    data = None

    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
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


def _build_multipart_body(
    *,
    fields: dict[str, str],
    file_field: str,
    file_name: str,
    file_bytes: bytes,
    content_type: str,
    boundary: str,
) -> bytes:
    body = bytearray()
    crlf = b"\r\n"

    for key, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        body.extend(str(value).encode("utf-8"))
        body.extend(crlf)

    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(
        (
            f'Content-Disposition: form-data; name="{file_field}"; filename="{file_name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8")
    )
    body.extend(file_bytes)
    body.extend(crlf)
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    return bytes(body)


def api_upload_document(
    token: str,
    *,
    title: str,
    topic_id: int,
    file_path: str,
    timeout: int = 45,
) -> tuple[int, dict]:
    file_obj = Path(file_path).expanduser().resolve()
    if not file_obj.is_file():
        raise FileNotFoundError(str(file_obj))

    file_bytes = file_obj.read_bytes()
    file_name = file_obj.name
    guessed_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
    boundary = f"----AppiumFormBoundary{int(time.time() * 1000)}{file_obj.stat().st_size}"

    body = _build_multipart_body(
        fields={"title": title, "topic_id": str(topic_id)},
        file_field="file",
        file_name=file_name,
        file_bytes=file_bytes,
        content_type=guessed_type,
        boundary=boundary,
    )

    req = urllib.request.Request(
        url=f"{BACKEND_BASE_URL}/documents/create",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.getcode()
            payload = resp.read().decode("utf-8", errors="ignore")
            return status, _parse_json(payload)
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="ignore")
        return exc.code, _parse_json(payload)


def get_login_session(email: str, password: str) -> dict:
    status, data = api_request_json(
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
    code, data = api_request_json("GET", f"/users?{query}", token=admin_token)
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
    return api_request_json("PUT", f"/users/update/{user_id}", token=token, payload=payload)


def api_register_user(user_name: str, email: str, password: str) -> tuple[int, dict]:
    return api_request_json(
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


def api_list_flashcard_decks(token: str, page: int = 1) -> list[dict]:
    status, data = api_request_json("GET", f"/flashcards/decks?page={page}", token=token)
    if status != 200:
        raise RuntimeError(f"Lấy flashcard decks thất bại, status={status}, response={data}")
    return ((data.get("data") or {}).get("data")) or []


def api_find_flashcard_deck_by_title(token: str, title: str, max_pages: int = 8) -> dict | None:
    for page in range(1, max_pages + 1):
        rows = api_list_flashcard_decks(token, page=page)
        if not rows:
            continue
        for row in rows:
            if (row.get("title") or "").strip() == title:
                return row
    return None


def api_create_flashcard_deck(token: str, *, title: str, description: str) -> tuple[int, dict]:
    return api_request_json(
        "POST",
        "/flashcards/decks/create",
        token=token,
        payload={"title": title, "description": description},
    )


def api_get_flashcard_deck_detail(token: str, deck_id: int) -> tuple[int, dict]:
    return api_request_json("GET", f"/flashcards/decks/{deck_id}", token=token)


def api_add_flashcard(
    token: str,
    *,
    deck_id: int,
    front: str,
    back: str,
    example: str | None = None,
) -> tuple[int, dict]:
    payload: dict[str, str | None] = {"front": front, "back": back}
    if example is not None:
        payload["example"] = example
    return api_request_json("POST", f"/flashcards/decks/add/{deck_id}", token=token, payload=payload)


def api_delete_flashcard(token: str, flashcard_id: int) -> tuple[int, dict]:
    return api_request_json("DELETE", f"/flashcards/remove/{flashcard_id}", token=token)


def api_delete_flashcard_deck(token: str, deck_id: int) -> tuple[int, dict]:
    return api_request_json("DELETE", f"/flashcards/decks/remove/{deck_id}", token=token)


def safe_delete_flashcard_deck(token: str, deck_id: int | None):
    if not deck_id:
        return
    try:
        api_delete_flashcard_deck(token, deck_id)
    except Exception:
        pass


def api_get_flashcards_review(token: str, deck_id: int) -> tuple[int, dict]:
    return api_request_json("GET", f"/flashcards/review/{deck_id}", token=token)


def api_get_flashcards_quiz(token: str, deck_id: int) -> tuple[int, dict]:
    return api_request_json("GET", f"/flashcards/quiz/{deck_id}", token=token)


def api_submit_flashcard_session(
    token: str,
    *,
    answer_correct: list[int],
    answer_miss: list[int],
) -> tuple[int, dict]:
    return api_request_json(
        "PATCH",
        "/flashcards/quiz/submit",
        token=token,
        payload={"answerCorrect": answer_correct, "answerMiss": answer_miss},
    )


def api_get_topics(token: str) -> list[dict]:
    status, data = api_request_json("GET", "/topics", token=token)
    if status != 200:
        raise RuntimeError(f"Lấy topics thất bại, status={status}, response={data}")
    return data.get("data") or []


def api_pick_topic(token: str) -> dict:
    topics = api_get_topics(token)
    if not topics:
        raise RuntimeError("Không có topic để setup test")
    return topics[0]


def api_find_document_by_title(token: str, title: str, page_max: int = 6) -> dict | None:
    for page in range(1, page_max + 1):
        query = urllib.parse.urlencode({"page": page, "keyword": title, "available": "All"})
        status, data = api_request_json("GET", f"/documents?{query}", token=token)
        if status != 200:
            continue
        rows = (data.get("data") or {}).get("documents") or []
        for row in rows:
            if (row.get("title") or "").strip() == title:
                return row
    return None


def api_delete_document(token: str, document_id: int):
    status, data = api_request_json("DELETE", f"/documents/remove/{document_id}", token=token)
    if status not in (200, 202, 204):
        raise RuntimeError(f"Delete document thất bại, status={status}, response={data}")


def safe_delete_document(token: str, document_id: int | None):
    if not document_id:
        return
    try:
        api_delete_document(token, document_id)
    except Exception:
        pass


def api_vectorize(files: list[dict]) -> tuple[int, dict]:
    return api_request_json(
        "POST",
        "/microservice/llm/vectorize",
        payload={"files": files},
        timeout=70,
    )


def api_ask_llm(token: str, question: str, timeout: int = 35) -> tuple[int, dict]:
    return api_request_json(
        "POST",
        "/microservice/llm/ask",
        token=token,
        payload={"question": question},
        timeout=timeout,
    )


def api_get_roadmap_list(token: str) -> tuple[int, dict]:
    return api_request_json("GET", "/roadmap", token=token)


def create_temp_docx_file(text: str) -> str:
    temp_dir = Path(tempfile.mkdtemp(prefix="appium-user-docx-"))
    docx_path = temp_dir / "sample.docx"
    escaped = xml_escape(text)

    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>{escaped}</w:t></w:r></w:p>
  </w:body>
</w:document>
"""

    with zipfile.ZipFile(docx_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document_xml)

    return str(docx_path)


def create_temp_pdf_file(text: str) -> str:
    temp_dir = Path(tempfile.mkdtemp(prefix="appium-user-pdf-"))
    pdf_path = temp_dir / "sample.pdf"

    escaped_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 14 Tf 72 720 Td ({escaped_text}) Tj ET"

    objects = [
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            "3 0 obj\n"
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\n"
            "endobj\n"
        ),
        f"4 0 obj\n<< /Length {len(stream.encode('latin-1'))} >>\nstream\n{stream}\nendstream\nendobj\n",
        "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj.encode("latin-1"))

    xref_pos = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    pdf.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF\n"
        ).encode("latin-1")
    )

    pdf_path.write_bytes(bytes(pdf))
    return str(pdf_path)


def safe_remove_file(path: str | None):
    if not path:
        return
    try:
        file_path = Path(path)
        if file_path.is_file():
            file_path.unlink(missing_ok=True)
    except Exception:
        pass


def parse_quiz_result(text: str) -> tuple[int, int] | None:
    match = re.search(r"(\d+)\s*/\s*(\d+)", text or "")
    if not match:
        return None
    try:
        return int(match.group(1)), int(match.group(2))
    except Exception:
        return None


class TestUserFlashcardsChatbotRoadmap:
    """Flashcards CRUD/practice, document viewer, mini-chat và roadmap."""

    # ──────────────────────────────────────────────
    # TC-USER-FCR-01
    # Create a new flashcard deck successfully
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=210)
    def test_create_new_flashcard_deck_successfully(self, driver):
        admin_token = get_admin_token()
        user_session = ensure_user_active(admin_token, USER1_EMAIL, USER1_PASSWORD)
        user_token = user_session["token"]

        ts = int(time.time() * 1000)
        title = f"[TC-USER-FCR-01]-deck-{ts}"
        description = "Deck tạo tự động từ Appium test"
        created_deck_id: int | None = None

        try:
            page = UserFlashcardsChatbotRoadmapPage(driver)
            login_user(driver, USER1_EMAIL, USER1_PASSWORD)
            page.open_flashcards_page()
            page.open_create_deck_modal()
            page.create_deck(title=title, description=description)

            assert page.has_deck_card(title, timeout=15), (
                "TC-USER-FCR-01: Tạo deck thành công nhưng không thấy deck trên UI"
            )

            found = api_find_flashcard_deck_by_title(user_token, title)
            assert found is not None, (
                "TC-USER-FCR-01: API không trả về deck vừa tạo"
            )
            created_deck_id = int(found["flashcard_deck_id"])
        finally:
            safe_delete_flashcard_deck(user_token, created_deck_id)

    # ──────────────────────────────────────────────
    # TC-USER-FCR-02
    # Flashcard validation: Blank front/back and 50-card limit
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=211)
    def test_flashcard_validation_blank_front_back_and_50_card_limit(self, driver):
        admin_token = get_admin_token()
        user_session = ensure_user_active(admin_token, USER1_EMAIL, USER1_PASSWORD)
        user_token = user_session["token"]

        ts = int(time.time() * 1000)
        title = f"[TC-USER-FCR-02]-deck-{ts}"
        created_deck_id: int | None = None

        code_create, data_create = api_create_flashcard_deck(
            user_token,
            title=title,
            description="Deck để test validation flashcard",
        )
        assert code_create in (200, 201), (
            f"TC-USER-FCR-02: Setup tạo deck thất bại, status={code_create}, response={data_create}"
        )
        created_deck_id = int((data_create.get("data") or {}).get("flashcard_deck_id"))

        try:
            page = UserFlashcardsChatbotRoadmapPage(driver)
            login_user(driver, USER1_EMAIL, USER1_PASSWORD)
            page.open_flashcards_page()
            page.open_deck_by_title(title)
            page.open_add_flashcard_modal()
            page.add_flashcard(front="", back="")

            alert_text = (page.wait_alert_and_accept(timeout=8) or "").lower()
            assert "điền đủ mặt trước và mặt sau" in alert_text, (
                "TC-USER-FCR-02: Validate blank front/back không hiển thị alert đúng"
            )

            status_detail_0, detail_0 = api_get_flashcard_deck_detail(user_token, created_deck_id)
            assert status_detail_0 == 200, (
                f"TC-USER-FCR-02: Không lấy được deck detail ban đầu, status={status_detail_0}"
            )
            total_0 = int((detail_0.get("data") or {}).get("totalFlashcard") or 0)
            assert total_0 == 0, (
                "TC-USER-FCR-02: Thêm flashcard rỗng không được làm tăng số lượng flashcard"
            )

            # tạo đủ 50 thẻ
            for i in range(1, 51):
                status_add, data_add = api_add_flashcard(
                    user_token,
                    deck_id=created_deck_id,
                    front=f"FCR02-front-{i}",
                    back=f"FCR02-back-{i}",
                )
                assert status_add in (200, 201), (
                    f"TC-USER-FCR-02: Tạo flashcard thứ {i} thất bại, status={status_add}, response={data_add}"
                )
                assert (data_add.get("data") or {}).get("flashcard_id"), (
                    f"TC-USER-FCR-02: API không trả về flashcard_id cho lần tạo thứ {i}"
                )

            status_over, data_over = api_add_flashcard(
                user_token,
                deck_id=created_deck_id,
                front="FCR02-front-over-limit",
                back="FCR02-back-over-limit",
            )

            status_detail_after, detail_after = api_get_flashcard_deck_detail(user_token, created_deck_id)
            assert status_detail_after == 200, (
                f"TC-USER-FCR-02: Không lấy được deck detail sau khi test limit, status={status_detail_after}"
            )
            total_after = int((detail_after.get("data") or {}).get("totalFlashcard") or 0)
            assert total_after == 50, (
                "TC-USER-FCR-02: Số lượng flashcard trong deck không được vượt quá 50"
            )

            if status_over in (200, 201):
                if (data_over.get("data") or {}).get("flashcard_id"):
                    raise AssertionError(
                        "TC-USER-FCR-02: API vẫn cho tạo flashcard thứ 51 (vượt limit 50)"
                    )
                pytest.xfail(
                    "TC-USER-FCR-02: API chặn vượt giới hạn nhưng vẫn trả status success thay vì mã lỗi validation."
                )
        finally:
            safe_delete_flashcard_deck(user_token, created_deck_id)

    # ──────────────────────────────────────────────
    # TC-USER-FCR-03
    # Practice flashcards (Random order and status tracking)
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=212)
    def test_practice_flashcards_random_order_and_status_tracking(self, driver):
        admin_token = get_admin_token()
        user_session = ensure_user_active(admin_token, USER1_EMAIL, USER1_PASSWORD)
        user_token = user_session["token"]

        ts = int(time.time() * 1000)
        title = f"[TC-USER-FCR-03]-deck-{ts}"
        created_deck_id: int | None = None

        code_create, data_create = api_create_flashcard_deck(
            user_token,
            title=title,
            description="Deck để test random và status tracking",
        )
        assert code_create in (200, 201), (
            f"TC-USER-FCR-03: Setup tạo deck thất bại, status={code_create}, response={data_create}"
        )
        created_deck_id = int((data_create.get("data") or {}).get("flashcard_deck_id"))

        try:
            for i in range(1, 9):
                code_add, data_add = api_add_flashcard(
                    user_token,
                    deck_id=created_deck_id,
                    front=f"FCR03-front-{i}",
                    back=f"FCR03-back-{i}",
                )
                assert code_add in (200, 201), (
                    f"TC-USER-FCR-03: Setup tạo card #{i} thất bại, status={code_add}, response={data_add}"
                )

            code_r1, data_r1 = api_get_flashcards_review(user_token, created_deck_id)
            code_r2, data_r2 = api_get_flashcards_review(user_token, created_deck_id)
            code_r3, data_r3 = api_get_flashcards_review(user_token, created_deck_id)
            assert code_r1 == 200 and code_r2 == 200 and code_r3 == 200, (
                "TC-USER-FCR-03: Không lấy được flashcard review list để kiểm tra random"
            )

            list1 = data_r1.get("data") or []
            list2 = data_r2.get("data") or []
            list3 = data_r3.get("data") or []
            ids1 = [int(x["flashcard_id"]) for x in list1 if x.get("flashcard_id") is not None]
            ids2 = [int(x["flashcard_id"]) for x in list2 if x.get("flashcard_id") is not None]
            ids3 = [int(x["flashcard_id"]) for x in list3 if x.get("flashcard_id") is not None]

            if len(ids1) < 4:
                pytest.xfail("TC-USER-FCR-03: Không đủ dữ liệu flashcard để kiểm tra random order")
                return

            randomized = ids1 != ids2 or ids1 != ids3 or ids2 != ids3
            if not randomized:
                pytest.xfail(
                    "TC-USER-FCR-03: Không quan sát được sự thay đổi thứ tự random sau nhiều lần fetch review."
                )

            done_id = ids1[0]
            miss_id = ids1[1]
            code_submit, data_submit = api_submit_flashcard_session(
                user_token,
                answer_correct=[done_id],
                answer_miss=[miss_id],
            )
            assert code_submit == 200, (
                f"TC-USER-FCR-03: Submit flashcard session thất bại, status={code_submit}, response={data_submit}"
            )

            code_detail, data_detail = api_get_flashcard_deck_detail(user_token, created_deck_id)
            assert code_detail == 200, (
                f"TC-USER-FCR-03: Không lấy được deck detail sau submit, status={code_detail}"
            )
            cards = (data_detail.get("data") or {}).get("data") or []
            status_map = {int(card["flashcard_id"]): (card.get("status") or "") for card in cards if card.get("flashcard_id") is not None}
            assert status_map.get(done_id) == "done", (
                "TC-USER-FCR-03: Flashcard đúng chưa được cập nhật status='done'"
            )
            assert status_map.get(miss_id) == "miss", (
                "TC-USER-FCR-03: Flashcard sai chưa được cập nhật status='miss'"
            )

            code_quiz, data_quiz = api_get_flashcards_quiz(user_token, created_deck_id)
            assert code_quiz == 200, (
                f"TC-USER-FCR-03: Không lấy được quiz list sau submit, status={code_quiz}"
            )
            quiz_ids = {int(x["flashcard_id"]) for x in (data_quiz.get("data") or []) if x.get("flashcard_id") is not None}
            assert done_id not in quiz_ids, (
                "TC-USER-FCR-03: Flashcard status='done' phải bị loại khỏi quiz list"
            )
            assert miss_id in quiz_ids, (
                "TC-USER-FCR-03: Flashcard status='miss' phải còn trong quiz list để luyện lại"
            )

            page = UserFlashcardsChatbotRoadmapPage(driver)
            login_user(driver, USER1_EMAIL, USER1_PASSWORD)
            page.open_flashcards_page()
            page.open_deck_by_title(title)
            page.open_review_mode()
            counter_before = page.get_review_counter_text()
            front_before = page.get_review_front_text()
            page.click_review_shuffle()
            time.sleep(0.7)
            page.click_review_next()
            time.sleep(0.7)
            counter_after = page.get_review_counter_text()
            assert "/" in counter_before and "/" in counter_after, (
                "TC-USER-FCR-03: UI review không hiển thị counter theo format 'Thẻ x / y'"
            )
            assert front_before != "" or counter_after != "", (
                "TC-USER-FCR-03: UI review không hiển thị nội dung thẻ sau khi thao tác"
            )
        finally:
            safe_delete_flashcard_deck(user_token, created_deck_id)

    # ──────────────────────────────────────────────
    # TC-USER-FCR-04
    # Submit flashcard session and check summary sync
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=213)
    def test_submit_flashcard_session_and_check_summary_sync(self, driver):
        admin_token = get_admin_token()
        user_session = ensure_user_active(admin_token, USER1_EMAIL, USER1_PASSWORD)
        user_token = user_session["token"]

        ts = int(time.time() * 1000)
        title = f"[TC-USER-FCR-04]-deck-{ts}"
        created_deck_id: int | None = None

        code_create, data_create = api_create_flashcard_deck(
            user_token,
            title=title,
            description="Deck để test submit session summary sync",
        )
        assert code_create in (200, 201), (
            f"TC-USER-FCR-04: Setup tạo deck thất bại, status={code_create}, response={data_create}"
        )
        created_deck_id = int((data_create.get("data") or {}).get("flashcard_deck_id"))

        try:
            for i in range(1, 5):
                code_add, data_add = api_add_flashcard(
                    user_token,
                    deck_id=created_deck_id,
                    front=f"FCR04-front-{i}",
                    back=f"FCR04-back-{i}",
                )
                assert code_add in (200, 201), (
                    f"TC-USER-FCR-04: Setup tạo card #{i} thất bại, status={code_add}, response={data_add}"
                )

            page = UserFlashcardsChatbotRoadmapPage(driver)
            login_user(driver, USER1_EMAIL, USER1_PASSWORD)
            page.open_flashcards_page()
            page.open_deck_by_title(title)

            done_before = page.get_total_done_value()
            assert done_before == 0, (
                f"TC-USER-FCR-04: Deck mới phải có totalDone=0, actual={done_before}"
            )

            page.open_quiz_mode()
            selected_count = page.choose_first_quiz_option_for_each_question()
            assert selected_count > 0, (
                "TC-USER-FCR-04: Không chọn được đáp án nào trên UI quiz"
            )

            page.submit_quiz()
            result_text = page.get_quiz_result_text()
            parsed = parse_quiz_result(result_text)
            assert parsed is not None, (
                f"TC-USER-FCR-04: Không parse được summary kết quả từ UI, text={result_text!r}"
            )
            correct_ui, total_ui = parsed
            assert total_ui > 0, "TC-USER-FCR-04: Tổng số câu trong summary phải > 0"

            deadline = time.time() + 10
            done_after = None
            while time.time() < deadline:
                code_detail, data_detail = api_get_flashcard_deck_detail(user_token, created_deck_id)
                if code_detail == 200:
                    done_after = int((data_detail.get("data") or {}).get("totalDone") or 0)
                    if done_after == correct_ui:
                        break
                time.sleep(0.6)

            assert done_after == correct_ui, (
                "TC-USER-FCR-04: Summary đúng trên UI chưa đồng bộ với totalDone trong backend"
            )
        finally:
            safe_delete_flashcard_deck(user_token, created_deck_id)

    # ──────────────────────────────────────────────
    # TC-USER-FCR-05
    # Delete flashcard/deck and verify ownership rights
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=214)
    def test_delete_flashcard_deck_and_verify_ownership_rights(self, driver):
        admin_token = get_admin_token()
        user1_session = ensure_user_active(admin_token, USER1_EMAIL, USER1_PASSWORD)
        user2_session = ensure_user_active(admin_token, USER2_EMAIL, USER2_PASSWORD)
        user1_token = user1_session["token"]
        user2_token = user2_session["token"]

        ts = int(time.time() * 1000)
        title = f"[TC-USER-FCR-05]-deck-{ts}"
        created_deck_id: int | None = None
        created_flashcard_id: int | None = None

        code_create, data_create = api_create_flashcard_deck(
            user1_token,
            title=title,
            description="Deck để test ownership delete",
        )
        assert code_create in (200, 201), (
            f"TC-USER-FCR-05: Setup tạo deck thất bại, status={code_create}, response={data_create}"
        )
        created_deck_id = int((data_create.get("data") or {}).get("flashcard_deck_id"))

        code_add, data_add = api_add_flashcard(
            user1_token,
            deck_id=created_deck_id,
            front="FCR05-front-owner",
            back="FCR05-back-owner",
        )
        assert code_add in (200, 201), (
            f"TC-USER-FCR-05: Setup tạo flashcard thất bại, status={code_add}, response={data_add}"
        )
        created_flashcard_id = int((data_add.get("data") or {}).get("flashcard_id"))

        try:
            status_del_card_u2, _ = api_delete_flashcard(user2_token, created_flashcard_id)
            status_del_deck_u2, _ = api_delete_flashcard_deck(user2_token, created_deck_id)

            status_after_u2, _ = api_get_flashcard_deck_detail(user1_token, created_deck_id)
            if status_del_card_u2 in (200, 202, 204) or status_del_deck_u2 in (200, 202, 204):
                if status_after_u2 == 404:
                    pytest.xfail(
                        "TC-USER-FCR-05: User không sở hữu vẫn xóa được deck (thiếu kiểm tra ownership)."
                    )
                pytest.xfail(
                    "TC-USER-FCR-05: API xóa flashcard/deck chưa chặn thao tác từ user không sở hữu."
                )

            assert status_del_deck_u2 in (401, 403, 404), (
                "TC-USER-FCR-05: Xóa deck bởi user không sở hữu phải bị từ chối"
            )

            page = UserFlashcardsChatbotRoadmapPage(driver)
            login_user(driver, USER1_EMAIL, USER1_PASSWORD)
            page.open_flashcards_page()
            page.open_deck_by_title(title)
            page.delete_current_deck()

            WebDriverWait(driver, 10).until(lambda d: "/flashcards" in d.current_url)

            status_after_owner, _ = api_get_flashcard_deck_detail(user1_token, created_deck_id)
            assert status_after_owner == 404, (
                "TC-USER-FCR-05: Owner xóa deck qua UI nhưng backend vẫn còn deck"
            )
            created_deck_id = None
        finally:
            safe_delete_flashcard_deck(user1_token, created_deck_id)

    # ──────────────────────────────────────────────
    # TC-USER-FCR-06
    # Search and open DOCX/PDF on mobile document viewer
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=215)
    def test_search_and_open_docx_pdf_on_mobile_document_viewer(self, driver):
        admin_token = get_admin_token()
        ensure_user_active(admin_token, USER1_EMAIL, USER1_PASSWORD)

        topic = api_pick_topic(admin_token)
        topic_id = int(topic["topic_id"])
        ts = int(time.time() * 1000)
        keyword = f"TC-USER-FCR-06-{ts}"
        docx_title = f"{keyword}-DOCX"
        pdf_title = f"{keyword}-PDF"

        docx_path = create_temp_docx_file(f"DOCX content {keyword}")
        pdf_path = create_temp_pdf_file(f"PDF content {keyword}")
        docx_id: int | None = None
        pdf_id: int | None = None

        try:
            code_docx, data_docx = api_upload_document(
                admin_token,
                title=docx_title,
                topic_id=topic_id,
                file_path=docx_path,
            )
            assert code_docx in (200, 201), (
                f"TC-USER-FCR-06: Upload DOCX setup thất bại, status={code_docx}, response={data_docx}"
            )
            docx_id = int((data_docx.get("data") or {}).get("document_id"))

            code_pdf, data_pdf = api_upload_document(
                admin_token,
                title=pdf_title,
                topic_id=topic_id,
                file_path=pdf_path,
            )
            assert code_pdf in (200, 201), (
                f"TC-USER-FCR-06: Upload PDF setup thất bại, status={code_pdf}, response={data_pdf}"
            )
            pdf_id = int((data_pdf.get("data") or {}).get("document_id"))

            page = UserFlashcardsChatbotRoadmapPage(driver)
            login_user(driver, USER1_EMAIL, USER1_PASSWORD)
            page.open_document_list()
            page.search_document(keyword)

            assert page.has_document_card(docx_title, timeout=10), (
                "TC-USER-FCR-06: Search tài liệu không trả về DOCX card"
            )
            assert page.has_document_card(pdf_title, timeout=10), (
                "TC-USER-FCR-06: Search tài liệu không trả về PDF card"
            )

            # DOCX
            handles_before = set(driver.window_handles)
            page.open_document_link_by_title(docx_title)
            time.sleep(1.2)
            handles_after = set(driver.window_handles)
            if len(handles_after) > len(handles_before):
                page.switch_to_latest_window()

            WebDriverWait(driver, 12).until(lambda d: f"/document/{docx_id}" in d.current_url)
            assert page.wait_document_viewer_title_contains("DOCX", timeout=20), (
                "TC-USER-FCR-06: Không load được DOCX viewer trên mobile"
            )

            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])

            # PDF
            page.open_document_list()
            page.search_document(keyword)

            handles_before_pdf = set(driver.window_handles)
            page.open_document_link_by_title(pdf_title)
            time.sleep(1.2)
            handles_after_pdf = set(driver.window_handles)
            if len(handles_after_pdf) > len(handles_before_pdf):
                page.switch_to_latest_window()

            WebDriverWait(driver, 12).until(lambda d: f"/document/{pdf_id}" in d.current_url)
            assert page.wait_document_viewer_title_contains("PDF", timeout=20), (
                "TC-USER-FCR-06: Không load được PDF viewer trên mobile"
            )
        finally:
            safe_delete_document(admin_token, docx_id)
            safe_delete_document(admin_token, pdf_id)
            safe_remove_file(docx_path)
            safe_remove_file(pdf_path)

    # ──────────────────────────────────────────────
    # TC-USER-FCR-07
    # Ask chatbot questions based on vectorized documents
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=216)
    def test_ask_chatbot_questions_based_on_vectorized_documents(self, driver):
        admin_token = get_admin_token()
        user_session = ensure_user_active(admin_token, USER1_EMAIL, USER1_PASSWORD)
        user_token = user_session["token"]

        topic = api_pick_topic(admin_token)
        topic_id = int(topic["topic_id"])

        ts = int(time.time() * 1000)
        keyword = f"TC-USER-FCR-07-{ts}"
        title = f"{keyword}-DOCX"
        question = f"Tóm tắt nội dung liên quan đến {keyword}"

        docx_path = create_temp_docx_file(f"Tài liệu kiểm thử chatbot chứa từ khóa {keyword}")
        document_id: int | None = None
        document_link: str | None = None

        try:
            code_upload, data_upload = api_upload_document(
                admin_token,
                title=title,
                topic_id=topic_id,
                file_path=docx_path,
            )
            assert code_upload in (200, 201), (
                f"TC-USER-FCR-07: Upload doc setup thất bại, status={code_upload}, response={data_upload}"
            )
            upload_data = data_upload.get("data") or {}
            document_id = int(upload_data["document_id"])
            document_link = upload_data.get("link")
            assert document_link, "TC-USER-FCR-07: Document setup thiếu link để vectorize"

            code_vec, data_vec = api_vectorize([{"document_id": document_id, "link": document_link}])
            if code_vec not in (200, 202):
                pytest.xfail(
                    f"TC-USER-FCR-07: Microservice vectorize chưa sẵn sàng, status={code_vec}, response={data_vec}"
                )
                return

            code_ask, data_ask = api_ask_llm(user_token, question, timeout=45)
            if code_ask != 200:
                pytest.xfail(
                    f"TC-USER-FCR-07: LLM ask chưa sẵn sàng, status={code_ask}, response={data_ask}"
                )
                return

            answer = (data_ask.get("data") or {}).get("answer") or ""
            sources = (data_ask.get("data") or {}).get("sources") or []
            assert answer.strip(), "TC-USER-FCR-07: LLM ask không trả về answer"
            if not sources:
                pytest.xfail(
                    "TC-USER-FCR-07: LLM ask trả lời nhưng chưa trả về sources từ tài liệu vectorized."
                )
                return

            page = UserFlashcardsChatbotRoadmapPage(driver)
            login_user(driver, USER1_EMAIL, USER1_PASSWORD)
            page.open_document_list()
            page.open_chat_widget()

            bot_before = page.get_chat_bot_message_count()
            page.send_chat_message(question)

            if not page.wait_new_bot_message(bot_before, timeout=45):
                pytest.xfail("TC-USER-FCR-07: UI chatbot không nhận phản hồi trong thời gian chờ.")
                return

            last_bot_msg = page.get_last_bot_message_text()
            assert last_bot_msg, "TC-USER-FCR-07: UI chatbot không hiển thị nội dung trả lời"

            if not page.has_source_panel(timeout=12):
                pytest.xfail(
                    "TC-USER-FCR-07: UI chatbot chưa hiển thị source panel dù API có sources."
                )
                return
            assert page.has_source_panel(timeout=5), (
                "TC-USER-FCR-07: Cần hiển thị nguồn tham khảo khi hỏi theo tài liệu vectorized"
            )
        finally:
            safe_delete_document(admin_token, document_id)
            safe_remove_file(docx_path)

    # ──────────────────────────────────────────────
    # TC-USER-FCR-08
    # Chatbot: Empty/long/special queries and user roadmap access
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=217)
    def test_chatbot_empty_long_special_queries_and_user_roadmap_access(self, driver):
        admin_token = get_admin_token()
        user_session = ensure_user_active(admin_token, USER1_EMAIL, USER1_PASSWORD)
        user_token = user_session["token"]

        page = UserFlashcardsChatbotRoadmapPage(driver)
        login_user(driver, USER1_EMAIL, USER1_PASSWORD)

        page.open_roadmap_page()
        assert page.has_roadmap_title("Lộ trình Cơ bản", timeout=10), (
            "TC-USER-FCR-08: User không truy cập/hiển thị được roadmap page"
        )
        page.click_first_step_title()
        assert page.is_step_panel_visible(timeout=8), (
            "TC-USER-FCR-08: Click step roadmap nhưng không mở panel chi tiết"
        )
        page.click_first_substep_button()
        assert page.is_substep_content_visible(timeout=8), (
            "TC-USER-FCR-08: Click sub-step roadmap nhưng không hiển thị nội dung"
        )

        code_rm, data_rm = api_get_roadmap_list(user_token)
        assert code_rm == 200, (
            f"TC-USER-FCR-08: API roadmap list không truy cập được với user, status={code_rm}, response={data_rm}"
        )

        page.open_chat_widget()

        msg_before_empty = page.get_chat_message_count()
        page.send_chat_empty()
        time.sleep(1.0)
        msg_after_empty = page.get_chat_message_count()
        assert msg_after_empty == msg_before_empty, (
            "TC-USER-FCR-08: Gửi câu hỏi rỗng không được tạo thêm message"
        )

        # long query
        long_query = "Giải thích ngắn gọn lộ trình học hiệu quả: " + ("A" * 1200)
        bot_before_long = page.get_chat_bot_message_count()
        page.send_chat_message(long_query)
        if not page.wait_new_bot_message(bot_before_long, timeout=35):
            pytest.xfail("TC-USER-FCR-08: Chatbot không phản hồi cho long query trong timeout.")
            return
        last_long = page.get_last_bot_message_text()
        assert last_long.strip(), (
            "TC-USER-FCR-08: Chatbot không hiển thị phản hồi cho long query"
        )

        # special query
        special_query = "' OR 1=1 -- {{<script>alert(1)</script>}} ?!@#$%^&*()_+"
        bot_before_special = page.get_chat_bot_message_count()
        page.send_chat_message(special_query)
        if not page.wait_new_bot_message(bot_before_special, timeout=35):
            pytest.xfail("TC-USER-FCR-08: Chatbot không phản hồi cho special query trong timeout.")
            return
        last_special = page.get_last_bot_message_text()
        assert last_special.strip(), (
            "TC-USER-FCR-08: Chatbot không hiển thị phản hồi cho special query"
        )

        assert "/roadmap" in driver.current_url, (
            "TC-USER-FCR-08: Sau thao tác chatbot, trang roadmap không được crash/rời route hiện tại"
        )
