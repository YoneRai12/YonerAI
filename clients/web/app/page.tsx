'use client';

import React, { useRef, useState } from 'react';

type ChatMsg = {
    role: 'user' | 'assistant' | 'system';
    text: string;
};

type SendResponse = {
    message_id: string;
    run_id: string;
    status: string;
    conversation_id: string;
};


function safeJsonParse<T>(raw: string): T | null {
    try {
        return JSON.parse(raw) as T;
    } catch {
        return null;
    }
}

export default function Page() {
    const apiBase = ''; // Next.js Rewritesを使用（CORS回避のためバックエンドへ転送）
    const [conversationId, setConversationId] = useState<string>('');
    const [input, setInput] = useState('');
    const [messages, setMessages] = useState<ChatMsg[]>([
        { role: 'system', text: 'ORA Web Client (Phase 3) — SSEストリーミングデモへようこそ' },
    ]);
    const [status, setStatus] = useState<'idle' | 'sending' | 'streaming' | 'error'>('idle');
    const [lastRunId, setLastRunId] = useState<string>('');
    const [lastMessageId, setLastMessageId] = useState<string>('');

    const esRef = useRef<EventSource | null>(null);

    const closeStream = () => {
        if (esRef.current) {
            esRef.current.close();
            esRef.current = null;
        }
    };

    const appendUser = (text: string) => {
        setMessages((prev) => [...prev, { role: 'user', text }]);
    };

    const upsertAssistantStreaming = (delta: string) => {
        setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last && last.role === 'assistant') {
                next[next.length - 1] = { role: 'assistant', text: last.text + delta };
            } else {
                next.push({ role: 'assistant', text: delta });
            }
            return next;
        });
    };

    const finalizeAssistant = (fullText: string) => {
        setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last && last.role === 'assistant') {
                next[next.length - 1] = { role: 'assistant', text: fullText };
            } else {
                next.push({ role: 'assistant', text: fullText });
            }
            return next;
        });
    };

    const send = async () => {
        const text = input.trim();
        if (!text || status === 'streaming' || status === 'sending') return;

        closeStream();
        setInput('');
        setStatus('sending');

        // Optimistic UI
        const userMsg: ChatMsg = { role: 'user', text };
        setMessages((prev) => [...prev, userMsg]);

        // --- Canonical Adapter Logic ---
        const idempotencyKey = crypto.randomUUID();

        // Minimal UserIdentity (In production: get from Context/Auth)
        const userIdentity = {
            provider: "web",
            id: "local-user-demo-1",
            display_name: "Demo User"
        };

        const payload = {
            conversation_id: conversationId || null, // Allow null for new conv
            user_identity: userIdentity,
            content: text,
            attachments: [],
            idempotency_key: idempotencyKey
        };

        try {
            const res = await fetch(`${apiBase}/v1/messages`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            if (!res.ok) {
                // Handle 422 Manual
                if (res.status === 422) {
                    const errBody = await res.json();
                    console.error("Validation Manual:", errBody.manual);
                    setMessages(p => [...p, { role: 'assistant', text: `⚠️ Schema Error: ${errBody.message}` }]);
                    setStatus('error');
                    return;
                }
                const errText = await res.text();
                throw new Error(`API ${res.status}: ${errText}`);
            }

            const data = await res.json() as SendResponse;
            setLastRunId(data.run_id);
            setLastMessageId(data.message_id);
            if (!conversationId && data.conversation_id) {
                setConversationId(data.conversation_id);
            }

            setStatus('streaming');
            setMessages(p => [...p, { role: 'assistant', text: '' }]); // Placeholder

            // SSE Streaming
            const es = new EventSource(`${apiBase}/v1/runs/${data.run_id}/events`);
            esRef.current = es;

            let buffer = "";

            es.addEventListener('delta', (ev) => {
                const parsed = safeJsonParse<{ text: string }>((ev as MessageEvent).data);
                if (parsed?.text) {
                    buffer += parsed.text;
                    setMessages((prev) => {
                        const next = [...prev];
                        const last = next[next.length - 1];
                        if (last.role === 'assistant') {
                            next[next.length - 1] = { ...last, text: buffer };
                        }
                        return next;
                    });
                }
            });

            es.addEventListener('final', (ev) => {
                const parsed = safeJsonParse<{ text: string; message_id?: string }>((ev as MessageEvent).data);
                if (parsed?.message_id) setLastMessageId(parsed.message_id);
                // Ensure final text sync? Usually delta covers it, but nice to be sure
                setStatus('idle');
                closeStream();
            });

            es.addEventListener('error', (ev) => {
                console.error('SSE Error:', ev);
                closeStream();
                setStatus('idle');
            });

        } catch (e) {
            console.error("Send failed:", e);
            setStatus('error');
            setMessages(p => [...p, { role: 'system', text: `Error: ${e}` }]);
        }
    };


    return (
        <div className="flex h-screen bg-neutral-950 text-neutral-100 font-sans overflow-hidden selection:bg-emerald-500/30">
            {/* Sidebar (Desktop) */}
            <aside className="hidden md:flex w-[260px] flex-col bg-black/40 border-r border-white/5 backdrop-blur-xl">
                <div className="p-4">
                    <button
                        onClick={() => window.location.reload()}
                        className="flex items-center gap-3 w-full px-4 py-3 rounded-xl hover:bg-white/5 transition-all text-left group border border-transparent hover:border-white/5"
                    >
                        <div className="size-8 rounded-lg bg-gradient-to-tr from-emerald-500 to-cyan-500 shadow-lg shadow-emerald-500/20 group-hover:scale-105 transition-transform" />
                        <div>
                            <span className="block font-semibold text-sm tracking-wide text-neutral-200">New Chat</span>
                            <span className="block text-[10px] text-neutral-500 font-mono">ORA Omni-Router</span>
                        </div>
                    </button>
                </div>

                <div className="flex-1 px-3 py-2 overflow-y-auto space-y-1">
                    <div className="px-3 py-2 text-[10px] font-bold text-neutral-600 uppercase tracking-wider">Today</div>
                    {/* Mock History Items */}
                    <button className="w-full text-left px-3 py-2.5 rounded-lg text-sm text-neutral-400 hover:text-neutral-200 hover:bg-white/5 transition-colors truncate">
                        Python Code Verification
                    </button>
                    <button className="w-full text-left px-3 py-2.5 rounded-lg text-sm text-neutral-400 hover:text-neutral-200 hover:bg-white/5 transition-colors truncate">
                        UI Design Ideas
                    </button>
                </div>

                <div className="p-4 border-t border-white/5">
                    <div className="flex items-center gap-3 px-2 py-2">
                        <div className="size-8 rounded-full bg-neutral-800 border border-neutral-700 flex items-center justify-center text-xs font-mono">
                            USR
                        </div>
                        <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium truncate">User</div>
                            <div className="text-[10px] text-neutral-500 truncate">Pro Plan</div>
                        </div>
                    </div>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 flex flex-col relative w-full">
                {/* Header (Mobile Only / Status) */}
                <header className="absolute top-0 w-full z-10 flex items-center justify-between p-4 md:hidden bg-neutral-950/80 backdrop-blur-md border-b border-white/5">
                    <span className="font-bold">ORA</span>
                    <span className={`text-[10px] px-2 py-1 rounded-full border ${status === 'streaming' ? 'border-emerald-500/50 text-emerald-400 bg-emerald-500/10' : 'border-neutral-800 text-neutral-500'}`}>
                        {status}
                    </span>
                </header>

                {/* Messages Area */}
                <div className="flex-1 overflow-y-auto scroll-smooth">
                    <div className="w-full max-w-3xl mx-auto pt-20 pb-40 px-4 md:px-0 space-y-8">
                        {messages.length === 0 && (
                            <div className="flex flex-col items-center justify-center h-[60vh] text-center space-y-6 opacity-0 animate-fade-in-up" style={{ animationFillMode: 'forwards' }}>
                                <div className="size-16 rounded-2xl bg-gradient-to-br from-emerald-500/20 to-cyan-500/20 flex items-center justify-center border border-emerald-500/20 shadow-2xl shadow-emerald-500/10 backdrop-blur-md">
                                    <span className="text-3xl">✦</span>
                                </div>
                                <h2 className="text-2xl font-bold bg-gradient-to-b from-white to-neutral-500 bg-clip-text text-transparent">
                                    How can I help you today?
                                </h2>
                            </div>
                        )}

                        {messages.map((m, i) => (
                            <div key={i} className={`group flex gap-5 ${m.role === 'user' ? 'flex-row-reverse' : 'flex-row'} animate-in fade-in slide-in-from-bottom-2 duration-300`}>
                                {/* Avatar */}
                                <div className={`shrink-0 size-9 rounded-xl flex items-center justify-center text-sm shadow-md
                                    ${m.role === 'user'
                                        ? 'bg-neutral-800 text-neutral-300 border border-neutral-700'
                                        : 'bg-emerald-600 text-white border border-emerald-500 shadow-emerald-900/20'}`}>
                                    {m.role === 'user' ? 'U' : 'AI'}
                                </div>

                                {/* Message Bubble */}
                                <div className={`flex flex-col gap-1 max-w-[85%] md:max-w-[75%] min-w-0
                                    ${m.role === 'user' ? 'items-end' : 'items-start'}`}>

                                    <div className="text-[10px] text-neutral-500 font-medium px-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                        {m.role.toUpperCase()}
                                    </div>

                                    <div className={`relative px-5 py-3.5 rounded-2xl text-[15px] leading-7 shadow-sm border
                                        ${m.role === 'user'
                                            ? 'bg-neutral-800/50 hover:bg-neutral-800 border-neutral-700 text-neutral-100 rounded-tr-none'
                                            : m.role === 'system'
                                                ? 'bg-red-500/5 border-red-500/20 text-red-200 w-full font-mono text-xs'
                                                : 'bg-transparent border-transparent text-neutral-100 px-0 py-0' /* AI message has no background style, like ChatGPT */
                                        }`}>

                                        {m.role === 'assistant' ? (
                                            <div className="prose prose-invert prose-emerald max-w-none">
                                                {/* Simple split for paragraphs since we don't have markdown parser yet */}
                                                {m.text.split('\n').map((line, idx) => (
                                                    <p key={idx} className="min-h-[1.5em]">{line || <br />}</p>
                                                ))}
                                            </div>
                                        ) : (
                                            m.text
                                        )}
                                    </div>

                                    {/* Footer / ID */}
                                    {m.role === 'assistant' && (
                                        <div className="flex gap-2 mt-2">
                                            <button className="p-1 rounded text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800 transition-colors">
                                                <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                                            </button>
                                            <button className="p-1 rounded text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800 transition-colors">
                                                <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                                            </button>
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}

                        {status === 'streaming' && (
                            <div className="flex items-center gap-2 text-neutral-500 pl-16">
                                <span className="size-2 bg-emerald-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                                <span className="size-2 bg-emerald-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                                <span className="size-2 bg-emerald-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                            </div>
                        )}
                    </div>
                </div>

                {/* Input Area */}
                <div className="w-full max-w-3xl mx-auto px-4 pb-6 pt-2">
                    <div className="relative rounded-2xl bg-neutral-900 border border-neutral-700 shadow-xl focus-within:border-emerald-500/50 focus-within:ring-1 focus-within:ring-emerald-500/20 transition-all">
                        <textarea
                            className="w-full bg-transparent max-h-[200px] py-4 pl-4 pr-12 outline-none resize-none text-neutral-200 placeholder:text-neutral-500"
                            placeholder="Message ORA..."
                            rows={1}
                            value={input}
                            onChange={(e) => {
                                setInput(e.target.value);
                                e.target.style.height = 'auto';
                                e.target.style.height = e.target.scrollHeight + 'px';
                            }}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter' && !e.shiftKey) {
                                    e.preventDefault();
                                    if (status === 'idle') send();
                                }
                            }}
                            disabled={status !== 'idle'}
                        />
                        <button
                            className={`absolute right-3 bottom-3 p-2 rounded-lg transition-all duration-200 
                                ${input.trim() && status === 'idle'
                                    ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-500/20 hover:bg-emerald-500'
                                    : 'bg-neutral-800 text-neutral-500 cursor-not-allowed'}`}
                            onClick={send}
                            disabled={status !== 'idle' || !input.trim()}
                        >
                            <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 12h14M12 5l7 7-7 7" />
                            </svg>
                        </button>
                    </div>
                    <div className="text-center mt-3 text-[10px] text-neutral-500">
                        ORA can make mistakes. Consider checking important information.
                    </div>
                </div>
            </main>
        </div>
    );
}
