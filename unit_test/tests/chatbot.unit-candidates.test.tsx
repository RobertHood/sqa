import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import Cookies from "js-cookie";
import MiniChat from "../../frontend_user/src/components/chat-mini/page";

jest.mock("js-cookie", () => ({
  get: jest.fn()
}));

type MockFetchResponse = {
  ok: boolean;
  json: () => Promise<unknown>;
};

type Deferred<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
};

const mockedCookieGet = Cookies.get as jest.Mock;
const mockedFetch = () => global.fetch as jest.Mock;

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });

  return { promise, resolve };
}

function mockAskResponse(answer: string, sources: unknown[] = []) {
  mockedFetch().mockResolvedValueOnce({
    ok: true,
    json: async () => ({
      data: {
        answer,
        sources
      }
    })
  } satisfies MockFetchResponse);
}

function mockPendingAskResponse() {
  const pending = deferred<MockFetchResponse>();
  mockedFetch().mockReturnValueOnce(pending.promise);
  return pending;
}

function mockFailedAskResponse() {
  mockedFetch().mockResolvedValueOnce({
    ok: false,
    json: async () => ({ message: "AI microservice error" })
  } satisfies MockFetchResponse);
}

function openChat(container: HTMLElement) {
  fireEvent.click(screen.getAllByRole("button")[0]);
  return container.querySelector("input") as HTMLInputElement;
}

function sendWithEnter(input: HTMLInputElement, message: string) {
  fireEvent.change(input, { target: { value: message } });
  fireEvent.keyDown(input, { key: "Enter", code: "Enter" });
}

function clickSend(container: HTMLElement) {
  const buttons = container.querySelectorAll("button");
  fireEvent.click(buttons[1]);
}

function clickClose(container: HTMLElement) {
  const buttons = container.querySelectorAll("button");
  fireEvent.click(buttons[0]);
}

function lastFetchInit() {
  const calls = mockedFetch().mock.calls;
  return calls[calls.length - 1][1];
}

function fetchRequestBodies() {
  return mockedFetch().mock.calls.map(([, init]) => JSON.parse(init.body));
}

const GENERIC_ERROR_TEXT = "Có lỗi xảy ra, vui lòng thử lại sau.";
const LOADING_TEXT = "Đang trả lời";
const SOURCE_HEADER_TEXT = "Nguồn tham khảo:";

