"use client";

import Link from "next/link";
import { useState } from "react";
import {
  Activity,
  Check,
  ChevronDown,
  ChevronRight,
  Paperclip,
  SendHorizontal,
} from "lucide-react";

type Message = {
  role: string;
  content: string;
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMsg = input;
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setInput("");
    setIsLoading(true);
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    try {
      const res = await fetch("/api/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content: userMsg,
          user_identity: {
            provider: "web",
            id: "web-guest",
            display_name: "Guest User",
          },
        }),
      });

      if (!res.ok) {
        throw new Error("API Error");
      }

      const data = await res.json();
      const runId = data.run_id;
      if (!runId) {
        throw new Error("No Run ID returned");
      }

      const evtSource = new EventSource(`/api/runs/${runId}/events`);

      evtSource.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          const type = payload.event;
          const innerData = payload.data;

          if (type === "delta") {
            const text = innerData.text || "";
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (last?.role === "assistant") {
                last.content += text;
              }
              return next;
            });
          } else if (type === "final" || type === "error") {
            evtSource.close();
            setIsLoading(false);
          }
        } catch (error) {
          console.error("SSE Parse Error", error);
        }
      };

      evtSource.onerror = (error) => {
        console.error("SSE Error", error);
        evtSource.close();
        setIsLoading(false);
      };
    } catch (error) {
      console.error(error);
      setMessages((prev) => {
        const next = [...prev];
        if (next.length > 0 && next[next.length - 1].content === "") {
          next[next.length - 1].content = "Error: Could not connect to YonerAI.";
        }
        return next;
      });
      setIsLoading(false);
    }
  };

  return (
    <div className="relative mx-auto flex h-full w-full max-w-5xl flex-col">
      <div className="w-full px-4 pt-4 md:px-8 md:pt-6">
        <div className="rounded-2xl border border-amber-400/30 bg-amber-500/10 p-4 text-sm text-amber-50 shadow-lg shadow-amber-950/10 backdrop-blur-sm">
          <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
            <div className="space-y-1">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-amber-200/80">
                Maintenance Notice
              </p>
              <p className="leading-relaxed text-amber-50/95">
                yonerai.com is currently under maintenance. The maintenance is planned to continue
                until March 31, 2026 at the latest, but it may also end earlier on an irregular
                schedule.
              </p>
              <p className="leading-relaxed text-amber-100/80">
                Public web access and operator features are being prepared in stages.
              </p>
            </div>
            <div className="space-y-1 text-xs text-amber-100/85 md:text-right">
              <p className="font-semibold uppercase tracking-[0.2em] text-amber-200/80">Contact</p>
              <p>
                <a
                  className="underline decoration-amber-200/40 underline-offset-4 hover:text-white"
                  href="mailto:hello@yonerai.com"
                >
                  hello@yonerai.com
                </a>
              </p>
              <p>
                <a
                  className="underline decoration-amber-200/40 underline-offset-4 hover:text-white"
                  href="https://yonerai.com"
                  target="_blank"
                  rel="noreferrer"
                >
                  yonerai.com
                </a>
              </p>
              <p>
                <Link
                  className="underline decoration-amber-200/40 underline-offset-4 hover:text-white"
                  href="/cua"
                >
                  Open CUA sidecar guide
                </Link>
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="flex w-full items-center justify-between p-4 md:hidden">
        <span className="font-bold text-gray-200">YonerAI</span>
        <PlusIcon />
      </div>

      <div className="hidden w-full justify-start px-8 pt-4 md:flex md:z-20">
        <ModelSelector />
      </div>

      <div className="scrollbar-hidden mx-auto flex-1 w-full max-w-3xl overflow-y-auto p-4">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <div className="mb-8 rounded-full bg-white/5 p-4 backdrop-blur-sm">
              <Activity className="h-10 w-10 text-white opacity-90" />
            </div>
            <h2 className="mb-12 text-2xl font-semibold tracking-tight text-white/90">
              How can I help you today?
            </h2>

            <div className="grid w-full grid-cols-1 gap-4 md:grid-cols-2">
              <SuggestionCard
                title="Write a Python script"
                desc="to automate detailed daily reports"
                onClick={() => setInput("Write a Python script to automate detailed daily reports")}
              />
              <SuggestionCard
                title="Explain quantum computing"
                desc="in simple terms"
                onClick={() => setInput("Explain quantum computing in simple terms")}
              />
              <SuggestionCard
                title="Draft an email"
                desc="requesting a deadline extension"
                onClick={() => setInput("Draft an email requesting a deadline extension")}
              />
              <SuggestionCard
                title="Brainstorm ideas"
                desc="for a cyberpunk novel setting"
                onClick={() => setInput("Brainstorm ideas for a cyberpunk novel setting")}
              />
            </div>
          </div>
        ) : (
          <div className="space-y-6 pb-4">
            {messages.map((message, index) => (
              <div
                key={index}
                className={`flex gap-4 ${message.role === "user" ? "justify-end" : "justify-start"}`}
              >
                {message.role === "assistant" && (
                  <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#10a37f]">
                    <Activity className="h-5 w-5 text-white" />
                  </div>
                )}
                <div
                  className={`max-w-[80%] rounded-2xl p-4 text-sm leading-relaxed ${
                    message.role === "user" ? "bg-[#2f2f2f] text-white" : "text-gray-100"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{message.content}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="flex w-full justify-center bg-transparent p-6 pb-8">
        <div className="relative w-full max-w-3xl">
          <div className="flex items-center gap-3 rounded-3xl bg-[#2f2f2f] p-2 pl-4 transition-colors">
            <button className="shrink-0 rounded-full bg-transparent p-2 text-gray-400 transition hover:bg-white/10 hover:text-white">
              <Paperclip className="h-5 w-5" />
            </button>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              className="max-h-[200px] flex-1 resize-none border-0 bg-transparent py-3 text-[15px] leading-relaxed text-white placeholder-gray-500 focus:ring-0"
              placeholder="Message YonerAI..."
              rows={1}
              style={{ minHeight: "44px" }}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
              className="shrink-0 rounded-full bg-white p-2 text-black shadow-sm transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isLoading ? (
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-black border-t-transparent" />
              ) : (
                <SendHorizontal className="h-5 w-5" />
              )}
            </button>
          </div>
          <p className="mt-3 text-center text-[11px] font-medium tracking-wide text-gray-500">
            YonerAI can make mistakes. Check important info.
          </p>
        </div>
      </div>
    </div>
  );
}

function SuggestionCard({
  title,
  desc,
  onClick,
}: {
  title: string;
  desc: string;
  onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="group rounded-xl border border-white/10 p-4 text-left transition hover:bg-white/5"
    >
      <p className="mb-1 text-sm font-semibold text-gray-200">{title}</p>
      <p className="text-xs text-gray-500 group-hover:text-gray-400">{desc}</p>
    </button>
  );
}

function ModelSelector() {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedModel, setSelectedModel] = useState("GPT-4.5");
  const [showSubmenu, setShowSubmenu] = useState(false);

  return (
    <div className="group relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 rounded-lg px-3 py-2 text-lg font-semibold text-gray-200 opacity-90 transition hover:bg-[#2f2f2f]"
      >
        {selectedModel} <ChevronDown className="h-4 w-4 opacity-50" />
      </button>

      {isOpen && (
        <div className="absolute left-0 top-full z-30 mt-2 w-64 rounded-xl border border-white/10 bg-[#2f2f2f] p-1 shadow-2xl">
          <div className="px-3 py-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
            Model
          </div>

          <ModelOption
            label="GPT-4o"
            desc="Great for most tasks"
            active={selectedModel === "GPT-4o"}
            onClick={() => {
              setSelectedModel("GPT-4o");
              setIsOpen(false);
            }}
          />
          <ModelOption
            label="GPT-5 (Preview)"
            desc="Reasoning & Deep Thought"
            active={selectedModel === "GPT-5 (Preview)"}
            onClick={() => {
              setSelectedModel("GPT-5 (Preview)");
              setIsOpen(false);
            }}
          />

          <div className="my-1 h-px bg-white/10" />

          <div
            className="relative"
            onMouseEnter={() => setShowSubmenu(true)}
            onMouseLeave={() => setShowSubmenu(false)}
          >
            <button className="group/item flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-[#424242]">
              <span className="text-sm font-medium text-gray-200">Legacy Models</span>
              <ChevronRight className="h-4 w-4 text-gray-500" />
            </button>

            {showSubmenu && (
              <div className="absolute left-full top-0 z-40 ml-2 w-56 rounded-xl border border-white/10 bg-[#2f2f2f] p-1 shadow-2xl">
                <ModelOption
                  label="GPT-3.5 Turbo"
                  active={selectedModel === "GPT-3.5 Turbo"}
                  onClick={() => {
                    setSelectedModel("GPT-3.5 Turbo");
                    setIsOpen(false);
                  }}
                />
                <ModelOption
                  label="GPT-4 Legacy"
                  active={selectedModel === "GPT-4 Legacy"}
                  onClick={() => {
                    setSelectedModel("GPT-4 Legacy");
                    setIsOpen(false);
                  }}
                />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ModelOption({
  label,
  desc,
  active,
  onClick,
}: {
  label: string;
  desc?: string;
  active?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="group flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-[#424242]"
    >
      <div className="flex flex-col">
        <span className="text-sm font-medium text-gray-200">{label}</span>
        {desc && <span className="text-xs text-gray-500">{desc}</span>}
      </div>
      {active && <Check className="h-4 w-4 text-white" />}
    </button>
  );
}

function PlusIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="text-gray-300"
    >
      <path d="M5 12h14" />
      <path d="M12 5v14" />
    </svg>
  );
}
