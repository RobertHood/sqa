import { describe, expect, it } from "vitest";

import {
    DEFAULT_BOT_GREETING,
    DEFAULT_MESSAGES,
    extractChatAnswer,
    extractChatSources,
    formatChatMessage,
    GENERIC_ERROR_MESSAGE,
    getInitialMessages,
    LOADING_MESSAGE,
    MISSING_API_URL_MESSAGE,
    NO_RESPONSE_MESSAGE,
    resolveChatErrorMessage,
    STORAGE_KEY,
} from "./chat-mini.utils";

describe("chat-mini utils", () => {
    describe("constants", () => {
        it("exposes the expected chatbot constants", () => {
            expect(DEFAULT_BOT_GREETING).toContain("Xin chao");
            expect(NO_RESPONSE_MESSAGE).toContain("Khong co phan hoi");
            expect(GENERIC_ERROR_MESSAGE).toContain("Co loi xay ra");
            expect(MISSING_API_URL_MESSAGE).toContain("backend");
            expect(LOADING_MESSAGE).toContain("Dang tra loi");
            expect(STORAGE_KEY).toBe("mini-chat.messages");
        });
    });

    describe("getInitialMessages", () => {
        it("returns default messages when storage is unavailable", () => {
            expect(getInitialMessages(null)).toEqual(DEFAULT_MESSAGES);
        });

        it("returns default messages when storage has no saved conversation", () => {
            expect(
                getInitialMessages({
                    getItem: () => null,
                }),
            ).toEqual(DEFAULT_MESSAGES);
        });

        it("returns stored messages when valid session data exists", () => {
            const storedMessages = [
                { id: 99, text: "Saved", sender: "bot" as const },
                { id: 100, text: "Thread", sender: "user" as const },
            ];

            expect(
                getInitialMessages({
                    getItem: () => JSON.stringify(storedMessages),
                }),
            ).toEqual(storedMessages);
        });

        it("returns default messages when saved JSON is malformed", () => {
            expect(
                getInitialMessages({
                    getItem: () => "{not-json",
                }),
            ).toEqual(DEFAULT_MESSAGES);
        });

        it("returns default messages when saved message list is empty", () => {
            expect(
                getInitialMessages({
                    getItem: () => "[]",
                }),
            ).toEqual(DEFAULT_MESSAGES);
        });

        it("returns default messages when session data is not an array", () => {
            expect(
                getInitialMessages({
                    getItem: () => JSON.stringify({ text: "invalid" }),
                }),
            ).toEqual(DEFAULT_MESSAGES);
        });

        it("returns default messages when stored entries are missing sender", () => {
            expect(
                getInitialMessages({
                    getItem: () =>
                        JSON.stringify([
                            {
                                id: 2,
                                text: "Saved",
                            },
                        ]),
                }),
            ).toEqual(DEFAULT_MESSAGES);
        });

        it("returns default messages when stored entries use an invalid sender value", () => {
            expect(
                getInitialMessages({
                    getItem: () =>
                        JSON.stringify([
                            {
                                id: 3,
                                text: "Saved",
                                sender: "system",
                            },
                        ]),
                }),
            ).toEqual(DEFAULT_MESSAGES);
        });
    });

    describe("formatChatMessage", () => {
        it("renders a single markdown bold segment", () => {
            expect(formatChatMessage("**Bold**")).toBe("<strong>Bold</strong>");
        });

        it("renders multiple markdown bold segments", () => {
            expect(formatChatMessage("**One** and **Two**")).toBe(
                "<strong>One</strong> and <strong>Two</strong>",
            );
        });

        it("converts newlines to br tags", () => {
            expect(formatChatMessage("Line 1\nLine 2")).toBe("Line 1<br/>Line 2");
        });

        it("supports bold text across multiple lines", () => {
            expect(formatChatMessage("**Bold**\nNext")).toBe(
                "<strong>Bold</strong><br/>Next",
            );
        });

        it("escapes raw html tags before formatting", () => {
            expect(formatChatMessage("<script>alert(1)</script>")).toBe(
                "&lt;script&gt;alert(1)&lt;/script&gt;",
            );
        });

        it("escapes ampersands and quotes", () => {
            expect(formatChatMessage('Tom & "Jerry"')).toBe(
                "Tom &amp; &quot;Jerry&quot;",
            );
        });

        it("leaves unmatched opening markdown markers as plain text", () => {
            expect(formatChatMessage("**Bold")).toBe("**Bold");
        });

        it("leaves unmatched closing markdown markers as plain text", () => {
            expect(formatChatMessage("Bold**")).toBe("Bold**");
        });

        it("keeps plain text unchanged when no formatting is present", () => {
            expect(formatChatMessage("Plain text only")).toBe("Plain text only");
        });

        it("supports punctuation inside bold text", () => {
            expect(formatChatMessage("**Hello, world!**")).toBe(
                "<strong>Hello, world!</strong>",
            );
        });

        it("normalizes Windows newlines without leaving carriage returns", () => {
            expect(formatChatMessage("Line 1\r\nLine 2")).toBe("Line 1<br/>Line 2");
        });

        it("trims surrounding whitespace before rendering bold markdown", () => {
            expect(formatChatMessage("  **Bold**  ")).toBe("<strong>Bold</strong>");
        });
    });

    describe("extractChatAnswer", () => {
        it("returns the trimmed answer from the API payload", () => {
            expect(
                extractChatAnswer({
                    data: {
                        answer: "  Final answer  ",
                    },
                }),
            ).toBe("Final answer");
        });

        it("returns the fallback message when the answer is missing", () => {
            expect(extractChatAnswer({ data: {} })).toBe(NO_RESPONSE_MESSAGE);
        });

        it("returns the fallback message when the answer is blank", () => {
            expect(
                extractChatAnswer({
                    data: {
                        answer: "   ",
                    },
                }),
            ).toBe(NO_RESPONSE_MESSAGE);
        });

        it("returns the fallback message when the payload is null", () => {
            expect(extractChatAnswer(null)).toBe(NO_RESPONSE_MESSAGE);
        });

        it("returns the fallback message when the answer is not a string", () => {
            expect(
                extractChatAnswer({
                    data: {
                        answer: 123 as never,
                    },
                }),
            ).toBe(NO_RESPONSE_MESSAGE);
        });

        it("preserves markdown in the extracted answer for later formatting", () => {
            expect(
                extractChatAnswer({
                    data: {
                        answer: "**Bold** line",
                    },
                }),
            ).toBe("**Bold** line");
        });

        it("falls back to the top-level message when answer is missing", () => {
            expect(
                extractChatAnswer({
                    message: "Top-level fallback",
                    data: {},
                }),
            ).toBe("Top-level fallback");
        });

        it("falls back to the top-level message when answer is blank", () => {
            expect(
                extractChatAnswer({
                    message: "Top-level fallback",
                    data: {
                        answer: "   ",
                    },
                }),
            ).toBe("Top-level fallback");
        });

        it("returns the top-level message when data is missing entirely", () => {
            expect(
                extractChatAnswer({
                    message: "Top-level fallback",
                }),
            ).toBe("Top-level fallback");
        });
    });

    describe("extractChatSources", () => {
        it("returns an empty list when sources are missing", () => {
            expect(extractChatSources({ data: {} })).toEqual([]);
        });

        it("returns an empty list when the payload is null", () => {
            expect(extractChatSources(null)).toEqual([]);
        });

        it("returns valid sources with trimmed file names and previews", () => {
            expect(
                extractChatSources({
                    data: {
                        sources: [
                            {
                                file_name: " lesson.pdf ",
                                preview: " Important excerpt ",
                            },
                        ],
                    },
                }),
            ).toEqual([
                {
                    file_name: "lesson.pdf",
                    preview: "Important excerpt",
                },
            ]);
        });

        it("drops sources with empty file names", () => {
            expect(
                extractChatSources({
                    data: {
                        sources: [
                            {
                                file_name: "   ",
                                preview: "Ignored",
                            },
                        ],
                    },
                }),
            ).toEqual([]);
        });

        it("drops non-array source payloads", () => {
            expect(
                extractChatSources({
                    data: {
                        sources: "invalid" as never,
                    },
                }),
            ).toEqual([]);
        });

        it("keeps a source when preview is missing", () => {
            expect(
                extractChatSources({
                    data: {
                        sources: [
                            {
                                file_name: "lesson.pdf",
                            },
                        ],
                    },
                }),
            ).toEqual([
                {
                    file_name: "lesson.pdf",
                    preview: undefined,
                },
            ]);
        });

        it("deduplicates repeated sources by file name", () => {
            expect(
                extractChatSources({
                    data: {
                        sources: [
                            {
                                file_name: " lesson.pdf ",
                                preview: "First preview",
                            },
                            {
                                file_name: "lesson.pdf",
                                preview: "Second preview",
                            },
                        ],
                    },
                }),
            ).toEqual([
                {
                    file_name: "lesson.pdf",
                    preview: "First preview",
                },
            ]);
        });

        it("normalizes Windows newlines inside source previews", () => {
            expect(
                extractChatSources({
                    data: {
                        sources: [
                            {
                                file_name: "lesson.pdf",
                                preview: "Line 1\r\nLine 2",
                            },
                        ],
                    },
                }),
            ).toEqual([
                {
                    file_name: "lesson.pdf",
                    preview: "Line 1\nLine 2",
                },
            ]);
        });
    });

    describe("resolveChatErrorMessage", () => {
        it("prefers the backend error message from result.data.error", () => {
            expect(
                resolveChatErrorMessage(new Error("fallback"), {
                    data: {
                        error: "Backend error",
                    },
                }),
            ).toBe("Backend error");
        });

        it("falls back to the top-level backend message", () => {
            expect(
                resolveChatErrorMessage(new Error("fallback"), {
                    message: "Request failed",
                }),
            ).toBe("Request failed");
        });

        it("falls back to the thrown Error message", () => {
            expect(resolveChatErrorMessage(new Error("Network down"))).toBe(
                "Network down",
            );
        });

        it("returns the generic message for a non-Error throw", () => {
            expect(resolveChatErrorMessage("boom")).toBe(GENERIC_ERROR_MESSAGE);
        });

        it("returns the generic message when the Error message is blank", () => {
            expect(resolveChatErrorMessage(new Error("   "))).toBe(
                GENERIC_ERROR_MESSAGE,
            );
        });

        it("trims backend error messages", () => {
            expect(
                resolveChatErrorMessage(null, {
                    data: {
                        error: "  Trim me  ",
                    },
                }),
            ).toBe("Trim me");
        });

        it("maps backend internal server errors to the generic user-facing message", () => {
            expect(
                resolveChatErrorMessage(null, {
                    data: {
                        error: "Internal Server Error",
                    },
                }),
            ).toBe(GENERIC_ERROR_MESSAGE);
        });
    });

    describe("formatting and extraction integration", () => {
        it("formats a bold extracted answer into html", () => {
            const answer = extractChatAnswer({
                data: {
                    answer: "**Bold**",
                },
            });
            expect(formatChatMessage(answer)).toBe("<strong>Bold</strong>");
        });

        it("formats multiline extracted answers into html", () => {
            const answer = extractChatAnswer({
                data: {
                    answer: "Line 1\nLine 2",
                },
            });
            expect(formatChatMessage(answer)).toBe("Line 1<br/>Line 2");
        });

        it("escapes html embedded inside extracted answers", () => {
            const answer = extractChatAnswer({
                data: {
                    answer: "<b>Unsafe</b>",
                },
            });
            expect(formatChatMessage(answer)).toBe("&lt;b&gt;Unsafe&lt;/b&gt;");
        });

        it("keeps source previews independent from answer formatting", () => {
            const sources = extractChatSources({
                data: {
                    sources: [
                        {
                            file_name: "lesson.pdf",
                            preview: "**Preview** text",
                        },
                    ],
                },
            });
            expect(sources[0]?.preview).toBe("**Preview** text");
        });

        it("returns a generic error when both backend and thrown errors are empty", () => {
            expect(
                resolveChatErrorMessage(new Error(""), {
                    message: "   ",
                    data: {
                        error: "   ",
                    },
                }),
            ).toBe(GENERIC_ERROR_MESSAGE);
        });
    });
});
