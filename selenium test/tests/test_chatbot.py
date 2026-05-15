import pytest

from pages.auth_pages import UserLoginPage
from pages.chatbot_page import ChatbotPage
from pages.config import USER_EMAIL, USER_PASSWORD


@pytest.fixture
def logged_in_chatbot(driver):
    UserLoginPage(driver).login(USER_EMAIL, USER_PASSWORD)
    page = ChatbotPage(driver)
    page.open_home()
    return page


@pytest.mark.chatbot
def test_chatbot_00_widget_is_closed_by_default(logged_in_chatbot):
    # Source: System CB-23, Unit CB-21/22/23.
    # Purpose: Verify the chat widget is hidden until the user opens it.
    page = logged_in_chatbot

    assert page.is_chat_closed()
    assert page.is_open_button_visible()


@pytest.mark.chatbot
def test_chatbot_01_widget_opens_and_displays_initial_message(logged_in_chatbot):
    # Source: System CB-21/CB-22, Unit CB-21/22/23.
    # Purpose: Verify the chatbot widget opens and shows the initial bot greeting.
    page = logged_in_chatbot
    page.open_chat()

    assert page.bot_message_count() >= 1


@pytest.mark.chatbot
def test_chatbot_02_empty_message_is_not_sent(logged_in_chatbot):
    # Source: System CB-04/CB-11, Unit CB-04/11.
    # Purpose: Verify blank input is ignored and does not create a new user message.
    page = logged_in_chatbot
    page.open_chat()
    before = len(page.message_texts())

    page.type_text(page.INPUT, "   ")
    page.click(page.SEND_BUTTON)

    assert len(page.message_texts()) == before


@pytest.mark.chatbot
def test_chatbot_03_user_message_appears_after_send(logged_in_chatbot):
    # Source: System CB-26/CB-33, Unit CB-24/26/28/29/32.
    # Purpose: Verify a sent chatbot prompt is rendered in the conversation.
    page = logged_in_chatbot
    page.open_chat()
    message = "What can I study today?"

    page.send_message(message)

    page.wait_until(lambda d: message in page.message_texts(), 10)
    assert message in page.message_texts()


@pytest.mark.chatbot
def test_chatbot_04_bot_returns_response_or_visible_error(logged_in_chatbot):
    # Source: System CB-35, Unit CB-18/35.
    # Purpose: Verify the UI gives visible feedback after a chatbot request finishes.
    page = logged_in_chatbot
    page.open_chat()
    before = page.bot_message_count()

    page.send_message("Give me a short study tip.")

    page.wait_until(lambda d: page.bot_message_count() > before, 30)
    assert page.bot_message_count() > before


@pytest.mark.chatbot
def test_chatbot_05_close_and_reopen_keeps_conversation(logged_in_chatbot):
    # Source: System CB-30, Unit CB-30.
    # Purpose: Verify closing and reopening the widget does not clear current chat messages.
    page = logged_in_chatbot
    page.open_chat()
    message = "Keep this message in the widget."
    page.send_message(message)
    page.wait_until(lambda d: message in page.message_texts(), 10)

    page.close_chat()
    page.open_chat()

    assert message in page.message_texts()


@pytest.mark.chatbot
def test_chatbot_06_input_clears_after_valid_send(logged_in_chatbot):
    # Source: System CB-32, Unit CB-24/26/28/29/32.
    # Purpose: Verify the input box is cleared immediately after sending a valid message.
    page = logged_in_chatbot
    page.open_chat()

    page.send_message("Clear this message after submit.")

    page.wait_until(lambda d: page.input_value() == "", 10)
    assert page.input_value() == ""


@pytest.mark.chatbot
def test_chatbot_07_change_page_and_reopen_keeps_conversation(logged_in_chatbot):
    # Source: System CB-31, Unit CB-31.
    # Purpose: Verify chat history survives a route change and widget remount.
    page = logged_in_chatbot
    page.open_chat()
    message = "Remember this after navigation."
    page.send_message(message)
    page.wait_until(lambda d: message in page.message_texts(), 10)

    page.open_path("/flashcards")
    page.open_chat()

    assert message in page.message_texts()


@pytest.mark.chatbot
def test_chatbot_acb_01_long_prompt_keeps_widget_usable(logged_in_chatbot):
    # Source: Additional Selenium case outside the provided system/unit files.
    # Purpose: Verify a long user prompt does not break the widget or route.
    page = logged_in_chatbot
    page.open_chat()
    message = "Study plan details " + ("A" * 1200)

    page.send_message(message)

    page.wait_until(lambda d: message in page.message_texts(), 10)
    assert "/" in page.driver.current_url


@pytest.mark.chatbot
def test_chatbot_acb_02_special_prompt_is_displayed_as_user_text(logged_in_chatbot):
    # Source: Additional Selenium case outside the provided system/unit files.
    # Purpose: Verify special characters entered by the user render as message text.
    page = logged_in_chatbot
    page.open_chat()
    message = "' OR 1=1 -- {{special_text}} ?!@#$%^&*()_+"

    page.send_message(message)

    page.wait_until(lambda d: message in page.user_message_texts(), 10)
    assert message in page.user_message_texts()


@pytest.mark.chatbot
def test_chatbot_acb_03_html_like_prompt_is_escaped_not_interpreted(logged_in_chatbot):
    # Source: Additional Selenium case outside the provided system/unit files.
    # Purpose: Verify HTML-like user input is escaped instead of being interpreted as markup.
    page = logged_in_chatbot
    page.open_chat()
    message = "' OR 1=1 -- {{<script>alert(1)</script>}} ?!@#$%^&*()_+"

    page.send_message(message)

    page.wait_until(lambda d: len(page.user_message_htmls()) > 0, 10)
    htmls = page.user_message_htmls()
    texts = page.user_message_texts()

    assert all("<script" not in html.lower() for html in htmls), f"User message was rendered as HTML: {htmls}"
    assert message in texts