describe("Chatbot module - clean unit-test candidates", () => {
  beforeEach(() => {
    mockedCookieGet.mockReturnValue("valid-token");
    global.fetch = jest.fn();
  });

  // Purpose: Verify that empty input cannot be submitted to the chatbot API.
  test("CB-04", () => {
    const { container } = render(<MiniChat />);
    const input = openChat(container);

    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });
    clickSend(container);

    expect(mockedFetch()).not.toHaveBeenCalled();
  });

  // Purpose: Verify that whitespace-only input cannot be submitted to the chatbot API.
  test("CB-11", () => {
    const { container } = render(<MiniChat />);
    const input = openChat(container);

    sendWithEnter(input, "          ");
    clickSend(container);

    expect(mockedFetch()).not.toHaveBeenCalled();
  });

  // Purpose: Verify logged-out requests omit Authorization and surface a generic error.
  test("CB-18", async () => {
    mockedCookieGet.mockReturnValue(undefined);
    mockFailedAskResponse();

    const { container } = render(<MiniChat />);
    const input = openChat(container);

    sendWithEnter(input, "hello");

    await screen.findByText(GENERIC_ERROR_TEXT);
    expect(lastFetchInit().headers.Authorization).toBeUndefined();
  });

  // Purpose: Verify users cannot send another message while a response is pending.
  test("CB-19", async () => {
    mockPendingAskResponse();

    const { container } = render(<MiniChat />);
    const input = openChat(container);

    sendWithEnter(input, "first message");
    await waitFor(() => expect(input).toBeDisabled());

    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });
    clickSend(container);

    expect(mockedFetch()).toHaveBeenCalledTimes(1);
  });

  // Purpose: Verify clicking the floating button opens the chatbot widget.
  test("CB-21", () => {
    const { container } = render(<MiniChat />);

    expect(container.querySelector("input")).not.toBeInTheDocument();

    const input = openChat(container);

    expect(input).toBeInTheDocument();
    expect(container.querySelectorAll("button")).toHaveLength(2);
  });

  // Purpose: Verify the default greeting appears after opening the widget.
  test("CB-22", () => {
    const { container } = render(<MiniChat />);

    openChat(container);

    expect(container.textContent).toContain("Xin");
  });

  // Purpose: Verify the widget is closed by default on initial render.
  test("CB-23", () => {
    const { container } = render(<MiniChat />);

    expect(container.querySelector("input")).not.toBeInTheDocument();
    expect(container.querySelectorAll("button")).toHaveLength(1);
  });

  // Purpose: Verify a loading message appears while the API request is pending.
  test("CB-24", async () => {
    mockPendingAskResponse();

    const { container } = render(<MiniChat />);
    const input = openChat(container);

    sendWithEnter(input, "hello");

    await waitFor(() => expect(container.textContent).toContain(LOADING_TEXT));
  });

  // Purpose: Verify the user's message appears immediately before the bot reply resolves.
  test("CB-26", async () => {
    mockPendingAskResponse();

    const { container } = render(<MiniChat />);
    const input = openChat(container);

    sendWithEnter(input, "Hello");

    expect(await screen.findByText("Hello")).toBeInTheDocument();
    expect(container.textContent).toContain(LOADING_TEXT);
  });

  // Purpose: Verify the input is disabled while waiting for the API.
  test("CB-28", async () => {
    mockPendingAskResponse();

    const { container } = render(<MiniChat />);
    const input = openChat(container);

    sendWithEnter(input, "hello");

    await waitFor(() => expect(input).toBeDisabled());
  });

  // Purpose: Verify the send button is disabled while waiting for the API.
  test("CB-29", async () => {
    mockPendingAskResponse();

    const { container } = render(<MiniChat />);
    const input = openChat(container);

    sendWithEnter(input, "hello");

    const sendButton = container.querySelectorAll("button")[1];
    await waitFor(() => expect(sendButton).toBeDisabled());
  });

  // Purpose: Verify close and reopen keeps the current in-memory conversation.
  test("CB-30", async () => {
    mockAskResponse("Bot reply");

    const { container } = render(<MiniChat />);
    const input = openChat(container);

    sendWithEnter(input, "Hello");
    expect(await screen.findByText("Bot reply")).toBeInTheDocument();

    clickClose(container);
    expect(container.querySelector("input")).not.toBeInTheDocument();

    openChat(container);

    expect(screen.getByText("Hello")).toBeInTheDocument();
    expect(screen.getByText("Bot reply")).toBeInTheDocument();
  });

  // Purpose: Verify the text input clears after a valid message is sent.
  test("CB-32", async () => {
    mockPendingAskResponse();

    const { container } = render(<MiniChat />);
    const input = openChat(container);

    sendWithEnter(input, "Hello");

    await waitFor(() => expect(input).toHaveValue(""));
  });

  // Purpose: Verify failed API requests show a generic chatbot error.
  test("CB-35", async () => {
    mockFailedAskResponse();

    const { container } = render(<MiniChat />);
    const input = openChat(container);

    sendWithEnter(input, "Hello");

    expect(await screen.findByText(GENERIC_ERROR_TEXT)).toBeInTheDocument();
  });

  // Purpose: Verify duplicate submit attempts are ignored while loading.
  test("CB-36", async () => {
    mockPendingAskResponse();

    const { container } = render(<MiniChat />);
    const input = openChat(container);

    sendWithEnter(input, "Hello");
    await waitFor(() => expect(input).toBeDisabled());

    sendWithEnter(input, "Duplicate");
    clickSend(container);

    expect(mockedFetch()).toHaveBeenCalledTimes(1);
  });

  // Purpose: Verify source details render when the API returns sources.
  test("CB-37", async () => {
    mockAskResponse("Answer with source", [
      {
        file_name: "document.pdf",
        preview: "Relevant source excerpt"
      }
    ]);

    const { container } = render(<MiniChat />);
    const input = openChat(container);

    sendWithEnter(input, "Question with source");

    expect(await screen.findByText("document.pdf")).toBeInTheDocument();
    expect(container.textContent).toContain("Relevant source excerpt");
  });

  // Purpose: Verify the source panel stays hidden when no sources are returned.
  test("CB-38", async () => {
    mockAskResponse("Answer without source", []);

    const { container } = render(<MiniChat />);
    const input = openChat(container);

    sendWithEnter(input, "Question without source");

    expect(await screen.findByText("Answer without source")).toBeInTheDocument();
    expect(screen.queryByText(SOURCE_HEADER_TEXT)).not.toBeInTheDocument();
  });

  // Purpose: Verify a source file name is rendered when present.
  test("CB-39", async () => {
    mockAskResponse("Answer with file name", [
      {
        file_name: "source-file.docx"
      }
    ]);

    const { container } = render(<MiniChat />);
    const input = openChat(container);

    sendWithEnter(input, "Question with file name");

    expect(await screen.findByText("source-file.docx")).toBeInTheDocument();
  });

  // Purpose: Verify bold markdown markers in bot text render as bold HTML.
  test("CB-40", async () => {
    mockAskResponse("This is **bold** text");

    const { container } = render(<MiniChat />);
    const input = openChat(container);

    sendWithEnter(input, "Show bold text");

    await waitFor(() => expect(container.querySelector("strong")?.textContent).toBe("bold"));
  });

  // Purpose: Verify newline characters in bot text render as line breaks.
  test("CB-41", async () => {
    mockAskResponse("Line one\nLine two");

    const { container } = render(<MiniChat />);
    const input = openChat(container);

    sendWithEnter(input, "Show multiline text");

    await screen.findByText("Line one", { exact: false });
    expect(container.querySelectorAll("br").length).toBeGreaterThanOrEqual(1);
  });
});

