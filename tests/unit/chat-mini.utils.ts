export type Source = {
    file_name: string;
    preview?: string;
};

export type Message = {
    id: number;
    text: string;
    sender: "user" | "bot";
    sources?: Source[];
};

export type ChatApiResponse = {
    message?: string;
    data?: {
        answer?: string;
        error?: string;
        sources?: Source[];
    };
};

export const STORAGE_KEY = "mini-chat.messages";
export const DEFAULT_BOT_GREETING = "Xin chÃ o, tÃ´i cÃ³ thá»ƒ há»— trá»£ gÃ¬ cho báº¡n?";
export const NO_RESPONSE_MESSAGE = "KhÃ´ng cÃ³ pháº£n há»“i tá»« há»‡ thá»‘ng.";
export const GENERIC_ERROR_MESSAGE = "CÃ³ lá»—i xáº£y ra, vui lÃ²ng thá»­ láº¡i sau.";
export const MISSING_API_URL_MESSAGE = "Thiáº¿u cáº¥u hÃ¬nh káº¿t ná»‘i backend.";
export const LOADING_MESSAGE = "Äang tráº£ lá»i...";

export const DEFAULT_MESSAGES: Message[] = [
    {
        id: 1,
        text: DEFAULT_BOT_GREETING,
        sender: "bot",
    },
];

function isNonEmptyString(value: unknown): value is string {
    return typeof value === "string" && value.trim().length > 0;
}

export function getInitialMessages(storage?: Pick<Storage, "getItem"> | null): Message[] {
    const resolvedStorage =
        storage ?? (typeof window === "undefined" ? null : window.sessionStorage);

    if (!resolvedStorage) {
        return DEFAULT_MESSAGES;
    }

    try {
        const storedMessages = resolvedStorage.getItem(STORAGE_KEY);

        if (!storedMessages) {
            return DEFAULT_MESSAGES;
        }

        const parsedMessages = JSON.parse(storedMessages) as Message[];
        return parsedMessages.length > 0 ? parsedMessages : DEFAULT_MESSAGES;
    } catch {
        return DEFAULT_MESSAGES;
    }
}

export function escapeHtml(text: string): string {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

export function formatChatMessage(text: string): string {
    return escapeHtml(text)
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/\n/g, "<br/>");
}

export function extractChatAnswer(result: ChatApiResponse | null): string {
    const answer = result?.data?.answer;
    return isNonEmptyString(answer) ? answer.trim() : NO_RESPONSE_MESSAGE;
}

export function extractChatSources(result: ChatApiResponse | null): Source[] {
    const sources = result?.data?.sources;
    if (!Array.isArray(sources)) {
        return [];
    }

    return sources
        .filter((source): source is Source => isNonEmptyString(source?.file_name))
        .map((source) => ({
            file_name: source.file_name.trim(),
            preview: isNonEmptyString(source.preview) ? source.preview.trim() : undefined,
        }));
}

export function resolveChatErrorMessage(
    error: unknown,
    result?: ChatApiResponse | null,
): string {
    if (isNonEmptyString(result?.data?.error)) {
        return result.data.error.trim();
    }

    if (isNonEmptyString(result?.message)) {
        return result.message.trim();
    }

    if (error instanceof Error && isNonEmptyString(error.message)) {
        return error.message.trim();
    }

    return GENERIC_ERROR_MESSAGE;
}
