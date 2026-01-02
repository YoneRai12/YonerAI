"use client";

import { useCallback, useEffect, useState, useRef, Suspense } from "react";
import dynamic from "next/dynamic";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

type OcrResult = {
  id: string | number;
  createdAt: string;
  text: string;
  mode?: string;
  previewUrl?: string;
  labels?: string[];
  faces?: number;
  objects?: string[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";

export default function HomePage() {
  const [isDragging, setIsDragging] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState<OcrResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"timeline" | "brain">("timeline");
  const [graphData, setGraphData] = useState<any>({ nodes: [], links: [] });
  const [realtimeText, setRealtimeText] = useState("");

  // タイムライン読み込み
  const fetchTimeline = useCallback(async () => {
    try {
      setError(null);
      const res = await fetch(`${API_BASE}/conversations/latest?limit=20`, {
        cache: "no-store",
      });
      if (!res.ok) throw new Error(`Timeline error: ${res.status}`);
      const data = await res.json();

      const list = (Array.isArray(data) ? data : data.items ?? data.conversations ?? []) as any[];

      const mapped: OcrResult[] = list.map((item) => ({
        id: item.id ?? crypto.randomUUID(),
        createdAt: item.timestamp_iso ?? item.created_at ? new Date(item.created_at * 1000).toISOString() : new Date().toISOString(),
        text: item.ocr_text ?? item.response ?? item.message ?? "",
        mode: item.mode ?? "history",
        // History items might not have structured data yet, or we need to parse it if stored as JSON
        // For now, history is just text
      }));

      setResults(mapped);
    } catch (e: any) {
      console.error(e);
      setError("タイムラインの取得に失敗しました");
    }
  }, []);

  useEffect(() => {
    fetchTimeline();

    // Fetch Graph Data
    fetch(`${API_BASE}/memory/graph`)
      .then(res => res.json())
      .then(data => setGraphData(data))
      .catch(err => console.error("Graph fetch error:", err));

    // WebSocket for Realtime Text
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${wsProtocol}//${window.location.hostname}:8000/api/ws`;
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (event) => {
      const msg = event.data;
      if (msg.startsWith("TRANSCRIPTION:")) {
        const text = msg.replace("TRANSCRIPTION:", "");
        setRealtimeText(text);
        setTimeout(() => setRealtimeText(""), 5000);
      }
    };
    return () => ws.close();
  }, [fetchTimeline]);

  const handleFiles = useCallback(
    async (files: FileList | null) => {
      if (!files || files.length === 0) return;
      const file = files[0];

      // Create Preview URL
      const previewUrl = URL.createObjectURL(file);

      setIsLoading(true);
      setError(null);

      try {
        const form = new FormData();
        form.append("file", file);

        const res = await fetch(`${API_BASE}/ocr`, {
          method: "POST",
          body: form,
        });

        if (!res.ok) throw new Error(`OCR error: ${res.status}`);
        const data = await res.json();

        if (data.error) {
          throw new Error(data.error);
        }

        const createdAt = new Date().toISOString();

        const newResult: OcrResult = {
          id: crypto.randomUUID(),
          createdAt,
          text: data.text || "テキストは検出されませんでした",
          mode: "auto",
          previewUrl,
          labels: data.labels,
          faces: data.faces,
          objects: data.objects
        };

        setResults((prev) => [newResult, ...prev]);
      } catch (e: any) {
        console.error(e);
        setError(`解析エラー: ${e.message}`);
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  const onDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (!isDragging) setIsDragging(true);
  };

  const onDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFiles(e.target.files);
  };



  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-50 flex flex-col items-center relative">
      {/* Real-time Overlay */}
      {realtimeText && (
        <div className="fixed bottom-10 left-1/2 -translate-x-1/2 z-50 pointer-events-none">
          <div className="bg-slate-900/80 backdrop-blur-md border border-cyan-500/50 px-6 py-4 rounded-2xl shadow-[0_0_30px_rgba(34,211,238,0.3)] animate-in fade-in slide-in-from-bottom-4">
            <p className="text-xl font-medium text-cyan-300 typing-effect">
              {realtimeText}
            </p>
          </div>
        </div>
      )}

      <div className="w-full max-w-5xl px-4 py-10 flex flex-col gap-8">
        {/* ヘッダー */}
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl md:text-3xl font-semibold tracking-tight">
              ORA Vision
            </h1>
            <p className="text-sm text-slate-400 mt-2">
              手書きメモや写真を投げるだけで記録に変える あなた専用のOCRアシスタント
            </p>
          </div>
        </header>

        {/* ドラッグ&ドロップエリア */}
        <section
          onDrop={onDrop}
          onDragOver={onDrop}
          onDragLeave={onDragLeave}
          className={[
            "relative rounded-3xl border border-slate-700/70 bg-slate-900/60",
            "backdrop-blur-xl shadow-[0_0_60px_rgba(15,23,42,0.7)]",
            "transition-all duration-200 cursor-pointer",
            "flex flex-col items-center justify-center px-6 py-16",
            isDragging ? "border-cyan-400/80 bg-slate-900/80" : "hover:border-slate-500",
          ].join(" ")}
        >
          <div className="absolute inset-0 -z-10 bg-[radial-gradient(circle_at_top,_rgba(34,211,238,0.15),_transparent_60%)]" />

          <input
            id="file-input"
            type="file"
            accept="image/*,.pdf"
            className="hidden"
            onChange={onFileChange}
          />

          <div className="flex flex-col items-center gap-4">
            <p className="text-sm uppercase tracking-[0.2em] text-cyan-300/80">
              Drop to Analyze
            </p>
            <p className="text-lg md:text-xl font-medium text-slate-100 text-center">
              ここにファイルをドラッグするかクリックして選択
            </p>
            <button
              type="button"
              onClick={() => document.getElementById("file-input")?.click()}
              className="mt-4 px-4 py-2 rounded-full text-sm font-medium border border-cyan-400/70 bg-cyan-400/10 hover:bg-cyan-400/20 transition"
            >
              ファイルを選択
            </button>
            {isLoading && (
              <p className="mt-4 text-xs text-slate-400 animate-pulse">
                解析中 裏で変態ロジックが全力稼働中
              </p>
            )}
            {error && !isLoading && (
              <p className="mt-4 text-xs text-red-400">
                {error}
              </p>
            )}
          </div>
        </section>

        {/* タイムライン / Brain View */}
        <section className="space-y-4">
          {/* Header */}
          <header className="flex items-center justify-between mb-8">
            <h1 className="text-4xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-600">
              ORA Vision
            </h1>
            <div className="flex space-x-4">
              <button
                onClick={() => setActiveTab("timeline")}
                className={`px-4 py-2 rounded-full transition-all ${activeTab === "timeline" ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"}`}
              >
                Timeline
              </button>
              <button
                onClick={() => setActiveTab("brain")}
                className={`px-4 py-2 rounded-full transition-all ${activeTab === "brain" ? "bg-purple-600 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"}`}
              >
                Brain View
              </button>
            </div>
          </header>

          {/* Realtime Overlay */}
          {realtimeText && (
            <div className="fixed bottom-10 left-1/2 transform -translate-x-1/2 bg-black/80 text-cyan-400 px-6 py-3 rounded-full text-xl font-mono border border-cyan-500/50 shadow-[0_0_20px_rgba(0,255,255,0.3)] z-50 animate-pulse">
              {realtimeText}
            </div>
          )}

          {activeTab === "brain" ? (
            <div className="w-full h-[600px] bg-gray-900 rounded-2xl border border-gray-800 overflow-hidden relative">
              <Suspense fallback={<div className="flex items-center justify-center h-full text-gray-400">Loading Brain View...</div>}>
                {graphData && graphData.nodes && graphData.nodes.length > 0 ? (
                  <ForceGraph2D
                    graphData={graphData}
                    nodeLabel="id"
                    nodeColor={node => (node as any).group === 1 ? "#ef4444" : (node as any).group === 2 ? "#3b82f6" : "#10b981"}
                    nodeRelSize={6}
                    linkColor={() => "#4b5563"}
                    backgroundColor="#111827"
                  />
                ) : (
                  <div className="flex items-center justify-center h-full text-gray-500">
                    No brain data available yet.
                  </div>
                )}
              </Suspense>
              <div className="absolute top-4 left-4 bg-black/50 p-2 rounded text-xs text-gray-400">
                Red: ORA | Blue: Users | Green: Topics
              </div>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-slate-300 tracking-wide">
                  履歴タイムライン
                </h2>
                <button
                  type="button"
                  onClick={fetchTimeline}
                  className="text-xs text-slate-400 hover:text-cyan-300 transition"
                >
                  更新
                </button>
              </div>

              {results.length === 0 ? (
                <p className="text-sm text-slate-500">
                  まだ解析履歴はありません 何かファイルを投げてみてください
                </p>
              ) : (
                <div className="space-y-3">
                  {results.map((item) => (
                    <article
                      key={item.id}
                      className="group rounded-2xl border border-slate-700/70 bg-slate-900/70 backdrop-blur-xl px-4 py-4 hover:border-cyan-400/60 transition"
                    >
                      <div className="flex gap-4">
                        {/* Preview Image */}
                        {item.previewUrl && (
                          <div className="w-24 h-24 rounded-xl overflow-hidden bg-slate-800/80 flex-shrink-0 border border-slate-700">
                            <img
                              src={item.previewUrl}
                              alt="preview"
                              className="w-full h-full object-cover"
                            />
                          </div>
                        )}

                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs text-slate-400">
                              {new Date(item.createdAt).toLocaleString()}
                            </span>
                            <span className="text-[10px] px-2 py-1 rounded-full bg-slate-800 text-slate-300">
                              {item.mode}
                            </span>
                          </div>

                          <p className="text-sm text-slate-100 whitespace-pre-wrap line-clamp-4 group-hover:line-clamp-none mb-2">
                            {item.text}
                          </p>

                          {/* Metadata Tags */}
                          <div className="flex flex-wrap gap-2">
                            {item.faces !== undefined && item.faces > 0 && (
                              <span className="text-[10px] px-2 py-0.5 rounded border border-pink-500/30 bg-pink-500/10 text-pink-300">
                                Faces: {item.faces}
                              </span>
                            )}
                            {item.labels?.slice(0, 5).map((label, i) => (
                              <span key={i} className="text-[10px] px-2 py-0.5 rounded border border-cyan-500/30 bg-cyan-500/10 text-cyan-300">
                                #{label}
                              </span>
                            ))}
                            {item.objects?.slice(0, 3).map((obj, i) => (
                              <span key={i} className="text-[10px] px-2 py-0.5 rounded border border-emerald-500/30 bg-emerald-500/10 text-emerald-300">
                                {obj}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </>
          )}
        </section>
      </div>
      {/* Control Panel (Hidden by default, simplistic toggle) */}
      <details className="fixed top-4 right-4 z-50 group">
        <summary className="list-none cursor-pointer bg-slate-900/80 backdrop-blur border border-slate-700 p-2 rounded-full hover:bg-slate-800 transition text-slate-400 hover:text-cyan-400">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.343 3.94c.09-.542.56-.94 1.11-.94h1.093c.55 0 1.02.398 1.11.94l.157.945c.03.18.158.31.33.376.17.066.36.035.5-.083l.86-.718c.418-.35.996-.282 1.34.09l.774.84c.343.374.33.97-.038 1.32l-.658.625c-.14.133-.182.338-.11.52.074.183.25.32.448.347l.888.118c.55.074.96.536.96 1.09v1.18c0 .553-.41 1.015-.96 1.09l-.888.117c-.198.026-.374.164-.448.347-.072.182-.03.387.11.52l.658.625c.368.35.38 .946.038 1.32l-.774.84c-.344.372-.922.44-1.34.09l-.86-.718c-.14-.118-.33-.15-.5-.083-.172.066-.3.196-.33.376l-.157.945c-.09.542-.56.94-1.11.94h-1.094c-.55 0-1.02-.398-1.11-.94l-.157-.945c-.03-.18-.158-.31-.33-.376-.17-.066-.36-.035-.5.083l-.86.718c-.418.35-.996.282-1.34-.09l-.774-.84c-.343-.374-.33-.97.038-1.32l.658-.625c.14-.133.182-.338.11-.52-.074-.183-.25-.32-.448-.347l-.888-.118c-.55-.074-.96-.536-.96-1.09v-1.18c0-.553.41-1.015.96-1.09l.888-.117c.198-.026.374-.164.448-.347.072-.182.03-.387-.11-.52l-.658-.625c-.368-.35-.38-.946-.038-1.32l.774-.84c.344-.372.922-.44 1.34-.09l.86.718c.14.118.33.15.5.083.172.066.3.196.33.376l.157.945z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </summary>
        <div className="absolute top-12 right-0 w-80 bg-slate-950/90 backdrop-blur-xl border border-slate-700/50 rounded-2xl shadow-2xl p-4 animate-in fade-in zoom-in-95 origin-top-right">
          <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            System Control
          </h3>

          <div className="space-y-3">
            <button
              onClick={async () => {
                if (!confirm("Botを再起動しますか？")) return;
                await fetch(`${API_BASE}/system/restart`, { method: "POST" });
                alert("再起動コマンドを送信しました。");
              }}
              className="w-full py-2 px-4 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20 transition text-sm font-medium flex items-center justify-center gap-2"
            >
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
              </svg>
              Restart Bot
            </button>

            <button
              onClick={async () => {
                if (prompt("本当に停止しますか？停止する場合は 'STOP' と入力してください") !== "STOP") return;
                await fetch(`${API_BASE}/system/shutdown`, { method: "POST" });
                alert("シャットダウンコマンドを送信しました。");
              }}
              className="w-full py-2 px-4 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20 transition text-sm font-medium flex items-center justify-center gap-2"
            >
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5.636 5.636a9 9 0 1012.728 0M12 3v9" />
              </svg>
              Shutdown App
            </button>

            <div className="mt-4 pt-4 border-t border-slate-800">
              <div className="text-xs text-slate-500 mb-2 flex justify-between">
                <span>Recent Logs</span>
                <button
                  onClick={() => window.open(`${API_BASE}/logs/stream`, '_blank')}
                  className="text-cyan-400 hover:underline"
                >
                  Open Raw
                </button>
              </div>
              <div className="h-32 bg-slate-950 rounded border border-slate-800 p-2 overflow-y-auto text-[10px] font-mono text-slate-400">
                <p className="opacity-50 italic">Log stream not connected in preview.</p>
              </div>
            </div>
          </div>
        </div>
      </details>
      {/* End Control Panel */}
    </main>
  );
}