describe("Chatbot module - strict regression designs that may expose gaps", () => {
  beforeEach(() => {
    mockedCookieGet.mockReturnValue("valid-token");
    global.fetch = jest.fn();
  });

  // Purpose: Verify identical repeated questions do not produce conflicting visible answers.
  test("CB-07", async () => {
    mockAskResponse("Nghị luận vào bài Ai đã đặt tên cho dòng sông?");
    mockAskResponse("Nghị luận vào bài Cái chết của một người lính.");

    const { container } = render(<MiniChat />);
    const input = openChat(container);

    sendWithEnter(input, "đề thi thptqg 2019 môn văn phần nghị luận vào bài nào");
    expect(await screen.findByText("Nghị luận vào bài Ai đã đặt tên cho dòng sông?")).toBeInTheDocument();

    await waitFor(() => expect(input).not.toBeDisabled());
    sendWithEnter(input, "đề thi thptqg 2019 môn văn phần nghị luận vào bài nào");

    await waitFor(() => expect(mockedFetch()).toHaveBeenCalledTimes(2));
    expect(fetchRequestBodies()).toEqual([
      { question: "đề thi thptqg 2019 môn văn phần nghị luận vào bài nào" },
      { question: "đề thi thptqg 2019 môn văn phần nghị luận vào bài nào" }
    ]);

    await screen.findByText("Nghị luận vào bài Cái chết của một người lính.");
    expect(container.textContent).not.toContain("Cái chết của một người lính");
  });

  // Purpose: Verify noisy special characters are normalized before the question is sent.
  test("CB-09", async () => {
    mockAskResponse("Ai đã đặt tên cho dòng sông?");

    const { container } = render(<MiniChat />);
    const input = openChat(container);

    sendWithEnter(
      input,
      "đ%ề$%t%h%i t##hpt%#$q$$%g 2#019 m#$#$@ôn !@v%ă%n% phầ%n %ng%hị%%%luận và%o %bài%%nào"
    );

    expect(await screen.findByText("Ai đã đặt tên cho dòng sông?")).toBeInTheDocument();
    expect(fetchRequestBodies()[0]).toEqual({
      question: "đề thi thptqg 2019 môn văn phần nghị luận vào bài nào"
    });
  });

  // Purpose: Verify a numerically correct answer with an incorrect conversion explanation is rejected.
  test("CB-20", async () => {
    mockAskResponse(
      "Để chuyển đổi 100000000000000000000000000 km sang mét, ta dùng 1 km = 1.000.000.000 m. Kết quả là 100000000000000000000000000000 m."
    );

    const { container } = render(<MiniChat />);
    const input = openChat(container);

    sendWithEnter(input, "100000000000000000000000000 km to meter");

    await screen.findByText(/100000000000000000000000000000 m/);
    expect(container.textContent).not.toContain("1.000.000.000 m");
  });

  // Purpose: Verify conversation history survives component unmount and remount.
  test("CB-31", async () => {
    mockAskResponse("Persistent bot reply");

    const firstRender = render(<MiniChat />);
    const firstInput = openChat(firstRender.container);

    sendWithEnter(firstInput, "Keep this message");
    expect(await screen.findByText("Persistent bot reply")).toBeInTheDocument();

    firstRender.unmount();

    const secondRender = render(<MiniChat />);
    openChat(secondRender.container);

    expect(screen.getByText("Keep this message")).toBeInTheDocument();
    expect(screen.getByText("Persistent bot reply")).toBeInTheDocument();
  });

  // Purpose: Verify the message list scrolls to the latest bot reply.
  test("CB-34", async () => {
    mockAskResponse("Newest bot reply");

    const scrollIntoView = jest.fn();
    window.HTMLElement.prototype.scrollIntoView = scrollIntoView;

    const { container } = render(<MiniChat />);
    const input = openChat(container);

    sendWithEnter(input, "Please scroll");

    expect(await screen.findByText("Newest bot reply")).toBeInTheDocument();
    expect(scrollIntoView).toHaveBeenCalled();
  });
});

