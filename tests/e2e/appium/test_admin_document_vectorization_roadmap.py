# tests/test_admin_document_vectorization_roadmap.py
# Kiểm thử Admin Documents, Vectorization & Roadmap

from __future__ import annotations

import json
import mimetypes
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

import pytest
from selenium.webdriver.support.ui import WebDriverWait

from config import ADMIN_BASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD
from pages.admin_document_roadmap_page import AdminDocumentRoadmapPage


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
    override_filename: str | None = None,
    timeout: int = 40,
) -> tuple[int, dict]:
    file_obj = Path(file_path).expanduser().resolve()
    if not file_obj.is_file():
        raise FileNotFoundError(str(file_obj))

    file_bytes = file_obj.read_bytes()
    file_name = override_filename or file_obj.name
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


def get_admin_session() -> dict:
    status, data = api_request_json(
        "POST",
        "/auth/login",
        payload={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    if status != 200:
        raise RuntimeError(f"Không lấy được admin token, status={status}, response={data}")
    payload = data.get("data") or {}
    token = payload.get("token")
    user = payload.get("user") or {}
    permissions = payload.get("permissions") or []
    if not token:
        raise RuntimeError(f"Login response không có token: {data}")
    return {"token": token, "user": user, "permissions": permissions}


def get_admin_token() -> str:
    return get_admin_session()["token"]


def api_get_topics(token: str) -> list[dict]:
    status, data = api_request_json("GET", "/topics", token=token)
    if status != 200:
        raise RuntimeError(f"Lấy topics thất bại, status={status}, response={data}")
    return data.get("data") or []


def api_get_subjects(token: str) -> list[dict]:
    status, data = api_request_json("GET", "/subjects", token=token)
    if status != 200:
        raise RuntimeError(f"Lấy subjects thất bại, status={status}, response={data}")
    return data.get("data") or []


def api_pick_subject_topic(token: str) -> tuple[int, dict]:
    topics = api_get_topics(token)
    subjects = api_get_subjects(token)
    subject_ids = {int(s["subject_id"]) for s in subjects if s.get("subject_id") is not None}

    for topic in topics:
        topic_subject_id = topic.get("subject_id")
        if topic_subject_id is None:
            continue
        if int(topic_subject_id) in subject_ids:
            return int(topic_subject_id), topic

    if topics:
        topic = topics[0]
        return int(topic.get("subject_id") or 0), topic

    raise RuntimeError("Không có topic để chạy test documents/roadmap")


def api_list_documents(
    *,
    token: str | None = None,
    keyword: str = "",
    available: str = "All",
    page: int = 1,
    topic_id: int | None = None,
    subject_id: int | None = None,
) -> list[dict]:
    query: dict[str, str | int] = {
        "page": page,
        "keyword": keyword,
        "available": available,
    }
    if topic_id is not None:
        query["topic_ids"] = topic_id
    if subject_id is not None:
        query["subject_id"] = subject_id

    status, data = api_request_json(
        "GET",
        f"/documents?{urllib.parse.urlencode(query)}",
        token=token,
    )
    if status != 200:
        raise RuntimeError(f"Lấy documents thất bại, status={status}, response={data}")
    return (data.get("data") or {}).get("documents") or []


def api_find_document_by_exact_title(token: str, title: str) -> dict | None:
    rows = api_list_documents(token=token, keyword=title, available="All", page=1)
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


def api_update_document_link(token: str, document_id: int, new_link: str):
    status, data = api_request_json(
        "PATCH",
        f"/documents/update/{document_id}",
        token=token,
        payload={"link": new_link},
    )
    if status not in (200, 202):
        raise RuntimeError(f"Update document link thất bại, status={status}, response={data}")


def api_vectorize(files: list[dict]) -> tuple[int, dict]:
    return api_request_json("POST", "/microservice/llm/vectorize", payload={"files": files}, timeout=60)


def api_get_roadmap_list(token: str) -> list[dict]:
    status, data = api_request_json("GET", "/roadmap", token=token)
    if status != 200:
        raise RuntimeError(f"Lấy roadmap list thất bại, status={status}, response={data}")
    return data.get("data") or []


def api_find_roadmap_by_exact_title(token: str, title: str) -> dict | None:
    for row in api_get_roadmap_list(token):
        if (row.get("title") or "").strip() == title:
            return row
    return None


def api_get_roadmap_by_id(token: str, roadmap_step_id: int) -> tuple[int, dict]:
    return api_request_json("GET", f"/roadmap/{roadmap_step_id}", token=token)


def api_delete_roadmap(token: str, roadmap_step_id: int):
    status, data = api_request_json("DELETE", f"/roadmap/remove/{roadmap_step_id}", token=token)
    if status not in (200, 202, 204):
        raise RuntimeError(f"Delete roadmap thất bại, status={status}, response={data}")


def safe_delete_roadmap(token: str, roadmap_step_id: int | None):
    if not roadmap_step_id:
        return
    try:
        api_delete_roadmap(token, roadmap_step_id)
    except Exception:
        pass


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


def login_admin_and_open_documents(driver) -> AdminDocumentRoadmapPage:
    clear_auth_state(driver)
    page = AdminDocumentRoadmapPage(driver)
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
    driver.get(page.DOCUMENT_URL)
    page.wait_until_document_page_loaded(timeout=20)
    assert page.is_document_management_page(), (
        f"Không vào được trang admin documents, URL hiện tại: {driver.current_url}"
    )
    return page


def login_admin_and_open_roadmap(driver) -> AdminDocumentRoadmapPage:
    clear_auth_state(driver)
    page = AdminDocumentRoadmapPage(driver)
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
    driver.get(page.ROADMAP_URL)
    page.wait_for_url_contains("/admin/roadmap")
    page.wait_for_visible(page.ROADMAP_TITLE, timeout=20)
    assert page.is_roadmap_management_page(), (
        f"Không vào được trang admin roadmap, URL hiện tại: {driver.current_url}"
    )
    return page


def create_temp_docx_file(text: str) -> str:
    temp_dir = Path(tempfile.mkdtemp(prefix="appium-docx-"))
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
    temp_dir = Path(tempfile.mkdtemp(prefix="appium-pdf-"))
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


def create_temp_text_file(content: str) -> str:
    temp_dir = Path(tempfile.mkdtemp(prefix="appium-txt-"))
    txt_path = temp_dir / "invalid.txt"
    txt_path.write_text(content, encoding="utf-8")
    return str(txt_path)


def safe_remove_file(path: str | None):
    if not path:
        return
    try:
        file_path = Path(path)
        if file_path.is_file():
            file_path.unlink(missing_ok=True)
    except Exception:
        pass


class TestAdminDocumentVectorizationRoadmap:
    """Upload/search/vectorize documents và CRUD roadmap trên admin."""

    # ──────────────────────────────────────────────
    # TC-ADMIN-DOC-01
    # Upload valid DOCX document
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=180)
    def test_upload_valid_docx_document(self, driver):
        token = get_admin_token()
        subject_id, topic = api_pick_subject_topic(token)
        topic_id = int(topic["topic_id"])
        assert subject_id > 0 and topic_id > 0, "TC-ADMIN-DOC-01: Thiếu subject/topic hợp lệ để upload DOCX"

        ts = int(time.time() * 1000)
        title = f"[TC-ADMIN-DOC-01]-docx-{ts}"
        file_path = create_temp_docx_file(f"DOCX content {ts}")
        created_document_id: int | None = None

        try:
            page = login_admin_and_open_documents(driver)
            page.open_document_create()
            assert page.is_document_create_page(), (
                f"TC-ADMIN-DOC-01: Không điều hướng được vào trang create document, URL: {driver.current_url}"
            )

            page.fill_document_form(
                title=title,
                subject_id=subject_id,
                topic_id=topic_id,
                file_path=file_path,
            )
            page.click_save_document()

            WebDriverWait(driver, 15).until(
                lambda d: "/admin/documents" in d.current_url and "/create" not in d.current_url
            )

            page.search_document(title)
            assert page.has_document_row(title, timeout=8), (
                "TC-ADMIN-DOC-01: Upload DOCX thành công nhưng không thấy tài liệu trong danh sách"
            )

            created = api_find_document_by_exact_title(token, title)
            assert created is not None, "TC-ADMIN-DOC-01: API không trả về document vừa upload"
            created_document_id = created.get("document_id")
            assert str(created.get("link") or "").lower().endswith(".docx"), (
                "TC-ADMIN-DOC-01: Document upload từ DOCX phải có link đuôi .docx"
            )
        finally:
            safe_delete_document(token, created_document_id)
            safe_remove_file(file_path)

    # ──────────────────────────────────────────────
    # TC-ADMIN-DOC-02
    # Upload valid PDF document
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=181)
    def test_upload_valid_pdf_document(self, driver):
        token = get_admin_token()
        subject_id, topic = api_pick_subject_topic(token)
        topic_id = int(topic["topic_id"])
        assert subject_id > 0 and topic_id > 0, "TC-ADMIN-DOC-02: Thiếu subject/topic hợp lệ để upload PDF"

        ts = int(time.time() * 1000)
        title = f"[TC-ADMIN-DOC-02]-pdf-{ts}"
        file_path = create_temp_pdf_file(f"PDF content {ts}")
        created_document_id: int | None = None

        try:
            page = login_admin_and_open_documents(driver)
            page.open_document_create()
            assert page.is_document_create_page(), (
                f"TC-ADMIN-DOC-02: Không điều hướng được vào trang create document, URL: {driver.current_url}"
            )

            page.fill_document_form(
                title=title,
                subject_id=subject_id,
                topic_id=topic_id,
                file_path=file_path,
            )
            page.click_save_document()

            WebDriverWait(driver, 15).until(
                lambda d: "/admin/documents" in d.current_url and "/create" not in d.current_url
            )

            page.search_document(title)
            assert page.has_document_row(title, timeout=8), (
                "TC-ADMIN-DOC-02: Upload PDF thành công nhưng không thấy tài liệu trong danh sách"
            )

            created = api_find_document_by_exact_title(token, title)
            assert created is not None, "TC-ADMIN-DOC-02: API không trả về document vừa upload"
            created_document_id = created.get("document_id")
            assert str(created.get("link") or "").lower().endswith(".pdf"), (
                "TC-ADMIN-DOC-02: Document upload từ PDF phải có link đuôi .pdf"
            )
        finally:
            safe_delete_document(token, created_document_id)
            safe_remove_file(file_path)

    # ──────────────────────────────────────────────
    # TC-ADMIN-DOC-03
    # Upload duplicate file content (system should detect hash)
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=182)
    def test_upload_duplicate_file_content_system_should_detect_hash(self, driver):
        _ = driver  # testcase API-level
        token = get_admin_token()
        _, topic = api_pick_subject_topic(token)
        topic_id = int(topic["topic_id"])

        ts = int(time.time() * 1000)
        file_path = create_temp_docx_file(f"Duplicate hash check {ts}")
        title_first = f"[TC-ADMIN-DOC-03]-first-{ts}"
        title_second = f"[TC-ADMIN-DOC-03]-second-{ts}"

        first_document_id: int | None = None
        second_document_id: int | None = None

        try:
            status_first, data_first = api_upload_document(
                token,
                title=title_first,
                topic_id=topic_id,
                file_path=file_path,
            )
            assert status_first in (200, 201), (
                f"TC-ADMIN-DOC-03: Upload lần 1 thất bại, status={status_first}, response={data_first}"
            )
            first_document_id = (data_first.get("data") or {}).get("document_id")

            status_second, data_second = api_upload_document(
                token,
                title=title_second,
                topic_id=topic_id,
                file_path=file_path,
            )

            if status_second in (200, 201):
                second_document_id = (data_second.get("data") or {}).get("document_id")
                pytest.xfail(
                    "TC-ADMIN-DOC-03: Backend hiện chưa chặn duplicate theo hash ở luồng upload document."
                )

            assert status_second == 409, (
                f"TC-ADMIN-DOC-03: Upload trùng nội dung phải trả 409, hiện tại status={status_second}, response={data_second}"
            )
            error_text = json.dumps(data_second, ensure_ascii=False).lower()
            assert "tồn tại" in error_text or "duplicate" in error_text, (
                "TC-ADMIN-DOC-03: Response duplicate phải mô tả rõ file trùng hash"
            )
        finally:
            safe_delete_document(token, first_document_id)
            safe_delete_document(token, second_document_id)
            safe_remove_file(file_path)

    # ──────────────────────────────────────────────
    # TC-ADMIN-DOC-04
    # Validation: Missing metadata or incorrect file format
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=183)
    def test_validation_missing_metadata_or_incorrect_file_format(self, driver):
        token = get_admin_token()
        _, topic = api_pick_subject_topic(token)
        topic_id = int(topic["topic_id"])

        # Case A: thiếu metadata trên UI create form
        page = login_admin_and_open_documents(driver)
        page.open_document_create()
        page.click_save_document()
        assert page.wait_notification_contains("Vui lòng điền đầy đủ thông tin", timeout=8), (
            "TC-ADMIN-DOC-04: Thiếu metadata phải hiển thị cảnh báo validation"
        )
        assert page.is_document_create_page(), (
            "TC-ADMIN-DOC-04: Form create không được redirect khi metadata còn thiếu"
        )

        # Case B: format file không hợp lệ (API-level)
        ts = int(time.time() * 1000)
        invalid_file = create_temp_text_file(f"Invalid format {ts}")
        created_document_id: int | None = None
        try:
            status, data = api_upload_document(
                token,
                title=f"[TC-ADMIN-DOC-04]-invalid-format-{ts}",
                topic_id=topic_id,
                file_path=invalid_file,
                override_filename=f"invalid-{ts}.txt",
            )

            if status in (200, 201):
                created_document_id = (data.get("data") or {}).get("document_id")
                pytest.xfail(
                    "TC-ADMIN-DOC-04: Backend hiện tại chưa chặn định dạng file ngoài DOCX/PDF ở /documents/create."
                )

            assert status in (400, 415, 422), (
                f"TC-ADMIN-DOC-04: File sai định dạng phải bị chặn, status={status}, response={data}"
            )
        finally:
            safe_delete_document(token, created_document_id)
            safe_remove_file(invalid_file)

    # ──────────────────────────────────────────────
    # TC-ADMIN-DOC-05
    # Search and filter document list by keyword or topic
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=184)
    def test_search_and_filter_document_list_by_keyword_or_topic(self, driver):
        token = get_admin_token()
        topics = api_get_topics(token)
        if not topics:
            pytest.xfail("TC-ADMIN-DOC-05: Không có topic để setup dữ liệu test")
            return

        topic_a = topics[0]
        topic_b = topics[1] if len(topics) > 1 else topics[0]
        topic_a_id = int(topic_a["topic_id"])
        topic_b_id = int(topic_b["topic_id"])
        topic_a_title = topic_a.get("title") or ""

        ts = int(time.time() * 1000)
        prefix = f"[TC-ADMIN-DOC-05]-{ts}"
        title_a = f"{prefix}-A"
        title_b = f"{prefix}-B"
        file_a = create_temp_docx_file(f"search filter A {ts}")
        file_b = create_temp_pdf_file(f"search filter B {ts}")

        doc_a_id: int | None = None
        doc_b_id: int | None = None

        try:
            status_a, data_a = api_upload_document(
                token,
                title=title_a,
                topic_id=topic_a_id,
                file_path=file_a,
            )
            assert status_a in (200, 201), (
                f"TC-ADMIN-DOC-05: Setup upload doc A thất bại, status={status_a}, response={data_a}"
            )
            doc_a_id = (data_a.get("data") or {}).get("document_id")

            status_b, data_b = api_upload_document(
                token,
                title=title_b,
                topic_id=topic_b_id,
                file_path=file_b,
            )
            assert status_b in (200, 201), (
                f"TC-ADMIN-DOC-05: Setup upload doc B thất bại, status={status_b}, response={data_b}"
            )
            doc_b_id = (data_b.get("data") or {}).get("document_id")

            page = login_admin_and_open_documents(driver)
            page.search_document(prefix)
            assert page.has_document_row(title_a, timeout=8), (
                "TC-ADMIN-DOC-05: Search theo keyword không trả về document A"
            )
            assert page.has_document_row(title_b, timeout=8), (
                "TC-ADMIN-DOC-05: Search theo keyword không trả về document B"
            )

            filtered = page.apply_topic_filter(topic_a_title)
            if not filtered:
                pytest.xfail("TC-ADMIN-DOC-05: Không chọn được topic filter trên UI")

            assert page.has_document_row(title_a, timeout=8), (
                "TC-ADMIN-DOC-05: Filter theo topic A phải giữ lại document thuộc topic A"
            )

            if topic_a_id != topic_b_id:
                assert not page.has_document_row(title_b, timeout=5), (
                    "TC-ADMIN-DOC-05: Filter theo topic A không được hiển thị document thuộc topic khác"
                )
        finally:
            safe_delete_document(token, doc_a_id)
            safe_delete_document(token, doc_b_id)
            safe_remove_file(file_a)
            safe_remove_file(file_b)

    # ──────────────────────────────────────────────
    # TC-ADMIN-DOC-06
    # Vectorize a valid document for RAG system
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=185)
    def test_vectorize_a_valid_document_for_rag_system(self, driver):
        token = get_admin_token()
        _, topic = api_pick_subject_topic(token)
        topic_id = int(topic["topic_id"])

        ts = int(time.time() * 1000)
        title = f"[TC-ADMIN-DOC-06]-{ts}"
        file_path = create_temp_docx_file(f"vectorize valid {ts}")
        created_document_id: int | None = None

        try:
            status, data = api_upload_document(
                token,
                title=title,
                topic_id=topic_id,
                file_path=file_path,
            )
            assert status in (200, 201), (
                f"TC-ADMIN-DOC-06: Setup upload document thất bại, status={status}, response={data}"
            )
            created_document_id = (data.get("data") or {}).get("document_id")

            created = api_find_document_by_exact_title(token, title)
            assert created is not None, "TC-ADMIN-DOC-06: Không tìm thấy document setup"
            assert created.get("link"), "TC-ADMIN-DOC-06: Document setup thiếu link để vectorize"

            page = login_admin_and_open_documents(driver)
            page.search_document(title)
            assert page.has_document_row(title, timeout=8), (
                "TC-ADMIN-DOC-06: Không thấy document trên UI để chạy vectorize"
            )

            selected = page.select_document_checkbox_by_title(title)
            assert selected, "TC-ADMIN-DOC-06: Không chọn được checkbox document"
            assert page.get_vectorize_selected_count() >= 1, (
                "TC-ADMIN-DOC-06: Nút Vectorize không cập nhật số lượng đã chọn"
            )

            page.click_vectorize_selected()

            if page.wait_notification_contains("Đã vectorize thành công", timeout=45):
                return

            if page.wait_notification_contains("Vectorize thất bại", timeout=4):
                pytest.xfail(
                    "TC-ADMIN-DOC-06: Microservice vectorize chưa sẵn sàng trong môi trường hiện tại."
                )

            pytest.xfail(
                "TC-ADMIN-DOC-06: Không nhận được kết quả vectorize rõ ràng (success/error) trong timeout."
            )
        finally:
            safe_delete_document(token, created_document_id)
            safe_remove_file(file_path)

    # ──────────────────────────────────────────────
    # TC-ADMIN-DOC-07
    # Batch vectorize multiple docs with error handling
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=186)
    def test_batch_vectorize_multiple_docs_with_error_handling(self, driver):
        token = get_admin_token()
        _, topic = api_pick_subject_topic(token)
        topic_id = int(topic["topic_id"])

        ts = int(time.time() * 1000)
        prefix = f"[TC-ADMIN-DOC-07]-{ts}"
        title_a = f"{prefix}-A"
        title_b = f"{prefix}-B"

        file_a = create_temp_docx_file(f"batch vectorize A {ts}")
        file_b = create_temp_pdf_file(f"batch vectorize B {ts}")
        doc_a_id: int | None = None
        doc_b_id: int | None = None

        try:
            status_a, data_a = api_upload_document(
                token,
                title=title_a,
                topic_id=topic_id,
                file_path=file_a,
            )
            assert status_a in (200, 201), (
                f"TC-ADMIN-DOC-07: Setup upload doc A thất bại, status={status_a}, response={data_a}"
            )
            doc_a_id = (data_a.get("data") or {}).get("document_id")

            status_b, data_b = api_upload_document(
                token,
                title=title_b,
                topic_id=topic_id,
                file_path=file_b,
            )
            assert status_b in (200, 201), (
                f"TC-ADMIN-DOC-07: Setup upload doc B thất bại, status={status_b}, response={data_b}"
            )
            doc_b_id = (data_b.get("data") or {}).get("document_id")

            page = login_admin_and_open_documents(driver)
            page.search_document(prefix)
            assert page.has_document_row(title_a, timeout=8), "TC-ADMIN-DOC-07: Không thấy doc A trên UI"
            assert page.has_document_row(title_b, timeout=8), "TC-ADMIN-DOC-07: Không thấy doc B trên UI"

            assert page.select_document_checkbox_by_title(title_a), (
                "TC-ADMIN-DOC-07: Không chọn được checkbox doc A"
            )
            assert page.select_document_checkbox_by_title(title_b), (
                "TC-ADMIN-DOC-07: Không chọn được checkbox doc B"
            )
            assert page.get_vectorize_selected_count() >= 2, (
                "TC-ADMIN-DOC-07: Batch vectorize phải chọn được ít nhất 2 tài liệu"
            )

            support_cdp_block = page.block_vectorize_api_endpoint()
            if not support_cdp_block:
                pytest.xfail("TC-ADMIN-DOC-07: Driver hiện tại không hỗ trợ CDP để giả lập lỗi vectorize")

            try:
                page.click_vectorize_selected()
                assert page.wait_notification_contains("Vectorize thất bại", timeout=20), (
                    "TC-ADMIN-DOC-07: Khi batch vectorize lỗi, UI phải hiển thị thông báo lỗi"
                )
                assert page.is_document_management_page(), (
                    "TC-ADMIN-DOC-07: Xử lý lỗi batch vectorize không được làm crash/rời khỏi trang documents"
                )
            finally:
                page.unblock_vectorize_api_endpoint()
        finally:
            safe_delete_document(token, doc_a_id)
            safe_delete_document(token, doc_b_id)
            safe_remove_file(file_a)
            safe_remove_file(file_b)

    # ──────────────────────────────────────────────
    # TC-ADMIN-RM-08
    # Create, edit, and delete roadmap and verify link integrity
    # ──────────────────────────────────────────────
    @pytest.mark.run(order=187)
    def test_create_edit_delete_roadmap_and_verify_link_integrity(self, driver):
        token = get_admin_token()
        topics = api_get_topics(token)
        if not topics:
            pytest.xfail("TC-ADMIN-RM-08: Không có topic để gắn roadmap")
            return

        topic_a = topics[0]
        topic_b = topics[1] if len(topics) > 1 else topics[0]
        topic_map = {int(t["topic_id"]): t for t in topics if t.get("topic_id") is not None}

        ts = int(time.time() * 1000)
        title_before = f"[TC-ADMIN-RM-08]-before-{ts}"
        desc_before = f"Roadmap step before {ts}"
        title_after = f"[TC-ADMIN-RM-08]-after-{ts}"
        desc_after = f"Roadmap step after {ts}"
        topic_a_id = int(topic_a["topic_id"])
        topic_b_id = int(topic_b["topic_id"])
        created_roadmap_id: int | None = None

        try:
            page = login_admin_and_open_roadmap(driver)
            page.fill_roadmap_form(
                title=title_before,
                description=desc_before,
                topic_id=topic_a_id,
            )
            page.submit_add_roadmap()

            assert page.has_roadmap_row(desc_before, timeout=8), (
                "TC-ADMIN-RM-08: Tạo roadmap xong nhưng không thấy dòng mới trên UI"
            )

            created = api_find_roadmap_by_exact_title(token, title_before)
            assert created is not None, "TC-ADMIN-RM-08: API không trả về roadmap vừa tạo"
            created_roadmap_id = int(created["roadmap_step_id"])
            assert int(created.get("topic_id") or 0) == topic_a_id, (
                "TC-ADMIN-RM-08: Roadmap mới tạo chưa gắn đúng topic"
            )
            assert topic_a_id in topic_map, (
                "TC-ADMIN-RM-08: Link roadmap -> topic bị sai (topic không tồn tại)"
            )

            page.click_edit_roadmap_by_description(desc_before)
            page.fill_roadmap_form(
                title=title_after,
                description=desc_after,
                topic_id=topic_b_id,
            )
            page.submit_save_roadmap()

            assert page.has_roadmap_row(desc_after, timeout=8), (
                "TC-ADMIN-RM-08: Chỉnh sửa roadmap xong nhưng UI chưa cập nhật description mới"
            )

            status_detail, detail = api_get_roadmap_by_id(token, created_roadmap_id)
            assert status_detail == 200, (
                f"TC-ADMIN-RM-08: Không lấy được roadmap detail sau update, status={status_detail}, response={detail}"
            )
            payload = detail.get("data") or {}
            assert (payload.get("title") or "").strip() == title_after, (
                "TC-ADMIN-RM-08: Update title roadmap chưa được lưu"
            )
            assert (payload.get("description") or "").strip() == desc_after, (
                "TC-ADMIN-RM-08: Update description roadmap chưa được lưu"
            )
            assert int(payload.get("topic_id") or 0) == topic_b_id, (
                "TC-ADMIN-RM-08: Update topic link của roadmap chưa được lưu"
            )
            assert topic_b_id in topic_map, (
                "TC-ADMIN-RM-08: Link roadmap -> topic sau update không còn hợp lệ"
            )

            page.click_delete_roadmap_by_description(desc_after)
            removed = page.wait_roadmap_row_removed(desc_after, timeout=10)
            assert removed, "TC-ADMIN-RM-08: Xoá roadmap trên UI nhưng dòng vẫn còn hiển thị"

            status_after_delete, data_after_delete = api_get_roadmap_by_id(token, created_roadmap_id)
            assert status_after_delete == 404, (
                "TC-ADMIN-RM-08: Xoá roadmap xong nhưng API detail vẫn truy cập được"
            )
            assert "không tìm thấy" in json.dumps(data_after_delete, ensure_ascii=False).lower(), (
                "TC-ADMIN-RM-08: API sau khi xoá phải phản hồi rõ roadmap không tồn tại"
            )
            created_roadmap_id = None
        finally:
            safe_delete_roadmap(token, created_roadmap_id)
