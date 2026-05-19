"use client";

import type { FormEvent, ReactNode } from "react";
import { useState } from "react";
import { Activity, AlertCircle, CheckCircle2, SendHorizontal } from "lucide-react";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  meta?: string;
};

type PublicMessageResponse = {
  ok: boolean;
  mode: string;
  conversation_id: string;
  message_id: string;
  reply: string;
  provider: string;
  requires_approval: boolean;
  contract_version: string;
};

type PublicMessageError = {
  error?: string;
  message?: string;
};

const DEFAULT_CONVERSATION_ID = "web-public-smoke";

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);
  const [lastContract, setLastContract] = useState<string | null>(null);

  const handleSend = async (event?: FormEvent<HTMLFormElement>) => {
    event?.preventDefault();
    const userMsg = input.trim();
    if (!userMsg || isLoading) return;

    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setInput("");
    setIsLoading(true);
    setLastError(null);
    setLastContract(null);

    try {
      const res = await fetch("/api/public/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMsg,
          conversation_id: DEFAULT_CONVERSATION_ID,
          mode: "mock",
        }),
      });

      const body = (await res.json().catch(() => ({}))) as PublicMessageResponse & PublicMessageError;
      if (!res.ok) {
        throw new Error(body.message || body.error || `Core API returned ${res.status}.`);
      }

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: body.reply,
          meta: `${body.provider} / ${body.mode} / ${body.message_id}`,
        },
      ]);
      setLastContract(body.contract_version);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not reach the public Core API.";
      setLastError(message);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "The local public Core API did not return a mock response.",
          meta: message,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="mx-auto flex h-full w-full max-w-5xl flex-col">
      <header className="border-b border-white/10 px-5 py-4 md:px-8">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#10a37f]">Public mock chat</p>
            <h1 className="mt-1 text-xl font-semibold text-white">YonerAI Core Message MVP</h1>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <StatusPill icon={<CheckCircle2 className="h-3.5 w-3.5" />} label="offline mock" />
            <StatusPill icon={<CheckCircle2 className="h-3.5 w-3.5" />} label="no provider key" />
            <StatusPill icon={<CheckCircle2 className="h-3.5 w-3.5" />} label="no memory store" />
          </div>
        </div>
      </header>

      <section className="flex-1 overflow-y-auto px-5 py-6 md:px-8">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col justify-center">
            <div className="mb-8 flex h-14 w-14 items-center justify-center rounded-xl bg-white/5">
              <Activity className="h-7 w-7 text-[#10a37f]" />
            </div>
            <h2 className="max-w-2xl text-3xl font-semibold leading-tight text-white md:text-4xl">
              Send a local mock message through the public Core API contract.
            </h2>
            <p className="mt-4 max-w-2xl text-sm leading-6 text-gray-400">
              This surface calls <code className="rounded bg-white/10 px-1.5 py-0.5">POST /v1/public/messages</code>{" "}
              through the local rewrite. It renders only deterministic offline responses.
            </p>

            <div className="mt-8 grid gap-3 md:grid-cols-3">
              <SuggestionCard label="hello" onClick={() => setInput("hello")} />
              <SuggestionCard label="check the mock message contract" onClick={() => setInput("check the mock message contract")} />
              <SuggestionCard label="confirm no provider call" onClick={() => setInput("confirm no provider call")} />
            </div>
          </div>
        ) : (
          <div className="space-y-5 pb-6">
            {messages.map((message, index) => (
              <MessageBubble key={`${message.role}-${index}`} message={message} />
            ))}
          </div>
        )}
      </section>

      <footer className="border-t border-white/10 px-5 py-4 md:px-8">
        {lastError && (
          <div className="mb-3 flex items-start gap-2 rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-100">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{lastError}</span>
          </div>
        )}
        {lastContract && (
          <p className="mb-3 text-xs text-gray-400">
            Contract: <span className="text-gray-200">{lastContract}</span>
          </p>
        )}
        <form onSubmit={handleSend} className="flex items-end gap-3 rounded-2xl bg-[#2f2f2f] p-3">
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void handleSend();
              }
            }}
            className="max-h-[180px] min-h-11 flex-1 resize-none bg-transparent px-2 py-3 text-[15px] leading-relaxed text-white outline-none placeholder:text-gray-500"
            placeholder="Message the offline mock contract..."
            rows={1}
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white text-black transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Send mock message"
          >
            {isLoading ? <div className="h-5 w-5 animate-spin rounded-full border-2 border-black border-t-transparent" /> : <SendHorizontal className="h-5 w-5" />}
          </button>
        </form>
        <p className="mt-3 text-center text-[11px] text-gray-500">
          This is a credential-free public mock surface, not live provider generation or persistent memory.
        </p>
      </footer>
    </div>
  );
}

function StatusPill({ icon, label }: { icon: ReactNode; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-gray-200">
      {icon}
      {label}
    </span>
  );
}

function SuggestionCard({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-lg border border-white/10 px-4 py-3 text-left text-sm text-gray-300 transition hover:bg-white/5 hover:text-white"
    >
      {label}
    </button>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[82%] rounded-xl px-4 py-3 text-sm leading-6 ${
          isUser ? "bg-white text-black" : "bg-white/5 text-gray-100"
        }`}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>
        {message.meta && <p className={`mt-2 text-xs ${isUser ? "text-black/60" : "text-gray-500"}`}>{message.meta}</p>}
      </div>
    </div>
  );
}