describe("Chatbot module - additional strict regression ideas", () => {
  beforeEach(() => {
    mockedCookieGet.mockReturnValue("valid-token");
    global.fetch = jest.fn();
  });

  // Purpose: Verify leading and trailing spaces are trimmed before a valid message is sent.
  test("ACB-01", async () => {
    mockAskResponse("Trimmed response");

    const { container } = render(<MiniChat />);
    const input = openChat(container);

    sendWithEnter(input, "   hello chatbot   ");

    expect(await screen.findByText("Trimmed response")).toBeInTheDocument();
    expect(fetchRequestBodies()[0]).toEqual({
      question: "hello chatbot"
    });
  });

  // Purpose: Verify user-entered HTML is escaped instead of rendered as markup.
  test("ACB-02", async () => {
    mockPendingAskResponse();

    const { container } = render(<MiniChat />);
    const input = openChat(container);

    sendWithEnter(input, "<img src=x alt='user-xss' />");

    expect(await screen.findByText("<img src=x alt='user-xss' />")).toBeInTheDocument();
    expect(container.querySelector("img[alt='user-xss']")).not.toBeInTheDocument();
  });

  // Purpose: Verify bot-returned HTML is escaped instead of rendered as markup.
  test("ACB-03", async () => {
    mockAskResponse("<img src=x alt='bot-xss' />");

    const { container } = render(<MiniChat />);
    const input = openChat(container);

    sendWithEnter(input, "return unsafe html");

    expect(await screen.findByText("<img src=x alt='bot-xss' />")).toBeInTheDocument();
    expect(container.querySelector("img[alt='bot-xss']")).not.toBeInTheDocument();
  });

  // Purpose: Verify source links are rendered when the API provides a source link field.
  test("ACB-04", async () => {
    mockAskResponse("Answer with linked source", [
      {
        file_name: "source-file.pdf",
        link: "/resources/documents/source-file.pdf",
        preview: "Preview text"
      }
    ]);

    const { container } = render(<MiniChat />);
    const input = openChat(container);

    sendWithEnter(input, "show source link");

    expect(await screen.findByText("source-file.pdf")).toBeInTheDocument();
    expect(screen.getByText("/resources/documents/source-file.pdf")).toBeInTheDocument();
  });

  // Purpose: Verify a bearer token is sent when a login token exists.
  test("ACB-05", async () => {
    mockedCookieGet.mockReturnValue("token-123");
    mockAskResponse("Authenticated response");

    const { container } = render(<MiniChat />);
    const input = openChat(container);

    sendWithEnter(input, "authenticated question");

    expect(await screen.findByText("Authenticated response")).toBeInTheDocument();
    expect(lastFetchInit().headers.Authorization).toBe("Bearer token-123");
  });

  // Purpose: Verify the request is sent to the backend chatbot ask endpoint.
  test("ACB-06", async () => {
    mockAskResponse("Endpoint response");

    const { container } = render(<MiniChat />);
    const input = openChat(container);

    sendWithEnter(input, "endpoint check");

    expect(await screen.findByText("Endpoint response")).toBeInTheDocument();
    expect(mockedFetch().mock.calls[0][0]).toBe("http://localhost:3000/microservice/llm/ask");
  });

  // Purpose: Verify the request uses JSON content type.
  test("ACB-07", async () => {
    mockAskResponse("Header response");

    const { container } = render(<MiniChat />);
    const input = openChat(container);

    sendWithEnter(input, "header check");

    expect(await screen.findByText("Header response")).toBeInTheDocument();
    expect(lastFetchInit().headers["Content-Type"]).toBe("application/json");
  });

  // Purpose: Verify a successful response without answer text uses the fallback no-response message.
  test("ACB-08", async () => {
    mockedFetch().mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        data: {
          sources: []
        }
      })
    } satisfies MockFetchResponse);

    const { container } = render(<MiniChat />);
    const input = openChat(container);

    sendWithEnter(input, "missing answer check");

    expect(await screen.findByText("KhÃ´ng cÃ³ pháº£n há»“i tá»« há»‡ thá»‘ng.")).toBeInTheDocument();
  });

  // Purpose: Verify malformed source entries do not render the literal text undefined.
  test("ACB-09", async () => {
    mockAskResponse("Answer with malformed source", [
      {
        preview: "Preview without file name"
      }
    ]);

    const { container } = render(<MiniChat />);
    const input = openChat(container);

    sendWithEnter(input, "malformed source check");

    expect(await screen.findByText("Answer with malformed source")).toBeInTheDocument();
    expect(container.textContent).not.toContain("undefined");
  });

  // Purpose: Verify the close button hides the chat box and restores the floating open button.
  test("ACB-10", () => {
    const { container } = render(<MiniChat />);

    openChat(container);
    clickClose(container);

    expect(container.querySelector("input")).not.toBeInTheDocument();
    expect(container.querySelectorAll("button")).toHaveLength(1);
  });
});
