"use client";

import type { FormEvent, ReactNode } from "react";
import { useMemo, useState } from "react";
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  Cpu,
  SendHorizontal,
  Server,
  ShieldCheck,
} from "lucide-react";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  meta?: string;
};

type ChatMode = "mock" | "local-ollama" | "local-openai-compatible";

type PublicMessageResponse = {
  ok: boolean;
  mode: string;
  conversation_id: string;
  message_id: string;
  reply: string;
  provider: string;
  model?: string | null;
  requires_approval: boolean;
  contract_version: string;
};

type PublicMessageError = {
  error?: string;
  message?: string;
  detail?: unknown;
};

type ModeOption = {
  id: ChatMode;
  label: string;
  description: string;
  requestMode: "mock" | "local";
  localProvider?: "ollama" | "openai_compatible_local";
  defaultModel?: string;
};

const DEFAULT_CONVERSATION_ID = "web-chat-mvp-smoke";

const MODE_OPTIONS: ModeOption[] = [
  {
    id: "mock",
    label: "Mock / offline",
    description: "Deterministic contract response. No local model server needed.",
    requestMode: "mock",
  },
  {
    id: "local-ollama",
    label: "Local Ollama",
    description: "Loopback Ollama-compatible /api/chat through the Core API.",
    requestMode: "local",
    localProvider: "ollama",
    defaultModel: "llama3.2",
  },
  {
    id: "local-openai-compatible",
    label: "OpenAI-compatible local",
    description: "LM Studio, llama.cpp server, text-generation-webui, or LocalAI on loopback.",
    requestMode: "local",
    localProvider: "openai_compatible_local",
    defaultModel: "local-model",
  },
];

