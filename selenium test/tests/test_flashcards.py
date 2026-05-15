from datetime import datetime

import pytest

from pages.auth_pages import UserLoginPage
from pages.config import USER_EMAIL, USER_PASSWORD
from pages.flashcard_page import FlashcardPage


@pytest.fixture
def flashcards(driver):
    UserLoginPage(driver).login(USER_EMAIL, USER_PASSWORD)
    page = FlashcardPage(driver)
    page.open_decks()
    return page


@pytest.mark.flashcards
def test_flashcard_01_deck_list_page_loads(flashcards):
    # Source: Additional Selenium case for the flashcard module.
    # Purpose: Verify the flashcard deck list page loads and exposes the create-deck action.
    page = flashcards

    assert page.wait_visible(page.CREATE_DECK_CARD).is_displayed()


@pytest.mark.flashcards
def test_flashcard_02_create_deck_modal_opens(flashcards):
    # Source: Additional Selenium case for the flashcard module.
    # Purpose: Verify the user can open the create-deck modal.
    page = flashcards

    page.open_create_deck_modal()

    assert page.wait_visible(page.DECK_TITLE_INPUT).is_displayed()
    assert page.wait_visible(page.DECK_DESCRIPTION_TEXTAREA).is_displayed()


@pytest.mark.flashcards
def test_flashcard_03_create_deck(flashcards):
    # Source: Additional Selenium case for the flashcard module.
    # Purpose: Verify a new flashcard deck can be created from the deck list.
    page = flashcards
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    title = f"Selenium Deck {stamp}"

    page.create_deck(title, "Created by Selenium test")

    assert title in page.driver.page_source


@pytest.mark.flashcards
def test_flashcard_04_create_deck_and_add_flashcard(flashcards):
    # Source: Additional Selenium case for the flashcard module.
    # Purpose: Verify a flashcard can be added inside a newly created deck.
    page = flashcards
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    title = f"Selenium Cards {stamp}"
    front = f"Front {stamp}"
    back = f"Back {stamp}"

    page.create_deck(title, "Deck for card creation")
    page.open_deck_by_title(title)
    page.add_flashcard(front, back)

    assert front in page.driver.page_source
    assert back in page.driver.page_source


@pytest.mark.flashcards
def test_flashcard_acb_01_empty_deck_title_uses_browser_validation(flashcards):
    # Source: Additional Selenium case outside the provided system/unit files.
    # Purpose: Verify the required title field blocks an empty deck submission.
    page = flashcards

    validation_message = page.try_submit_empty_deck_title()

    assert validation_message


@pytest.mark.flashcards
def test_flashcard_acb_02_deck_detail_shows_learning_actions(flashcards):
    # Source: Additional Selenium case outside the provided system/unit files.
    # Purpose: Verify a deck with at least one card exposes add, review, and quiz actions.
    page = flashcards
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    title = f"Selenium Actions {stamp}"

    page.create_deck(title, "Deck for detail actions")
    page.open_deck_by_title(title)
    page.add_flashcard(f"Action Front {stamp}", f"Action Back {stamp}")

    assert page.detail_actions_are_visible()


@pytest.mark.flashcards
def test_flashcard_fc_create_09_expired_token_redirects_to_login(flashcards):
    # Source: System FC-CREATE-09.
    # Purpose: Verify creating a deck with an expired/missing token redirects to login.
    page = flashcards
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")

    page.driver.delete_cookie("token")
    page.submit_create_deck_with_current_auth(
        f"Expired Token Deck {stamp}",
        "This request should not stay on the flashcard page.",
    )
    page.accept_alert_if_present()

    assert "/login" in page.driver.current_url


@pytest.mark.flashcards
def test_flashcard_fc_detail_24_nonexistent_deck_shows_error_not_query_title(driver):
    # Source: System FC-DETAIL-24.
    # Purpose: Verify a non-existent deck detail page does not trust the query-string title as a real deck.
    UserLoginPage(driver).login(USER_EMAIL, USER_PASSWORD)
    page = FlashcardPage(driver)
    fake_title = "System Missing Deck"

    page.open_path(f"/flashcards/999999?flashcard_deck_title={fake_title.replace(' ', '%20')}")
    page.wait_until(lambda d: fake_title in d.page_source or "not found" in d.page_source.lower(), 12)

    assert fake_title not in page.driver.page_source


@pytest.mark.flashcards
def test_flashcard_fc_detail_25_invalid_deck_id_shows_error_not_query_title(driver):
    # Source: System FC-DETAIL-25.
    # Purpose: Verify an invalid deck id is handled safely instead of rendering a fake deck title.
    UserLoginPage(driver).login(USER_EMAIL, USER_PASSWORD)
    page = FlashcardPage(driver)
    fake_title = "Invalid Deck Title"

    page.open_path(f"/flashcards/abc?flashcard_deck_title={fake_title.replace(' ', '%20')}")
    page.wait_until(lambda d: fake_title in d.page_source or "invalid" in d.page_source.lower(), 12)

    assert fake_title not in page.driver.page_source


@pytest.mark.flashcards
def test_flashcard_fc_quiz_22_answer_options_are_unique(flashcards):
    # Source: System FC-QUIZ-22.
    # Purpose: Verify each quiz question renders one and only one instance of each answer option.
    page = flashcards
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    title = f"Selenium Duplicate Quiz {stamp}"
    duplicate_answer = f"Duplicate Answer {stamp}"

    page.create_deck(title, "Deck for duplicate quiz-option regression")
    page.open_deck_by_title(title)
    page.add_flashcard(f"Duplicate Question A {stamp}", duplicate_answer)
    page.add_flashcard(f"Duplicate Question B {stamp}", duplicate_answer)
    page.open_quiz()
    page.wait_for_quiz_options()

    option_groups = page.quiz_option_groups()

    assert option_groups
    assert all(len(options) == len(set(options)) for options in option_groups), option_groups
