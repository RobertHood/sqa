"use client";
import { useState } from "react";
import styles from "./ChatMini.module.css";
import Cookies from "js-cookie";
import ReactMarkdown from "react-markdown";

type Source = {
    file_name: string;
    preview?: string;
};

type Message = {
    id: number;
    text: string;
    sender: "user" | "bot";
    sources?: Source[];
};

export default function MiniChat() {
    const [open, setOpen] = useState(false);
    const [messages, setMessages] = useState<Message[]>([
        {
            id: 1,
            text: "Xin chào, tôi có thể hỗ trợ gì cho bạn?",
            sender: "bot",
        },
    ]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const API_URL = process.env.NEXT_PUBLIC_ENDPOINT_BACKEND;
    const token = Cookies.get("token");

    const sendMessage = async () => {
        if (!input.trim() || loading) return;

        const userMsg: Message = {
            id: Date.now(),
            text: input,
            sender: "user",
        };

        setMessages((prev) => [...prev, userMsg]);
        setInput("");
        setLoading(true);

        try {
            const headers: Record<string, string> = {
                "Content-Type": "application/json",
            };

            if (token) {
                headers.Authorization = `Bearer ${token}`;
            }

            const res = await fetch(`${API_URL}/microservice/llm/ask`, {
                method: "POST",
                headers,
                body: JSON.stringify({
                    question: userMsg.text,
                }),
            });

            if (!res.ok) {
                throw new Error("Request failed");
            }

            const result = await res.json();

            setMessages((prev) => [
                ...prev,
                {
                    id: Date.now() + 1,
                    text: result?.data?.answer || "Không có phản hồi từ hệ thống.",
                    sender: "bot",
                    sources: result?.data?.sources || [],
                },
            ]);

        } catch (error) {
            setMessages((prev) => [
                ...prev,
                {
                    id: Date.now() + 1,
                    text: "Có lỗi xảy ra, vui lòng thử lại sau.",
                    sender: "bot",
                },
            ]);
        } finally {
            setLoading(false);
        }
    };

    return (
        <>
            {!open && (
                <button
                    className={styles.chatButton}
                    onClick={() => setOpen(true)}
                >
                    💬
                </button>
            )}

            {open && (
                <div className={styles.chatBox}>
                    {/* HEADER */}
                    <div className={styles.header}>
                        <span>Trợ lý hỗ trợ</span>
                        <button
                            className={styles.closeBtn}
                            onClick={() => setOpen(false)}
                        >
                            ✖
                        </button>
                    </div>

                    {/* MESSAGES */}
                    <div className={styles.messages}>
                        {messages.map((msg) => (
                            <div key={msg.id} className={styles.messageWrapper}>
                                {/* MESSAGE BUBBLE */}
                                <div
                                    className={`${styles.message} ${msg.sender === "user" ? styles.user : styles.bot
                                        }`}
                                    dangerouslySetInnerHTML={{
                                        __html: msg.text
                                            .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
                                            .replace(/\n/g, "<br/>"),
                                    }}
                                />

                                {/* SOURCE PANEL */}
                                {msg.sender === "bot" && msg.sources && msg.sources.length > 0 && (
                                    <div className={styles.sourcePanel}>
                                        <div className={styles.sourceHeader}>
                                            Nguồn tham khảo:
                                        </div>

                                        {msg.sources.map((s, i) => (
                                            <div key={i} className={styles.sourceItem}>
                                                <div className={styles.sourceFile}>
                                                    {s.file_name}
                                                </div>
                                                {s.preview && (
                                                    <div className={styles.sourcePreview}>
                                                        “{s.preview}”
                                                    </div>
                                                )}

                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        ))}

                        {loading && (
                            <div
                                className={`${styles.message} ${styles.bot}`}
                            >
                                Đang trả lời...
                            </div>
                        )}
                    </div>

                    {/* INPUT */}
                    <div className={styles.inputBox}>
                        <input
                            className={styles.input}
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={(e) =>
                                e.key === "Enter" && sendMessage()
                            }
                            placeholder="Nhập tin nhắn..."
                            disabled={loading}
                        />
                        <button
                            className={styles.sendBtn}
                            onClick={sendMessage}
                            disabled={loading}
                        >
                            ➤
                        </button>
                    </div>
                </div>
            )}
        </>
    );
}
