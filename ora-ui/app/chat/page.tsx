"use client";

import { useState } from "react";
import { SendHorizontal, Paperclip, ChevronDown, ChevronRight, Check, Activity } from "lucide-react";

export default function Home() {
  const [messages, setMessages] = useState<{ role: string, content: string }[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMsg = input;
    setMessages(prev => [...prev, { role: "user", content: userMsg }]);
    setInput("");
    setIsLoading(true);

    // Initial placeholder for assistant
    setMessages(prev => [...prev, { role: "assistant", content: "" }]);

    try {
      const res = await fetch("/api/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content: userMsg,
          user_identity: { provider: "web", id: "web-guest", display_name: "Guest User" }
        })
      });

      if (!res.ok) throw new Error("API Error");

      const data = await res.json();
      const runId = data.run_id;

      if (!runId) {
        throw new Error("No Run ID returned");
      }

      // Start SSE Stream
      console.log(`Listening to events for run: ${runId}`);
      const evtSource = new EventSource(`/api/runs/${runId}/events`);

      evtSource.onmessage = (event) => {
        try {
          // The stream yields { data: "JSON_STRING" }
          // We need to parse event.data first
          const payload = JSON.parse(event.data);
          // payload is { event: "delta", data: {...} }
          const type = payload.event;
          const innerData = payload.data; // { text: "..." }

          if (type === "delta") {
            const text = innerData.text || "";
            setMessages(prev => {
              const newArr = [...prev];
              const last = newArr[newArr.length - 1];
              if (last.role === "assistant") {
                last.content += text;
              }
              return newArr;
            });
          } else if (type === "final" || type === "error") {
            evtSource.close();
            setIsLoading(false);
          }
        } catch (e) {
          console.error("SSE Parse Error", e);
        }
      };

      evtSource.onerror = (err) => {
        console.error("SSE Error", err);
        evtSource.close();
        setIsLoading(false);
      };

    } catch (e) {
      console.error(e);
      setMessages(prev => {
        const newArr = [...prev];
        // Remove empty placeholder if failed immediately
        if (newArr.length > 0 && newArr[newArr.length - 1].content === "") {
          newArr[newArr.length - 1].content = "⚠️ Error: Could not connect to ORA Brain.";
        }
        return newArr;
      });
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full w-full max-w-5xl mx-auto relative">

      {/* Top Model Selector (Mock) */}
      <div className="w-full flex items-center justify-between p-4 md:hidden">
        <span className="font-bold text-gray-200">ORA Model</span>
        <PlusIcon />
      </div>

      {/* Model Version Dropdown (Desktop) */}
      <div className="hidden md:flex absolute top-0 left-0 w-full p-4 z-20 justify-start px-8">
        <ModelSelector />
      </div>


      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto w-full max-w-3xl mx-auto p-4 scrollbar-hidden">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="mb-8 p-4 rounded-full bg-white/5 backdrop-blur-sm">
              <Activity className="w-10 h-10 text-white opacity-90" />
            </div>
            <h2 className="text-2xl font-semibold text-white/90 mb-12 tracking-tight">How can I help you today?</h2>

            {/* Suggestion Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full">
              <SuggestionCard title="Write a Python script" desc="to automate detailed daily reports" onClick={() => setInput("Write a Python script to automate detailed daily reports")} />
              <SuggestionCard title="Explain quantum computing" desc="in simple terms" onClick={() => setInput("Explain quantum computing in simple terms")} />
              <SuggestionCard title="Draft an email" desc="requesting a deadline extension" onClick={() => setInput("Draft an email requesting a deadline extension")} />
              <SuggestionCard title="Brainstorm ideas" desc="for a cyberpunk novel setting" onClick={() => setInput("Brainstorm ideas for a cyberpunk novel setting")} />
            </div>
          </div>
        ) : (
          <div className="space-y-6 pb-4">
            {messages.map((m, i) => (
              <div key={i} className={`flex gap-4 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                {m.role === 'assistant' && (
                  <div className="w-8 h-8 rounded-full bg-[#10a37f] flex items-center justify-center shrink-0 mt-1">
                    <Activity className="w-5 h-5 text-white" />
                  </div>
                )}
                <div className={`max-w-[80%] rounded-2xl p-4 text-sm leading-relaxed ${m.role === 'user' ? 'bg-[#2f2f2f] text-white' : 'text-gray-100'}`}>
                  <p className="whitespace-pre-wrap">{m.content}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="w-full p-6 pb-8 flex justify-center bg-transparent">
        <div className="w-full max-w-3xl relative">
          <div className="flex items-center gap-3 bg-[#2f2f2f] p-2 pl-4 rounded-3xl transition-colors">
            <button className="p-2 text-gray-400 hover:text-white transition bg-transparent hover:bg-white/10 rounded-full shrink-0">
              <Paperclip className="w-5 h-5" />
            </button>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              className="flex-1 bg-transparent border-0 focus:ring-0 text-white placeholder-gray-500 resize-none max-h-[200px] py-3 leading-relaxed text-[15px]"
              placeholder="Message ORA..."
              rows={1}
              style={{ minHeight: "44px" }}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
              className="p-2 bg-white text-black rounded-full hover:opacity-90 transition disabled:opacity-50 disabled:cursor-not-allowed shadow-sm shrink-0"
            >
              {isLoading ? (
                <div className="w-5 h-5 border-2 border-black border-t-transparent rounded-full animate-spin" />
              ) : (
                <SendHorizontal className="w-5 h-5" />
              )}
            </button>
          </div>
          <p className="text-center text-[11px] text-gray-500 mt-3 font-medium tracking-wide">
            ORA can make mistakes. Check important info.
          </p>
        </div>
      </div>

    </div>
  );
}

function SuggestionCard({ title, desc, onClick }: { title: string, desc: string, onClick?: () => void }) {
  return (
    <button onClick={onClick} className="text-left p-4 rounded-xl border border-white/10 hover:bg-white/5 transition group">
      <p className="font-semibold text-gray-200 text-sm mb-1">{title}</p>
      <p className="text-gray-500 text-xs group-hover:text-gray-400">{desc}</p>
    </button>
  )
}

function ModelSelector() {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedModel, setSelectedModel] = useState("GPT-4.5");
  const [showSubmenu, setShowSubmenu] = useState(false);

  return (
    <div className="relative group">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 text-lg font-semibold text-gray-200 opacity-90 hover:bg-[#2f2f2f] px-3 py-2 rounded-lg transition"
      >
        {selectedModel} <ChevronDown className="w-4 h-4 opacity-50" />
      </button>

      {/* Main Dropdown */}
      {isOpen && (
        <div className="absolute top-full left-0 mt-2 w-64 bg-[#2f2f2f] border border-white/10 rounded-xl shadow-2xl p-1 z-30">
          <div className="px-3 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Model
          </div>

          <ModelOption
            label="GPT-4o"
            desc="Great for most tasks"
            active={selectedModel === "GPT-4o"}
            onClick={() => { setSelectedModel("GPT-4o"); setIsOpen(false); }}
          />
          <ModelOption
            label="GPT-5 (Preview)"
            desc="Reasoning & Deep Thought"
            active={selectedModel === "GPT-5 (Preview)"}
            onClick={() => { setSelectedModel("GPT-5 (Preview)"); setIsOpen(false); }}
          />

          <div className="h-px bg-white/10 my-1" />

          {/* Submenu Trigger */}
          <div
            className="relative"
            onMouseEnter={() => setShowSubmenu(true)}
            onMouseLeave={() => setShowSubmenu(false)}
          >
            <button className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg hover:bg-[#424242] transition-colors text-left group/item">
              <span className="text-sm font-medium text-gray-200">Legacy Models</span>
              <ChevronRight className="w-4 h-4 text-gray-500" />
            </button>

            {/* Nested Submenu (Right side) */}
            {showSubmenu && (
              <div className="absolute top-0 left-full ml-2 w-56 bg-[#2f2f2f] border border-white/10 rounded-xl shadow-2xl p-1 z-40">
                <ModelOption
                  label="GPT-3.5 Turbo"
                  active={selectedModel === "GPT-3.5 Turbo"}
                  onClick={() => { setSelectedModel("GPT-3.5 Turbo"); setIsOpen(false); }}
                />
                <ModelOption
                  label="GPT-4 Legacy"
                  active={selectedModel === "GPT-4 Legacy"}
                  onClick={() => { setSelectedModel("GPT-4 Legacy"); setIsOpen(false); }}
                />
              </div>
            )}
          </div>

        </div>
      )}
    </div>
  )
}

function ModelOption({ label, desc, active, onClick }: { label: string, desc?: string, active?: boolean, onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg hover:bg-[#424242] transition-colors text-left group"
    >
      <div className="flex flex-col">
        <span className="text-sm font-medium text-gray-200">{label}</span>
        {desc && <span className="text-xs text-gray-500">{desc}</span>}
      </div>
      {active && <Check className="w-4 h-4 text-white" />}
    </button>
  )
}

function PlusIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-gray-300">
      <path d="M5 12h14"></path>
      <path d="M12 5v14"></path>
    </svg>
  )
}