async function parsePublicMessageBody(res: Response): Promise<unknown> {
  try {
    return await res.json();
  } catch {
    if (!res.ok) {
      throw new Error(`Core API returned ${res.status}.`);
    }
    throw new Error("Core API returned an invalid JSON response.");
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isPublicMessageResponse(value: unknown): value is PublicMessageResponse {
  return (
    isRecord(value) &&
    value.ok === true &&
    typeof value.reply === "string" &&
    typeof value.provider === "string" &&
    typeof value.mode === "string" &&
    typeof value.message_id === "string" &&
    typeof value.contract_version === "string"
  );
}

function detailToMessage(detail: unknown): string | undefined {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((entry) => (isRecord(entry) && typeof entry.msg === "string" ? entry.msg : undefined))
      .find(Boolean);
  }
  if (isRecord(detail)) {
    if (typeof detail.message === "string") return detail.message;
    if (typeof detail.error === "string") return detail.error;
  }
  return undefined;
}

function toPublicMessageError(value: unknown): PublicMessageError {
  if (!isRecord(value)) return {};
  return {
    error: typeof value.error === "string" ? value.error : undefined,
    message: typeof value.message === "string" ? value.message : undefined,
    detail: value.detail,
  };
}

function toSafeErrorMessage(value: unknown, status: number): string {
  const errorBody = toPublicMessageError(value);
  return errorBody.message || detailToMessage(errorBody.detail) || errorBody.error || `Core API returned ${status}.`;
}

function buildRequestBody(mode: ModeOption, message: string, model: string) {
  const body: Record<string, string> = {
    message,
    conversation_id: DEFAULT_CONVERSATION_ID,
    mode: mode.requestMode,
  };

  if (mode.localProvider) {
    body.local_provider = mode.localProvider;
    const selectedModel = model.trim() || mode.defaultModel;
    if (selectedModel) {
      body.model = selectedModel;
    }
  }

  return body;
}

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [selectedMode, setSelectedMode] = useState<ChatMode>("mock");
  const [model, setModel] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);
  const [lastContract, setLastContract] = useState<string | null>(null);

  const mode = useMemo(
    () => MODE_OPTIONS.find((option) => option.id === selectedMode) ?? MODE_OPTIONS[0],
    [selectedMode],
  );
  const isLocalMode = Boolean(mode.localProvider);

  const handleSend = async (event?: FormEvent<HTMLFormElement>) => {
    event?.preventDefault();
    const userMsg = input.trim();
    if (!userMsg || isLoading) return;

    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        content: userMsg,
        meta: mode.label,
      },
    ]);
    setInput("");
    setIsLoading(true);
    setLastError(null);
    setLastContract(null);

    try {
      const res = await fetch("/api/public/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildRequestBody(mode, userMsg, model)),
      });

      const body = await parsePublicMessageBody(res);
      if (!res.ok) {
        throw new Error(toSafeErrorMessage(body, res.status));
      }

      if (!isPublicMessageResponse(body)) {
        throw new Error("Core API returned a malformed public message response.");
      }

      const responseMeta = [body.provider, body.mode, body.model, body.message_id].filter(Boolean).join(" / ");

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: body.reply,
          meta: responseMeta,
        },
      ]);
      setLastContract(body.contract_version);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not reach the local public Core API.";
      setLastError(message);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "The local public Core API did not return a usable response.",
          meta: message,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="mx-auto flex h-full w-full max-w-6xl flex-col">
      <header className="border-b border-white/10 px-5 py-4 md:px-8">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#10a37f]">
              Temporary Web Chat MVP
            </p>
            <h1 className="mt-1 text-xl font-semibold text-white">YonerAI local conversation smoke</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-400">
              This demo sends messages to the local Core API contract. It is not the final YonerAI product UI, not
              production service, and not persistent memory.
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <StatusPill icon={<CheckCircle2 className="h-3.5 w-3.5" />} label="mock/offline" />
            <StatusPill icon={<Server className="h-3.5 w-3.5" />} label="loopback local LLM" />
            <StatusPill icon={<ShieldCheck className="h-3.5 w-3.5" />} label="no provider key" />
          </div>
        </div>
      </header>

      <section className="grid min-h-0 flex-1 gap-0 overflow-hidden lg:grid-cols-[minmax(0,1fr)_320px]">
        <main className="min-h-0 overflow-y-auto px-5 py-6 md:px-8">
          {messages.length === 0 ? (
            <div className="flex min-h-full flex-col justify-center">
              <div className="mb-8 flex h-14 w-14 items-center justify-center rounded-xl bg-white/5">
                <Activity className="h-7 w-7 text-[#10a37f]" />
              </div>
              <h2 className="max-w-2xl text-3xl font-semibold leading-tight text-white md:text-4xl">
                Send a local message through the public Core API.
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-6 text-gray-400">
                Use mock/offline mode for deterministic smoke checks, or local mode when an Ollama-compatible or
                OpenAI-compatible local server is already running on loopback.
              </p>

              <div className="mt-8 grid gap-3 md:grid-cols-3">
                <SuggestionCard label="hello" onClick={() => setInput("hello")} />
                <SuggestionCard label="check the local message contract" onClick={() => setInput("check the local message contract")} />
                <SuggestionCard label="confirm no memory persistence" onClick={() => setInput("confirm no memory persistence")} />
              </div>
            </div>
          ) : (
            <div className="space-y-5 pb-6">
              {messages.map((message, index) => (
                <MessageBubble key={`${message.role}-${index}`} message={message} />
              ))}
            </div>
          )}
        </main>

        <aside className="border-t border-white/10 bg-black/20 px-5 py-5 lg:border-l lg:border-t-0">
          <div className="space-y-4">
            <div>
              <h2 className="text-sm font-semibold text-white">Mode</h2>
              <div className="mt-3 space-y-2">
                {MODE_OPTIONS.map((option) => (
                  <ModeButton
                    key={option.id}
                    option={option}
                    selected={selectedMode === option.id}
                    onSelect={() => setSelectedMode(option.id)}
                  />
                ))}
              </div>
            </div>

            <div>
              <label htmlFor="model" className="text-sm font-semibold text-white">
                Local model
              </label>
              <input
                id="model"
                value={model}
                onChange={(event) => setModel(event.target.value)}
                disabled={!isLocalMode}
                className="mt-2 h-11 w-full rounded-md border border-white/10 bg-white/5 px-3 text-sm text-white outline-none transition placeholder:text-gray-500 focus:border-[#10a37f] disabled:cursor-not-allowed disabled:opacity-50"
                placeholder={isLocalMode ? mode.defaultModel : "mock mode does not use a model"}
              />
              <p className="mt-2 text-xs leading-5 text-gray-500">
                Base URL is configured on the Core API side and must stay loopback-only. This page does not accept
                arbitrary provider URLs.
              </p>
            </div>

            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3 text-xs leading-5 text-gray-400">
              <p className="font-semibold text-gray-200">Current request path</p>
              <p className="mt-1">
                <code className="rounded bg-white/10 px-1.5 py-0.5">/api/public/messages</code> rewrites locally to{" "}
                <code className="rounded bg-white/10 px-1.5 py-0.5">/v1/public/messages</code>.
              </p>
            </div>
          </div>
        </aside>
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
        <form onSubmit={handleSend} className="flex items-end gap-3 rounded-xl bg-[#2f2f2f] p-3">
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void handleSend();
              }
            }}
            className="max-h-[180px] min-h-11 flex-1 bg-transparent px-2 py-3 text-[15px] leading-relaxed text-white outline-none placeholder:text-gray-500"
            placeholder="Message the temporary local Web Chat MVP..."
            rows={3}
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white text-black transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Send message"
          >
            {isLoading ? (
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-black border-t-transparent" />
            ) : (
              <SendHorizontal className="h-5 w-5" />
            )}
          </button>
        </form>
        <p className="mt-3 text-center text-[11px] text-gray-500">
          Temporary demo only: no login, no persistent memory, no Discord gateway, and no external provider call.
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

function ModeButton({ option, selected, onSelect }: { option: ModeOption; selected: boolean; onSelect: () => void }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-full rounded-lg border px-3 py-3 text-left transition ${
        selected
          ? "border-[#10a37f] bg-[#10a37f]/10 text-white"
          : "border-white/10 bg-white/[0.03] text-gray-300 hover:bg-white/5"
      }`}
    >
      <span className="flex items-center gap-2 text-sm font-medium">
        {option.localProvider ? <Cpu className="h-4 w-4" /> : <ShieldCheck className="h-4 w-4" />}
        {option.label}
      </span>
      <span className="mt-1 block text-xs leading-5 text-gray-500">{option.description}</span>
    </button>
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
