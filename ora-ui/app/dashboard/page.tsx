"use client";

import React, { useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence, useSpring, useMotionValue, Reorder, LayoutGroup } from "framer-motion";
import {
    Activity,
    Pause,
    Play,
    Zap,
    Database,
    Cpu,
    Server,
    Lock,
    Cloud,
    CheckCircle2,
    Loader2,
    Camera,
    EyeOff,
    RefreshCcw,
    LayoutGrid,
    List,
    Eye,
    Coins,
    Sparkles,
    User as UserIcon,
    Bot,
    GripVertical,
    AlertTriangle,
    X,
    Rocket // Added for Nitro
} from "lucide-react";

// Animated Counter Component & Global Motion Config
// Cupertino Fluid Physics (Critically Damped - No Bounce, Pure Precision)
const SPRING_FLUID = { type: "spring", stiffness: 150, damping: 25, mass: 1 } as const;
const SPRING_TACTILE = { type: "spring", stiffness: 300, damping: 35, mass: 1 } as const;
const STAGGER_STANDARD = 0.06;
const STAGGER_SLOW = 0.1;
const STAGGER_FAST = 0.05;

const SPRING_CONFIG = { stiffness: 120, damping: 25, mass: 1 } as const;
const SPRING_SLOW = { stiffness: 40, damping: 20, mass: 2 } as const; // Slower, heavier feel for bars/counters

// Hardcoded limits
// Limits State (Default to hardcoded, update via API)
// Hardcoded limits as fallback
const DEFAULT_LIMIT_HIGH = 1000000; // Free Tier Limit
const DEFAULT_LIMIT_STABLE = 10000000; // Free Tier Limit
const LIMIT_OPT_VISUAL = 10000000; // Free Tier Limit

const topCardVariants = {
    hidden: { opacity: 0, y: 20, scale: 0.95, filter: "blur(10px)" },
    visible: (i: number) => ({
        opacity: 1,
        y: 0,
        scale: 1,
        filter: "blur(0px)",
        transition: {
            delay: i * 0.05,
            ...SPRING_FLUID
        }
    })
};

type SpotlightPoint = { x: number; y: number };

const spotlightRects = new WeakMap<HTMLElement, DOMRect>();
const spotlightRafs = new WeakMap<HTMLElement, number>();
const spotlightPoints = new WeakMap<HTMLElement, SpotlightPoint>();

const updateSpotlightPosition = (el: HTMLElement, clientX: number, clientY: number) => {
    spotlightPoints.set(el, { x: clientX, y: clientY });
    if (spotlightRafs.has(el)) {
        return;
    }

    const rafId = requestAnimationFrame(() => {
        const rect = spotlightRects.get(el) || el.getBoundingClientRect();
        spotlightRects.set(el, rect);
        const point = spotlightPoints.get(el);
        if (!point) {
            spotlightRafs.delete(el);
            return;
        }
        el.style.setProperty("--x", `${point.x - rect.left}px`);
        el.style.setProperty("--y", `${point.y - rect.top}px`);
        spotlightRafs.delete(el);
    });

    spotlightRafs.set(el, rafId);
};

const activateSpotlight = (el: HTMLElement, clientX: number, clientY: number) => {
    spotlightRects.set(el, el.getBoundingClientRect());
    el.classList.add("spotlight-active");
    updateSpotlightPosition(el, clientX, clientY);
};

const deactivateSpotlight = (el: HTMLElement) => {
    el.classList.remove("spotlight-active");
    spotlightRects.delete(el);
    const rafId = spotlightRafs.get(el);
    if (rafId !== undefined) {
        cancelAnimationFrame(rafId);
    }
    spotlightRafs.delete(el);
    spotlightPoints.delete(el);
};

function AnimatedCounter({ value, formatter, delay = 0 }: { value: number, formatter?: (v: number) => string, delay?: number }) {
    const ref = useRef<HTMLSpanElement>(null);
    const motionValue = useMotionValue(0);
    const springValue = useSpring(motionValue, SPRING_SLOW);
    const format = formatter || ((v) => Math.round(v).toLocaleString());

    useEffect(() => {
        if (delay > 0) {
            const timer = setTimeout(() => {
                motionValue.set(value);
            }, delay * 1000);
            return () => clearTimeout(timer);
        } else {
            motionValue.set(value);
        }
    }, [value, motionValue, delay]);

    useEffect(() => {
        return springValue.on("change", (latest) => {
            if (ref.current) {
                ref.current.textContent = format(latest);
            }
        });
    }, [springValue, format]);

    return <span ref={ref}>{format(value)}</span>;
}

// CircularProgress with Determinate Animation
function CircularProgress({ size = 24, strokeWidth = 3, color = "text-yellow-500", label, percent = 0 }: { size?: number, strokeWidth?: number, color?: string, label?: string, percent?: number }) {
    const radius = (size - strokeWidth) / 2;
    const circumference = radius * 2 * Math.PI;
    const offset = circumference - (percent / 100) * circumference;

    return (
        <div className={`relative flex items-center justify-center ${color}`} style={{ width: size, height: size }}>
            {/* Background Ring */}
            <svg className="w-full h-full rotate-[-90deg]">
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="transparent"
                    stroke="currentColor"
                    strokeWidth={strokeWidth}
                    strokeOpacity={0.2}
                />
                {/* Progress Ring (Determinate) */}
                <motion.circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="transparent"
                    stroke="currentColor"
                    strokeWidth={strokeWidth}
                    strokeDasharray={circumference}
                    initial={{ strokeDashoffset: circumference }}
                    animate={{ strokeDashoffset: offset }}
                    transition={SPRING_FLUID}
                />
            </svg>
            {/* Label Overlay */}
            {label && (
                <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-[8px] font-bold text-white/90 font-mono tracking-tighter leading-none">{label}</span>
                </div>
            )}
        </div>
    );
}

// Isolated Clock Component to prevent full-page re-renders
function SystemClock() {
    const [currentTime, setCurrentTime] = useState(new Date());
    useEffect(() => {
        const timer = setInterval(() => setCurrentTime(new Date()), 1000);
        return () => clearInterval(timer);
    }, []);

    return (
        <div className="flex flex-row md:flex-col items-center md:items-end gap-3 md:gap-0">
            <div className="text-xl md:text-4xl font-mono text-white tracking-widest leading-none">
                {currentTime.toLocaleDateString("ja-JP")}
            </div>
            <div className="text-lg md:text-2xl font-mono text-cyan-500 tracking-widest leading-none mt-1">
                {currentTime.toLocaleTimeString("ja-JP")}
            </div>
        </div>
    );
}

// Types
interface CostState {
    total_usd: number;
    daily_tokens: {
        high: number;
        stable: number;
        burn: number;
        optimization: number;
    };
    lifetime_tokens: {
        high: number;
        stable: number;
        burn: number;
        optimization: number;
        openai_sum?: number;
    };
    last_reset: string;
    unlimited_mode?: boolean;
    unlimited_users?: string[];
}

interface User {
    discord_user_id: string;
    real_user_id?: string;
    display_name: string;
    status: string;
    impression: string | null;
    created_at: string;
    points: number;
    cost_usage: {
        high: number;
        stable: number;
        optimization: number;
        burn: number;
        total_usd: number;
    } | null;
    last_message?: string;
    guild_name?: string;
    guild_id?: string;
    discord_status?: string;
    is_bot?: boolean; // Added
    avatar_url?: string | null;
    banner_url?: string | null;
    mode?: string; // Restored for backward compatibility
    message_count?: number; // New: Analyzed message count
    traits?: string[]; // New: Extracted traits
    is_nitro?: boolean; // New: Nitro status
    last_updated?: string; // New: Last optimization time
}

interface UserProfile {
    name: string;
    traits?: string[];
    history_summary?: string;
    impression?: string;
    deep_profile?: string;    // New: Deep Analysis
    future_pred?: string;     // New: Future Prediction
    relationship?: string;   // New: Interaction Analysis

    // 4-Layer Architecture
    layer1_session_meta?: any; // New: Session Metadata
    layer2_user_memory?: {
        facts: string[];
        traits: string[];
        impression: string;
        interests: string[];
    };
    layer3_recent_summaries?: any[]; // New: List of summaries
    layer3_summary?: {
        global_summary: string;
        deep_profile: string;
        future_pred: string;
    };

    last_context?: {
        content: string;
        timestamp: string;
        channel: string;
        guild?: string;
    }[];
    last_updated: string;
}

interface UserDetail {
    specific: UserProfile | null;
    general: UserProfile | null;
}

interface HistoryData {
    timeline: {
        date: string;
        high: number;
        stable: number;
        optimization: number;
        burn: number;
        usd: number;
    }[];
    breakdown: {
        [key: string]: {
            total: number;
            [model: string]: number;
        };
    };
    hourly: {
        hour: string;
        high: number;
        stable: number;
        optimization: number;
        burn: number;
        usd: number;
    }[];
}

// Detailed Stats Interfaces
interface ModelStat {
    name: string;
    value: number;
    color: string;
}

interface TimePoint {
    time: string;
    value: number;
}

interface DetailedStats {
    models: ModelStat[];
    timeline: TimePoint[];
}

type LaneKey = "high" | "stable" | "optimization" | "burn" | "usd";

const LANE_META: Record<Exclude<LaneKey, "burn">, { label: string; chip: string; text: string; bar: string; ring: string }> = {
    high: {
        label: "高速推論",
        chip: "bg-cyan-500/15 text-cyan-200 border-cyan-500/40",
        text: "text-cyan-300",
        bar: "bg-cyan-500",
        ring: "ring-cyan-500/40"
    },
    stable: {
        label: "共有モデル (Shared)",
        chip: "bg-green-500/15 text-green-200 border-green-500/40",
        text: "text-green-300",
        bar: "bg-green-500",
        ring: "ring-green-500/40"
    },
    optimization: {
        label: "自動最適化 (Opt)",
        chip: "bg-purple-500/15 text-purple-200 border-purple-500/40",
        text: "text-purple-300",
        bar: "bg-purple-500",
        ring: "ring-purple-500/40"
    },
    usd: {
        label: "USD",
        chip: "bg-neutral-500/15 text-neutral-200 border-neutral-400/40",
        text: "text-neutral-200",
        bar: "bg-neutral-200",
        ring: "ring-neutral-400/40"
    }
};

const pad2 = (value: number) => value.toString().padStart(2, "0");

const formatLocalDateKey = (d: Date) => {
    const year = d.getFullYear();
    const month = pad2(d.getMonth() + 1);
    const day = pad2(d.getDate());
    return `${year}-${month}-${day}`;
};

const formatLocalHourKey = (d: Date) => {
    const year = d.getFullYear();
    const month = pad2(d.getMonth() + 1);
    const day = pad2(d.getDate());
    const hour = pad2(d.getHours());
    return `${year}-${month}-${day}T${hour}`;
};

const getLaneValue = (entry: { [key: string]: any }, lane: LaneKey) => {
    if (lane === "usd") return entry.usd || 0;
    return entry[lane] || 0;
};

const buildWeeklySeries = (history: HistoryData | null, lane: LaneKey) => {
    if (!history) return [];
    const map = new Map<string, number>();
    for (const item of history.timeline || []) {
        map.set(item.date, getLaneValue(item, lane));
    }
    const series: { key: string; label: string; value: number }[] = [];
    for (let i = 6; i >= 0; i--) {
        const d = new Date();
        d.setHours(0, 0, 0, 0);
        d.setDate(d.getDate() - i);
        const key = formatLocalDateKey(d);
        series.push({
            key,
            label: `${d.getMonth() + 1}/${d.getDate()}`,
            value: map.get(key) ?? 0
        });
    }
    return series;
};

const buildHourlySeries = (history: HistoryData | null, lane: LaneKey) => {
    if (!history) return [];
    const map = new Map<string, number>();
    for (const item of history.hourly || []) {
        map.set(item.hour, getLaneValue(item, lane));
    }
    const series: { key: string; label: string; value: number }[] = [];
    const now = new Date();
    now.setMinutes(0, 0, 0);
    for (let i = 23; i >= 0; i--) {
        const d = new Date(now);
        d.setHours(d.getHours() - i);
        const key = formatLocalHourKey(d);
        series.push({
            key,
            label: `${pad2(d.getHours())}:00`,
            value: map.get(key) ?? 0
        });
    }
    return series;
};

// Mock Data Generator
const generateMockStats = (type: string): DetailedStats => {
    const hours = Array.from({ length: 24 }, (_, i) => i);
    const timeline = hours.map(h => ({
        time: `${h}:00`,
        value: Math.floor(Math.random() * (type === 'usd' ? 100 : 5000))
    }));

    let models: ModelStat[] = [];
    if (type === 'high') {
        models = [
            { name: "Ministral 3B", value: 45, color: "bg-cyan-500" },
            { name: "Qwen 2.5 7B", value: 30, color: "bg-cyan-400" },
            { name: "Llama 3 8B", value: 25, color: "bg-cyan-300" }
        ];
    } else if (type === 'stable') {
        models = [
            { name: "GPT-4o", value: 60, color: "bg-green-500" },
            { name: "Claude 3.5", value: 30, color: "bg-green-400" },
            { name: "Gemini Pro", value: 10, color: "bg-green-300" }
        ];
    } else if (type === 'optimization') {
        models = [
            { name: "nomic-embed", value: 50, color: "bg-purple-500" },
            { name: "BERT", value: 30, color: "bg-purple-400" },
            { name: "CLIP", value: 20, color: "bg-purple-300" }
        ];
    } else if (type === 'usd') {
        models = [
            { name: "OpenAI API", value: 40, color: "bg-neutral-200" },
            { name: "Anthropic", value: 35, color: "bg-neutral-400" },
            { name: "Electricity", value: 25, color: "bg-neutral-600" }
        ];
    }
    return { models, timeline };
};

// Visual Components for Stats
const ModelBreakdown = ({ models }: { models: ModelStat[] }) => (
    <div className="space-y-3">
        <h4 className="text-[10px] font-bold uppercase tracking-widest text-neutral-500 mb-2">Model Distribution</h4>
        {models.map((m, i) => (
            <div key={i} className="flex items-center gap-3 text-xs">
                <div className={`w-2 h-2 rounded-full ${m.color}`} />
                <div className="flex-1 flex justify-between">
                    <span className="text-neutral-300 font-mono">{m.name}</span>
                    <span className="text-neutral-500">{m.value}%</span>
                </div>
                <div className="w-24 h-1.5 bg-neutral-800 rounded-full overflow-hidden">
                    <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${m.value}%` }}
                        transition={{ duration: 1, delay: i * 0.1 }}
                        className={`h-full ${m.color}`}
                    />
                </div>
            </div>
        ))}
    </div>
);

const DotGraph = ({ data, color }: { data: TimePoint[], color: string }) => {
    const max = Math.max(...data.map(d => d.value));
    return (
        <div className="h-full flex flex-col">
            <h4 className="text-[10px] font-bold uppercase tracking-widest text-neutral-500 mb-2">24h Activity</h4>
            <div className="flex items-end justify-between flex-1 gap-[2px] h-32">
                {data.map((d, i) => {
                    const height = (d.value / max) * 100;
                    return (
                        <motion.div
                            key={i}
                            initial={{ height: 0 }}
                            animate={{ height: `${height}%` }}
                            transition={{ type: "spring", stiffness: 300, damping: 30, delay: i * 0.02 }}
                            className={`w-full min-w-[4px] rounded-t-sm opacity-60 hover:opacity-100 transition-opacity ${color}`}
                            title={`${d.time}: ${d.value}`}
                        />
                    );
                })}
            </div>
            <div className="flex justify-between mt-1 text-[8px] text-neutral-600 font-mono">
                <span>00:00</span>
                <span>12:00</span>
                <span>23:00</span>
            </div>
        </div>
    );
};

function HistoryModal({ lane, onClose }: { lane: string, onClose: () => void }) {
    const [history, setHistory] = useState<HistoryData | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchHistory = async () => {
            try {
                const apiBase = "";
                const res = await fetch(`${apiBase}/api/dashboard/history`);
                if (res.ok) {
                    const data = await res.json();
                    setHistory(data.data);
                }
            } catch (e) {
                console.error(e);
            } finally {
                setLoading(false);
            }
        };
        fetchHistory();
    }, []);

    // Helper: Get data for specific lane
    const getLaneData = (item: any) => {
        if (lane === "usd") return item.usd;
        return item[lane] || 0;
    };

    // Find max for scaling
    const maxVal = history?.timeline.reduce((acc, item) => Math.max(acc, getLaneData(item)), 0) || 1;

    // Color mapping
    const colorMap: Record<string, string> = {
        high: "text-cyan-400 bg-cyan-500",
        stable: "text-green-400 bg-green-500",
        optimization: "text-purple-400 bg-purple-500",
        usd: "text-white bg-neutral-500",
    };
    const theme = colorMap[lane] || colorMap["usd"];
    const [textColor, bgColor] = theme.split(" ");

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm" onClick={onClose}>
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="bg-neutral-900 border border-neutral-800 rounded-2xl w-full max-w-4xl max-h-[85vh] overflow-hidden flex flex-col shadow-2xl relative"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="p-6 border-b border-neutral-800 flex justify-between items-center bg-neutral-950/50">
                    <h2 className={`text-2xl font-black uppercase tracking-tight flex items-center gap-3 ${textColor}`}>
                        {lane === "usd" ? "Cost History" : `${lane} Lane History`}
                    </h2>
                    <button onClick={onClose} className="p-2 text-neutral-500 hover:text-white bg-neutral-800 rounded-full">
                        <EyeOff className="w-5 h-5" />
                    </button>
                </div>

                {loading ? (
                    <div className="flex items-center justify-center h-64">
                        <Loader2 className={`w-8 h-8 animate-spin ${textColor}`} />
                    </div>
                ) : history ? (
                    <div className="grid grid-cols-1 md:grid-cols-3 h-full overflow-hidden">
                        {/* Chart Area */}
                        <div className="col-span-2 p-6 overflow-y-auto border-r border-neutral-800">
                            <h3 className="text-neutral-500 text-xs font-bold uppercase tracking-wider mb-6">30-Day Activity</h3>

                            <div className="space-y-3">
                                {history.timeline.slice(-30).map((day, i) => {
                                    const val = getLaneData(day);
                                    const percent = (val / maxVal) * 100;
                                    return (
                                        <div key={i} className="flex items-center gap-4 text-xs group">
                                            <span className="w-20 text-right font-mono text-neutral-600">{day.date.slice(5)}</span>
                                            <div className="flex-1 h-6 bg-neutral-800/50 rounded flex items-center overflow-hidden relative">
                                                <motion.div
                                                    initial={{ width: 0 }}
                                                    animate={{ width: `${percent}%` }}
                                                    transition={{ delay: i * 0.02, duration: 0.5, ease: "easeOut" }}
                                                    className={`h-full opacity-80 group-hover:opacity-100 ${bgColor}`}
                                                />
                                                <span className="absolute left-2 text-white font-mono font-bold drop-shadow-md">
                                                    {lane === "usd" ? `$${val.toFixed(2)}` : val.toLocaleString()}
                                                </span>
                                            </div>
                                        </div>
                                    )
                                })}
                            </div>
                        </div>

                        {/* Breakdown Area */}
                        <div className="col-span-1 p-6 bg-neutral-950/30 overflow-y-auto">
                            <h3 className="text-neutral-500 text-xs font-bold uppercase tracking-wider mb-6">Usage Breakdown (Lifetime)</h3>

                            {history.breakdown[lane] ? (
                                <div className="space-y-4">
                                    {Object.entries(history.breakdown[lane])
                                        .filter(([k]) => k !== "total")
                                        .sort(([, a], [, b]) => b - a)
                                        .map(([model, count], i) => (
                                            <div key={i} className="bg-neutral-900 border border-neutral-800 p-3 rounded-lg">
                                                <div className="text-neutral-300 font-medium text-sm mb-1">{model}</div>
                                                <div className={`text-xl font-mono font-bold ${textColor}`}>
                                                    {count.toLocaleString()} <span className="text-xs text-neutral-600">tokens</span>
                                                </div>
                                            </div>
                                        ))}
                                    {Object.keys(history.breakdown[lane]).length <= 1 && (
                                        <div className="text-neutral-600 italic text-sm">No detailed breakdown available.</div>
                                    )}
                                </div>
                            ) : (
                                <div className="text-neutral-500">No data available for this lane.</div>
                            )}
                        </div>
                    </div>
                ) : null}
            </motion.div>
        </div>
    );
}

function UserDetailModal({ userId, initialUser, onClose }: { userId: string, initialUser: User | null, onClose: () => void }) {
    const [detail, setDetail] = useState<UserDetail | null>(() => {
        if (!initialUser) return null;
        // Construct temporary profile from initialUser
        return {
            specific: null,
            general: {
                name: initialUser.display_name,
                impression: initialUser.impression || "読み込み中...",
                last_updated: new Date().toISOString(),
                traits: [],
                history_summary: "詳細データを取得中...",
                deep_profile: "詳細分析を取得中...",
                future_pred: "...",
                relationship: "..."
            } as UserProfile
        };
    });
    const [feedback, setFeedback] = useState<{ msg: string; type: 'success' | 'error' } | null>(null);
    const [loading, setLoading] = useState(true);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [isSuccess, setIsSuccess] = useState(false);

    useEffect(() => {
        const fetchDetail = async () => {
            try {
                // If we have initial data, we are technically "loading fresh data" but "displaying cached data"
                // setLoading(true); // Don't block UI if we have data

                const apiBase = "";
                const ts = new Date().getTime();
                const res = await fetch(`${apiBase}/api/dashboard/users/${userId}?t=${ts}`, { cache: "no-store" });
                if (res.ok) {
                    const data = await res.json();
                    setDetail(data.data);
                }
            } catch (e) {
                console.error(e);
            } finally {
                setLoading(false);
            }
        };
        fetchDetail();
    }, [userId]);

    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, transition: { duration: 0.3 }, pointerEvents: "none" }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
            onClick={onClose}
        >
            <motion.div
                layoutId={userId}
                className="bg-neutral-900 border border-neutral-800 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col shadow-2xl relative"
                onClick={(e) => e.stopPropagation()}
                transition={{ type: "spring", stiffness: 300, damping: 30 }}
            >

                {/* Close Button */}
                <div className="absolute top-4 right-4 z-20 flex items-center gap-2">
                    <button
                        onClick={async (e) => {
                            e.stopPropagation();
                            try {
                                const res = await fetch(`/api/dashboard/users/${userId}/optimize`, { method: "POST" });
                                if (res.ok) {
                                    setFeedback({ msg: "Optimization Queue: Added!", type: "success" });
                                    setTimeout(() => setFeedback(null), 3000);
                                } else {
                                    setFeedback({ msg: "Failed to queue.", type: "error" });
                                }
                            } catch (err) {
                                setFeedback({ msg: "Connection Error.", type: "error" });
                            }
                        }}
                        className="p-2 text-cyan-400 hover:text-cyan-200 bg-cyan-950/50 hover:bg-cyan-900/80 rounded-full transition-all border border-cyan-500/30 shadow-[0_0_10px_rgba(6,182,212,0.2)] relative"
                        title="Force Immediate Optimization"
                    >
                        <Zap className="w-5 h-5" />

                        {/* Inline Feedback Overlay */}
                        <AnimatePresence>
                            {feedback && (
                                <motion.div
                                    initial={{ opacity: 0, y: 10, scale: 0.9 }}
                                    animate={{ opacity: 1, y: 0, scale: 1 }}
                                    exit={{ opacity: 0, y: -10, scale: 0.9 }}
                                    className={`absolute top-10 right-0 w-max px-3 py-1.5 rounded-lg text-xs font-bold border backdrop-blur-md z-50
                                        ${feedback.type === 'success'
                                            ? 'bg-cyan-950/90 text-cyan-200 border-cyan-500/50 shadow-[0_0_15px_rgba(6,182,212,0.3)]'
                                            : 'bg-red-950/90 text-red-200 border-red-500/50 shadow-[0_0_15px_rgba(239,68,68,0.3)]'}`}
                                >
                                    {feedback.msg}
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </button>

                    <button onClick={onClose} className="p-2 text-neutral-400 hover:text-white bg-black/20 rounded-full transition-colors border border-white/5">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Show Spinner ONLY if no data at all (should rarely happen with initialUser) */}
                {!detail && loading ? (
                    <div className="flex items-center justify-center h-64">
                        <Loader2 className="w-8 h-8 animate-spin text-cyan-500" />
                    </div>
                ) : detail ? (
                    <>
                        {/* Loading Indicator Overlay (Subtle) */}
                        {loading && (
                            <div className="absolute top-4 left-4 z-20 flex items-center gap-2 bg-black/50 px-2 py-1 rounded-full border border-white/10 backdrop-blur-md">
                                <Loader2 className="w-3 h-3 animate-spin text-cyan-400" />
                                <span className="text-[10px] text-cyan-200">最新情報を取得中...</span>
                            </div>
                        )}
                        {/* Impression Header - Use Specific first, fallback to General */}
                        <motion.div
                            className={`p-6 pt-10 flex flex-col items-center justify-center border-b border-white/5 relative overflow-hidden shrink-0 min-h-[160px]
                                ${(initialUser as any)?.banner_url ? "" : "bg-gradient-to-r from-cyan-950/50 to-purple-950/50"}
                            `}
                        >
                            {/* Banner Image Background */}
                            {(initialUser as any)?.banner_url && (
                                <div className="absolute inset-0 z-0">
                                    <img
                                        src={(initialUser as any).banner_url}
                                        alt=""
                                        className="w-full h-full object-cover opacity-60"
                                    />
                                    <div className="absolute inset-0 bg-gradient-to-t from-neutral-900 via-neutral-900/40 to-transparent" />
                                </div>
                            )}

                            <div className="absolute inset-0 bg-[url('/noise.png')] opacity-10 mix-blend-overlay z-[1]"></div>
                            <motion.div
                                layoutId={`avatar-${userId}`}
                                className="w-20 h-20 rounded-2xl flex items-center justify-center font-bold text-4xl shadow-2xl mb-4 bg-gradient-to-br from-neutral-800 to-neutral-900 text-neutral-400 border border-white/10 relative z-10 overflow-hidden"
                            >
                                {(initialUser as any)?.avatar_url ? (
                                    <motion.img
                                        src={(initialUser as any).avatar_url}
                                        alt=""
                                        className="w-full h-full rounded-2xl object-cover"
                                    />
                                ) : (
                                    initialUser?.display_name ? initialUser.display_name.charAt(0).toUpperCase() : "?"
                                )}
                            </motion.div>
                            <motion.h2
                                className="text-2xl font-black text-white text-center tracking-tight relative z-10 leading-tight min-h-[2rem]"
                            >
                                {detail.specific?.impression || detail.general?.impression || "分析中..."}
                            </motion.h2>
                            <motion.p
                                className="text-cyan-400/80 font-mono text-xs mt-2 uppercase tracking-widest relative z-10"
                            >
                                {detail.specific ? "Server Priority Memory" : "Global Identity"}
                            </motion.p>
                        </motion.div>

                        {/* Content Scroll */}
                        <div className="overflow-y-auto p-4 md:p-6 space-y-10 [&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar-track]:bg-neutral-900 [&::-webkit-scrollbar-thumb]:bg-neutral-700 [&::-webkit-scrollbar-thumb]:rounded-full hover:[&::-webkit-scrollbar-thumb]:bg-neutral-600">

                            {/* Re-Optimize Button (Sticky-ish or Top) */}
                            {/* Re-Optimize Button (Sticky-ish or Top) */}
                            <button
                                className={`px-3 py-1.5 border text-[10px] font-bold uppercase tracking-widest rounded-lg transition-colors flex items-center gap-2
                                    ${isRefreshing || isSuccess ? "bg-emerald-900/20 text-emerald-400 border-emerald-700/50 cursor-not-allowed" : "bg-cyan-900/20 hover:bg-cyan-900/40 border-cyan-800/50 text-cyan-400"}
                                `}
                                disabled={isRefreshing || isSuccess}
                                onClick={async () => {
                                    setIsRefreshing(true);
                                    try {
                                        const res = await fetch(`/api/dashboard/users/${userId}/optimize`, { method: "POST" });
                                        if (res.ok) {
                                            const data = await res.json();
                                            console.log(`Success: ${data.message}`);
                                            setIsRefreshing(false);
                                            setIsSuccess(true);
                                            // Wait for backend + Show Approved message
                                            setTimeout(() => onClose(), 1500);
                                        } else {
                                            let errMsg = "Unknown Error";
                                            try {
                                                const err = await res.json();
                                                errMsg = err.detail || JSON.stringify(err);
                                            } catch (e) {
                                                const text = await res.text();
                                                errMsg = text || res.statusText;
                                            }
                                            console.error(`Failed: ${errMsg}`);
                                            alert(`エラー: ${errMsg}`);
                                            setIsRefreshing(false);
                                        }
                                    } catch (e) {
                                        console.error(`Error: ${e}`);
                                        alert(`通信エラー: ${e}`);
                                        setIsRefreshing(false);
                                    }
                                }}
                            >
                                {isSuccess ? <CheckCircle2 className="w-3 h-3" /> : isRefreshing ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
                                {isSuccess ? "承認しました" : isRefreshing ? "送信中..." : "Force Refresh"}
                            </button>

                            {/* 1. Server Specific Profile (TOP) */}
                            {detail.specific && (
                                <motion.section
                                    initial={{ opacity: 0, y: 20 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: 0.1, duration: 0.4 }}
                                    className="space-y-6"
                                >
                                    <div className="flex items-center gap-2">
                                        <div className="h-0.5 flex-1 bg-gradient-to-r from-cyan-500/50 to-transparent" />
                                        <span className="text-cyan-500 font-black text-[10px] uppercase tracking-[0.2em] whitespace-nowrap">Server Specific Memory</span>
                                        <div className="h-0.5 w-12 bg-neutral-800" />
                                    </div>
                                    <ProfileContent profile={detail.specific} theme="cyan" />
                                </motion.section>
                            )}

                            {/* 2. General Global Profile (BOTTOM) */}
                            {detail.general && (
                                <motion.section
                                    initial={{ opacity: 0, y: 20 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: 0.2, duration: 0.4 }}
                                    className="space-y-6"
                                >
                                    <div className="flex items-center gap-2">
                                        <div className="h-0.5 flex-1 bg-gradient-to-r from-purple-500/50 to-transparent" />
                                        <span className="text-purple-400 font-black text-[10px] uppercase tracking-[0.2em] whitespace-nowrap">General Identity Memory</span>
                                        <div className="h-0.5 w-12 bg-neutral-800" />
                                    </div>
                                    <ProfileContent profile={detail.general} theme="purple" />
                                </motion.section>
                            )}

                            {!detail.specific && !detail.general && (
                                <div className="p-8 text-center text-neutral-600 italic">No memory data found for this identifier.</div>
                            )}
                        </div>
                    </>
                ) : (
                    <div className="p-8 text-center text-neutral-500 font-mono">FAILED TO LOAD ORA_CORE_STREAM</div>
                )}
            </motion.div>
        </motion.div>
    );
}

// Custom Typewriter Component
function TypewriterText({ text, speed = 8, delay = 0 }: { text: string; speed?: number; delay?: number }) {
    const [displayed, setDisplayed] = useState("");
    const [started, setStarted] = useState(false);

    useEffect(() => {
        // Reset on text change
        setDisplayed("");
        setStarted(false);

        const startTimeout = setTimeout(() => {
            setStarted(true);
            let i = 0;
            // Adjust speed based on length to prevent too slow rendering for long text
            const dynamicSpeed = Math.max(1, Math.min(speed, 5000 / text.length));

            const timer = setInterval(() => {
                i++;
                if (i <= text.length) {
                    setDisplayed(text.slice(0, i));
                } else {
                    clearInterval(timer);
                }
            }, dynamicSpeed);
            return () => clearInterval(timer);
        }, delay);
        return () => clearTimeout(startTimeout);
    }, [text, speed, delay]);

    return <span className="whitespace-pre-wrap">{started ? displayed : ""}</span>;
}

// Sub-component for individual profile display (Refactored for 4-Layer Memory)
function ProfileContent({ profile, theme }: { profile: UserProfile, theme: "cyan" | "purple" }) {
    const accentColor = theme === "cyan" ? "text-cyan-400" : "text-purple-400";
    const borderColor = theme === "cyan" ? "border-cyan-800/30" : "border-purple-800/30";
    const bgColor = theme === "cyan" ? "bg-cyan-950/10" : "bg-purple-950/10";
    const panelBg = "bg-neutral-900/50";

    // Data Resolution
    const l1 = profile.layer1_session_meta || {}; // New Layer 1
    const l2 = profile.layer2_user_memory || {
        facts: [],
        traits: profile.traits || [],
        impression: profile.impression || "Analyzing...",
        interests: []
    };

    // Layer 3 Resolution: List (New) vs Object (Legacy)
    const l3List = profile.layer3_recent_summaries; // Array
    const l3Legacy = profile.layer3_summary || {
        global_summary: profile.history_summary || "No summary available.",
        deep_profile: profile.deep_profile || "",
        future_pred: profile.future_pred || ""
    };

    return (
        <div className="space-y-6">

            {/* Layer 1: Session Metadata (Ephemeral) */}
            <div className={`p-3 rounded-lg border ${borderColor} bg-neutral-900/30 flex flex-col gap-2`}>
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs font-bold text-neutral-400">
                        <Activity className="w-3 h-3" />
                        <span>LAYER 1: SESSION METADATA</span>
                    </div>
                    <span className="text-[10px] text-neutral-600 font-mono">
                        UPDATED: {new Date(profile.last_updated).toLocaleString("ja-JP", { timeZone: "Asia/Tokyo" })} (JST)
                    </span>
                </div>
                {Object.keys(l1).length > 0 ? (
                    <div className="flex flex-wrap gap-2 mt-1">
                        {l1.environment && (
                            <span className="px-2 py-0.5 rounded bg-neutral-800 text-neutral-300 text-[10px] border border-neutral-700 font-mono">
                                ENV: {l1.environment}
                            </span>
                        )}
                        {l1.device_est && (
                            <span className="px-2 py-0.5 rounded bg-neutral-800 text-neutral-300 text-[10px] border border-neutral-700 font-mono">
                                DEVICE: {l1.device_est}
                            </span>
                        )}
                        {l1.mood && (
                            <span className="px-2 py-0.5 rounded bg-neutral-800 text-neutral-300 text-[10px] border border-neutral-700 font-mono">
                                MOOD: {l1.mood}
                            </span>
                        )}
                        {l1.activity && (
                            <span className="px-2 py-0.5 rounded bg-neutral-800 text-neutral-300 text-[10px] border border-neutral-700 font-mono">
                                ACT: {l1.activity}
                            </span>
                        )}
                    </div>
                ) : (
                    <div className="text-[10px] text-neutral-600 italic pl-5">
                        Waiting for next analysis...
                    </div>
                )}
            </div>

            {/* Layer 2: User Memory (Facts & Traits) */}
            <div className={`p-4 rounded-xl ${panelBg} border ${borderColor} space-y-4`}>
                <div className="flex items-center gap-2 mb-2">
                    <UserIcon className={`w-4 h-4 ${accentColor}`} />
                    <h3 className="text-sm font-bold text-white uppercase tracking-wider">Layer 2: User Memory</h3>
                </div>

                {/* Facts (New) */}
                {l2.facts && l2.facts.length > 0 && (
                    <div className="space-y-1">
                        <span className="text-[10px] text-neutral-500 uppercase tracking-widest font-bold">Facts (Anchor)</span>
                        <div className="flex flex-wrap gap-2">
                            {l2.facts.map((f, i) => (
                                <span key={i} className="px-2 py-0.5 bg-neutral-800 rounded text-[11px] text-neutral-300 border border-neutral-700/50">
                                    {f}
                                </span>
                            ))}
                        </div>
                    </div>
                )}

                {/* Traits & Interests */}
                <div className="space-y-4">
                    <div className="space-y-1">
                        <span className="text-[10px] text-neutral-500 uppercase tracking-widest font-bold">Traits</span>
                        <div className="flex flex-wrap gap-1.5">
                            {(l2.traits || []).map((t, i) => (
                                <span key={i} className={`px-2 py-0.5 rounded-full text-[10px] bg-neutral-800/80 text-neutral-400 border border-neutral-700/50`}>
                                    #{t}
                                </span>
                            ))}
                            {(!l2.traits || l2.traits.length === 0) && <span className="text-neutral-600 text-[10px] italic">None</span>}
                        </div>
                    </div>
                    {l2.interests && l2.interests.length > 0 && (
                        <div className="space-y-1">
                            <span className="text-[10px] text-neutral-500 uppercase tracking-widest font-bold">Interests</span>
                            <div className="flex flex-wrap gap-1.5">
                                {(l2.interests || []).map((int, i) => (
                                    <span key={i} className={`px-2 py-0.5 rounded text-[10px] bg-neutral-800/50 text-neutral-400 border border-neutral-700/30`}>
                                        {int}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
                {/* Impression Quote */}
                <div className={`${bgColor} p-3 rounded-lg border border-${theme}-500/10 italic text-${theme}-200/80 text-sm flex items-start gap-2`}>
                    <span className="text-xs font-bold opacity-50 not-italic">IMPRESSION:</span>
                    <span>"{l2.impression}"</span>
                </div>
            </div>

            {/* Layer 3: Summary (Map & Deep) */}
            <div className={`p-4 rounded-xl ${panelBg} border ${borderColor} space-y-4`}>
                <div className="flex items-center gap-2 mb-2">
                    <Database className={`w-4 h-4 ${accentColor}`} />
                    <h3 className="text-sm font-bold text-white uppercase tracking-wider">Layer 3: Recent Summary</h3>
                </div>

                {l3List && Array.isArray(l3List) && l3List.length > 0 ? (
                    // NEW: List View for Summaries
                    <div className="space-y-3">
                        {l3List.map((item, i) => (
                            <div key={i} className="bg-neutral-950/30 p-3 rounded border border-neutral-800/50 flex flex-col gap-1">
                                <div className="flex justify-between items-start">
                                    <span className={`text-xs font-bold ${accentColor}`}>{item.title}</span>
                                    <span className="text-[10px] text-neutral-600 font-mono">{item.timestamp}</span>
                                </div>
                                <p className="text-xs text-neutral-400 leading-relaxed pl-2 border-l-2 border-neutral-800">
                                    {item.snippet}
                                </p>
                            </div>
                        ))}
                    </div>
                ) : (
                    // FALLBACK: Legacy Text View
                    <div className="text-neutral-300 text-sm leading-relaxed font-serif">
                        <TypewriterText text={l3Legacy.global_summary} speed={2} delay={100} key={l3Legacy.global_summary} />
                        {(l3Legacy.deep_profile || l3Legacy.future_pred) && (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-3 border-t border-neutral-800 mt-3">
                                {l3Legacy.deep_profile && (
                                    <div className="space-y-1">
                                        <h4 className="text-[10px] font-bold text-purple-400 flex items-center gap-1"><Sparkles className="w-3 h-3" /> DEEP PROFILE</h4>
                                        <p className="text-[11px] text-neutral-400 leading-tight bg-purple-950/20 p-2 rounded border border-purple-500/10">{l3Legacy.deep_profile}</p>
                                    </div>
                                )}
                                {l3Legacy.future_pred && (
                                    <div className="space-y-1">
                                        <h4 className="text-[10px] font-bold text-cyan-400 flex items-center gap-1"><Zap className="w-3 h-3" /> PREDICTION</h4>
                                        <p className="text-[11px] text-neutral-400 leading-tight bg-cyan-950/20 p-2 rounded border border-cyan-500/10">{l3Legacy.future_pred}</p>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Layer 4: Session (Raw Logs) */}
            {profile.last_context && profile.last_context.length > 0 ? (
                <div className={`p-4 rounded-xl ${panelBg} border border-neutral-800/50 space-y-3`}>
                    <div className="flex items-center gap-2">
                        <Server className={`w-4 h-4 ${accentColor}`} />
                        <h3 className="text-sm font-bold text-white uppercase tracking-wider">Layer 4: Current Session</h3>
                    </div>
                    <div className="space-y-2 max-h-56 overflow-y-auto pr-2 custom-scrollbar">
                        {profile.last_context.map((msg, i) => (
                            <div key={i} className="bg-black/40 rounded p-2 border border-neutral-800">
                                <div className="flex justify-between text-[10px] text-neutral-600 mb-1 font-mono">
                                    <span>#{msg.channel}</span>
                                    <span>{new Date(msg.timestamp).toLocaleTimeString()}</span>
                                </div>
                                <p className="text-neutral-400 text-xs leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                            </div>
                        ))}
                    </div>
                </div>
            ) : (
                <div className="p-4 rounded-xl border border-neutral-800/30 text-center text-neutral-600 text-xs">
                    Layer 4: No active session log.
                </div>
            )}
        </div>
    );
}

interface SystemStatus {
    uptime: number;
    cpu: number;
    ram: number;
    gpu: string;
}

// Import NeuralBackground
import NeuralBackground from "../components/NeuralBackground";



const MatrixRain = () => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;

        const letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%^&*()";
        const fontSize = 14;
        const columns = canvas.width / fontSize;
        const drops: number[] = [];
        for (let i = 0; i < columns; i++) drops[i] = 1;

        const draw = () => {
            ctx.fillStyle = "rgba(0, 0, 0, 0.05)";
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.fillStyle = "#0F0";
            ctx.font = `${fontSize}px monospace`;

            for (let i = 0; i < drops.length; i++) {
                const text = letters.charAt(Math.floor(Math.random() * letters.length));
                ctx.fillText(text, i * fontSize, drops[i] * fontSize);
                if (drops[i] * fontSize > canvas.height && Math.random() > 0.975) {
                    drops[i] = 0;
                }
                drops[i]++;
            }
        };
        const interval = setInterval(draw, 33);
        const handleResize = () => {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        };
        window.addEventListener('resize', handleResize);
        return () => {
            clearInterval(interval);
            window.removeEventListener('resize', handleResize);
        };
    }, []);
    return <canvas ref={canvasRef} className="fixed inset-0 z-[9999] pointer-events-none opacity-50 mix-blend-screen" />;
};

export default function DashboardPage() {
    const [users, setUsers] = useState<User[]>([]);
    const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
    const [usage, setUsage] = useState<CostState | null>(null);
    // Dynamic Limits State
    const [limits, setLimits] = useState({
        high: DEFAULT_LIMIT_HIGH,
        stable: DEFAULT_LIMIT_STABLE,
        optimization: LIMIT_OPT_VISUAL
    });

    // Fetch Limits on Mount
    useEffect(() => {
        const fetchLimits = async () => {
            try {
                const res = await fetch("/api/config/limits");
                if (res.ok) {
                    const data = await res.json();
                    setLimits({
                        high: data.high?.limit ?? DEFAULT_LIMIT_HIGH,
                        stable: data.stable?.limit ?? DEFAULT_LIMIT_STABLE,
                        optimization: data.optimization?.limit ?? LIMIT_OPT_VISUAL
                    });
                }
            } catch (e) {
                console.error("Failed to fetch limits", e);
            }
        };
        fetchLimits();
    }, []);

    const [historyData, setHistoryData] = useState<HistoryData | null>(null);
    const [historyLoading, setHistoryLoading] = useState(true);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [refreshing, setRefreshing] = useState(false);
    const [historyLane, setHistoryLane] = useState<string | null>(null);
    const [insightLane, setInsightLane] = useState<Exclude<LaneKey, "burn">>("high");
    const [selectedUser, setSelectedUser] = useState<string | null>(null);
    const [screenshotMode, setScreenshotMode] = useState(false);
    const [groupByServer, setGroupByServer] = useState(true);
    const [showFees, setShowFees] = useState(false); // Toggle visibility of fees
    const [showOffline, setShowOffline] = useState(false);
    const [showBots, setShowBots] = useState(true); // Default Show Bots
    const [autoSortServers, setAutoSortServers] = useState(true); // Auto-sort by activity
    const [manualOrder, setManualOrder] = useState<string[]>([]); // Manual server order
    // Reorderable Grid Items
    const [items, setItems] = useState(["high", "stable", "optimization", "usd", "neural"]);
    const [expandedCard, setExpandedCard] = useState<string | null>(null);
    const [isFrozen, setIsFrozen] = useState(false);

    // EASTER EGG STATES
    const [matrixMode, setMatrixMode] = useState(false);
    const [gravityMode, setGravityMode] = useState(false);
    const [overloadMode, setOverloadMode] = useState(false);
    const [synapseClicks, setSynapseClicks] = useState(0);
    const keyHistoryRef = useRef<string[]>([]);

    // Easter Egg Listeners
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            // Track key history for sequences
            keyHistoryRef.current = [...keyHistoryRef.current, e.key].slice(-20);
            const history = keyHistoryRef.current.join(",");

            // 1. KONAMI CODE (Matrix Mode)
            // Up,Up,Down,Down,Left,Right,Left,Right,b,a
            const konami = "ArrowUp,ArrowUp,ArrowDown,ArrowDown,ArrowLeft,ArrowRight,ArrowLeft,ArrowRight,b,a";
            if (history.includes(konami)) {
                setMatrixMode(prev => !prev);
                keyHistoryRef.current = []; // Reset
            }

            // 2. GRAVITY (Gravity Mode)
            // check for "g,r,a,v,i,t,y" sequence logic simpler:
            if (e.key.length === 1) {
                // Simple string check for typed words might need a different buffer or just check suffix
                const str = keyHistoryRef.current.filter(k => k.length === 1).join("").toLowerCase();
                if (str.endsWith("gravity")) {
                    setGravityMode(prev => !prev);
                    keyHistoryRef.current = [];
                }
                // 3. CHAOS MODE (Shuffle)

            }

            if (e.key === "Escape") {
                if (screenshotMode) setScreenshotMode(false);
                if (matrixMode) setMatrixMode(false);
                // Gravity mode persists until toggled off or reload? Let's allow Esc to clear all.
                if (gravityMode) setGravityMode(false);
                if (overloadMode) setOverloadMode(false);
                setIsSimulating(false); // Disable Simulation
            }
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [screenshotMode, matrixMode, gravityMode, overloadMode]);

    // 4. SIMULATION MODE (Pseudo-Optimization)
    const [isSimulating, setIsSimulating] = useState(false);
    // Map of UserID -> Simulation State
    const [simulatedUsersState, setSimulatedUsersState] = useState<Record<string, { status: "Processing" | "Optimized", timestamp: number }>>({});

    // Continuous Simulation Loop
    useEffect(() => {
        if (!isSimulating) {
            setSimulatedUsersState({});
            return;
        }

        const runCycle = () => {
            const now = Date.now();

            // 1. Cleanup old simulations (keep Optimized for 3s then remove)
            setSimulatedUsersState(prev => {
                const next = { ...prev };
                let changed = false;
                Object.entries(next).forEach(([id, state]) => {
                    // If Processing and time is up -> Switch to Optimized (Handled by timeouts, but safe check here)
                    // Actually timeouts are hard in React state loops. Let's use polling check or individual timeouts.
                    // Simpler: Just spawn new ones. The timeouts will update state.
                });
                return changed ? next : prev;
            });

            // 2. Select Candidates
            // Filter out users already in simulation
            const activeSimIds = Object.keys(simulatedUsersState);
            const candidates = users.filter(u =>
                !activeSimIds.includes(u.discord_user_id) &&
                u.status !== 'Processing' &&
                u.status !== 'Pending' &&
                u.status !== 'Error'
            );

            if (candidates.length === 0) return;

            // 3. Pick Random Count (1-10)
            const batchSize = Math.floor(Math.random() * 10) + 1;
            const selected: string[] = [];

            // Shuffle and pick
            const shuffled = [...candidates].sort(() => 0.5 - Math.random());
            const targets = shuffled.slice(0, batchSize);

            // 4. Add to State
            const newSims: Record<string, { status: "Processing" | "Optimized", timestamp: number }> = {};

            targets.forEach(u => {
                newSims[u.discord_user_id] = { status: "Processing", timestamp: Date.now() };

                // Schedule Optimization Flip (Random 1-10s)
                const duration = Math.floor(Math.random() * 9000) + 1000; // 1s - 10s

                setTimeout(() => {
                    // Update to Optimized
                    setSimulatedUsersState(prev => {
                        if (!prev[u.discord_user_id]) return prev; // Stopped?
                        return {
                            ...prev,
                            [u.discord_user_id]: { status: "Optimized", timestamp: Date.now() }
                        };
                    });

                    // Schedule Cleanup (after 3s of Optimized)
                    setTimeout(() => {
                        setSimulatedUsersState(prev => {
                            const next = { ...prev };
                            delete next[u.discord_user_id];
                            return next;
                        });
                    }, 3000);

                }, duration);
            });

            setSimulatedUsersState(prev => ({ ...prev, ...newSims }));
        };

        runCycle(); // Immediate start
        // Random Interval for waves? Or Fixed? 
        // User said "Max 10 people". 
        // Let's run a wave every 8 seconds to allow overlap but prevent total chaos.
        const interval = setInterval(runCycle, 8000);

        return () => clearInterval(interval);
    }, [isSimulating, users]); // users dependency might cause re-loop, but we need candidates. 
    // Optimization: If users change often, this resets interval. 
    // Better to use ref for users or acceptable for now.

    const toggleSimulation = () => {
        setIsSimulating(prev => !prev);
    };

    // Add Chaos trigger to main listener
    // We will do this by replacing the main listener block.

    // UI States for Refresh Confirmation
    const [refreshConfirmOpen, setRefreshConfirmOpen] = useState(false);

    // Add Simulate Button near Force Refresh or specialized area
    // Let's put a small discrete button in the header or key control area

    const [refreshSuccess, setRefreshSuccess] = useState(false);

    // Track dragging state to prevent click-to-expand during drag
    const isDraggingRef = useRef(false);

    // Derived State for Neural Activity
    // "Pending" or "New" implies active processing or queue
    const processingUsers = users.filter(u => u.status === 'Pending' || u.status === 'New').length;
    const isThinking = processingUsers > 0;
    const resetLabel = usage?.last_reset ? new Date(usage.last_reset).toLocaleString("ja-JP") : "—";
    const insightMeta = LANE_META[insightLane];
    const weeklySeries = useMemo(() => buildWeeklySeries(historyData, insightLane), [historyData, insightLane]);
    const hourlySeries = useMemo(() => buildHourlySeries(historyData, insightLane), [historyData, insightLane]);
    const weeklyMax = Math.max(1, ...weeklySeries.map((point) => point.value));
    const hourlyMax = Math.max(1, ...hourlySeries.map((point) => point.value));



    // Track last data strings to prevent redundant re-renders
    const lastUsersStrRef = useRef<string>("");
    const lastUsageStrRef = useRef<string>("");
    const lastHistoryStrRef = useRef<string>("");

    const fetchData = async (isSilent = false) => {
        const apiBase = "";
        if (!isSilent) setRefreshing(true);
        try {
            const ts = new Date().getTime();
            const [usageRes, usersRes] = await Promise.all([
                fetch(`${apiBase}/api/dashboard/usage?t=${ts}`, { cache: "no-store" }),
                fetch(`${apiBase}/api/dashboard/users?t=${ts}`, { cache: "no-store" })
            ]);

            if (usageRes.ok) {
                const data = await usageRes.json();
                const newUsageStr = JSON.stringify(data.data);
                if (newUsageStr !== lastUsageStrRef.current) {
                    lastUsageStrRef.current = newUsageStr;
                    setUsage(data.data);
                }
            }

            if (usersRes.ok) {
                const data = await usersRes.json();
                // Safety check: ensure data.data is an array
                if (Array.isArray(data.data)) {
                    // Deep Compare to prevent re-render if data hasn't changed
                    const newDataStr = JSON.stringify(data.data);
                    if (newDataStr !== lastUsersStrRef.current) {
                        lastUsersStrRef.current = newDataStr;
                        setUsers(data.data);
                    }
                } else {
                    console.error("Dashboard: Users data is not an array:", data);
                    setUsers([]);
                }
            }
        } catch (error) {
            console.error("Failed to fetch dashboard data", error);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useEffect(() => {
        fetchData(); // Initial load (not silent, shows shimmer?)
        // Poll every 6 seconds for "live" feeling (Reduced from 3s to save CPU)
        const interval = setInterval(() => fetchData(true), 6000);
        return () => {
            clearInterval(interval);
        };
    }, []);

    const fetchHistory = async () => {
        try {
            const apiBase = "";
            const ts = new Date().getTime();
            const res = await fetch(`${apiBase}/api/dashboard/history?t=${ts}`, { cache: "no-store" });
            if (res.ok) {
                const data = await res.json();
                const nextStr = JSON.stringify(data.data);
                if (nextStr !== lastHistoryStrRef.current) {
                    lastHistoryStrRef.current = nextStr;
                    setHistoryData(data.data);
                }
            }
        } catch (err) {
            console.error("Failed to fetch history data", err);
        } finally {
            setHistoryLoading(false);
        }
    };

    useEffect(() => {
        fetchHistory();
        const interval = setInterval(fetchHistory, 60000);
        return () => {
            clearInterval(interval);
        };
    }, []);

    // Toggle Screenshot Mode (Video/Privacy Mode)
    // Persist until Escape key is pressed
    const toggleScreenshotMode = () => {
        setScreenshotMode(true);
    };

    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape" && screenshotMode) {
                setScreenshotMode(false);
            }
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [screenshotMode]);

    // Sort Users: Processing > Pending (Recency) > Optimized (Usage)
    // Sort Users: Processing: Error > Processing > Pending > Optimized (Usage)
    const sortedUsers = useMemo(() => {
        // 1. Filter
        const filtered = (users || []).filter(u => {
            // 0. SIMULATION STATUS OVERRIDE
            if (simulatedUsersState[u.discord_user_id]) {
                return true;
            }

            // 1. Critical Override: Always show if Processing/Pending/Error (Attention Needed)
            if (u.status === "Processing" || u.status === "Pending" || u.status === "Error" || u.impression === "Processing...") return true;

            // 0. Bot Filter (Now checked AFTER override)
            if (!showBots && u.is_bot) return false;

            // 2. Button Toggle (Show Offline)
            if (showOffline) return true;

            // 3. Status Filter (Online/Idle/DnD Only if showOffline is false)
            const ds = u.discord_status || 'offline';
            return ['online', 'idle', 'dnd'].includes(ds);
        });

        const mapped = filtered.map(u => {
            const simState = simulatedUsersState[u.discord_user_id];
            if (simState) {
                return {
                    ...u,
                    status: simState.status,
                    impression: simState.status === "Processing" ? "Processing..." : u.impression
                };
            }
            return u;
        });

        // 3. Sort
        return mapped.sort((a, b) => {
            // 1. Active Processing ("Processing..." impression or status) FIRST
            // Priority: Error > Processing > Pending
            const isErrorA = a.status === "Error";
            const isErrorB = b.status === "Error";
            if (isErrorA && !isErrorB) return -1;
            if (!isErrorA && isErrorB) return 1;

            const aProc = a.impression === "Processing..." || a.status === "Processing" || a.status === "Pending";
            const bProc = b.impression === "Processing..." || b.status === "Processing" || b.status === "Pending";
            if (aProc && !bProc) return -1;
            if (!aProc && bProc) return 1;

            // 2. Status Priority within processing
            // User Correction: Processing (Working) > Pending (Waiting) > Error > Normal (Optimized/New)
            const statusOrder: Record<string, number> = { "Processing": -2, "Pending": -1, "Error": 0, "New": 1, "Optimized": 1 };

            const orderA = statusOrder[a.status] ?? 1;
            const orderB = statusOrder[b.status] ?? 1;
            if (orderA !== orderB) return orderA - orderB;

            // 3. Online Status (Online > Idle > DnD > Offline)
            const discordOrder: Record<string, number> = { "online": 0, "idle": 1, "dnd": 2, "offline": 3 };
            const dA = discordOrder[a.discord_status || "offline"] ?? 3;
            const dB = discordOrder[b.discord_status || "offline"] ?? 3;
            if (dA !== dB) return dA - dB;

            // 4. Primary Sort: Recency (last_updated/created_at) Descending
            const tA = a.last_updated ? new Date(a.last_updated).getTime() : (a.created_at ? new Date(a.created_at).getTime() : 0);
            const tB = b.last_updated ? new Date(b.last_updated).getTime() : (b.created_at ? new Date(b.created_at).getTime() : 0);
            if (tA !== tB) return tB - tA;

            // 5. Secondary Sort: High Usage (Desc) as fallback
            const usageA = a.cost_usage?.high || 0;
            const usageB = b.cost_usage?.high || 0;
            return usageB - usageA;
        });
    }, [users, showOffline, showBots, simulatedUsersState]);

    // Memoize the grouped/sorted lists used in rendering to avoid heavy calculation on every render frame
    const sortedAllUsers = useMemo(() => {
        return [...sortedUsers].sort((a, b) => {
            // 1. Active Processing / Error FIRST
            const isErrorA = a.status === "Error";
            const isErrorB = b.status === "Error";
            if (isErrorA && !isErrorB) return -1;
            if (!isErrorA && isErrorB) return 1;

            const aProc = a.impression === "Processing..." || a.status === "Processing";
            const bProc = b.impression === "Processing..." || b.status === "Processing";
            if (aProc && !bProc) return -1;
            if (!aProc && bProc) return 1;

            // 2. Status Priority: Processing > Pending > Error > Normal
            const statusOrder: Record<string, number> = { "Processing": -2, "Pending": -1, "Error": 0, "New": 1, "Optimized": 1 };
            const orderA = statusOrder[a.status] ?? 1;
            const orderB = statusOrder[b.status] ?? 1;
            if (orderA !== orderB) return orderA - orderB;

            // 3. Recency
            if (a.created_at && b.created_at) {
                return b.created_at.localeCompare(a.created_at);
            }

            // 4. Usage
            return (b.cost_usage?.high || 0) - (a.cost_usage?.high || 0);
        });
    }, [sortedUsers]);

    const sortedGroupedUsers = useMemo(() => {
        const grouped = sortedUsers.reduce((acc, user) => {
            const key = user.guild_name || "Unknown Server";
            if (!acc[key]) acc[key] = [];
            acc[key].push(user);
            return acc;
        }, {} as Record<string, User[]>);

        return Object.entries(grouped)
            .sort((a, b) => {
                // AUTO SORT: Prioritize Activity
                // AUTO SORT: Prioritize Processing Count -> Then Freshness (User Request)
                if (autoSortServers) {
                    // 1. Processing/Error users COUNT (Active Servers on Top)
                    const getCriticalCount = (us: User[]) => us.filter(u => u.status === "Error" || u.status === "Processing" || u.impression === "Processing...").length;
                    const aProcCount = getCriticalCount(a[1]);
                    const bProcCount = getCriticalCount(b[1]);
                    if (aProcCount !== bProcCount) return bProcCount - aProcCount;

                    // 2. Freshness (Last Optimized/Active)
                    // Sort by the most recent timestamp in the group
                    const getFreshness = (us: User[]) => Math.max(0, ...us.map(u => {
                        const t1 = u.last_message ? new Date(u.last_message).getTime() : 0;
                        const t2 = u.created_at ? new Date(u.created_at).getTime() : 0;
                        const t3 = u.last_updated ? new Date(u.last_updated).getTime() : 0; // Optimization Time
                        return Math.max(t1, t2, t3);
                    }));
                    const aFresh = getFreshness(a[1]);
                    const bFresh = getFreshness(b[1]);
                    if (aFresh !== bFresh) return bFresh - aFresh;

                    // 3. Pending count
                    const aPending = a[1].filter(u => u.status === "Pending").length;
                    const bPending = b[1].filter(u => u.status === "Pending").length;
                    if (bPending !== aPending) return bPending - aPending;

                    // 4. Total count
                    return b[1].length - a[1].length;
                }
                // MANUAL SORT: Use Manual Order
                else {
                    const idxA = manualOrder.indexOf(a[0]);
                    const idxB = manualOrder.indexOf(b[0]);
                    const validA = idxA !== -1;
                    const validB = idxB !== -1;

                    if (validA && validB) return idxA - idxB;
                    if (validA) return -1; // A is in known order, B is new (put B at end)
                    if (validB) return 1;
                    // Fallback: Alphabetical for unsorted
                    return a[0].localeCompare(b[0]);
                }
            })
            .map(([serverName, users]) => {
                // Determine order for users inside the group (Already mostly sorted by sortedUsers, but double check)
                const sortedGroup = [...users].map(u => {
                    // APPLY SIMULATION OVERRIDE
                    const simState = simulatedUsersState[u.discord_user_id];
                    if (simState) {
                        return {
                            ...u,
                            status: simState.status,
                            impression: simState.status === "Processing" ? "Processing..." : u.impression
                        };
                    }
                    return u;
                });
                return { serverName, users: sortedGroup };
            });
    }, [sortedUsers, autoSortServers, manualOrder, simulatedUsersState]);

    const deferredAllUsers = useDeferredValue(sortedAllUsers);
    const deferredGroupedUsers = useDeferredValue(sortedGroupedUsers);
    const visibleAllUsers = selectedUser ? sortedAllUsers : deferredAllUsers;
    const visibleGroupedUsers = selectedUser ? sortedGroupedUsers : deferredGroupedUsers;

    // Privacy Masking
    const maskName = (name: string | null) => screenshotMode ? "User-Protected" : (name || "Unknown");
    const maskID = (id: string) => screenshotMode ? "****-****-****" : id;
    const maskAvatar = (name: string | null) => screenshotMode ? "?" : (name ? name.charAt(0).toUpperCase() : "?");

    // Animation Variants
    const containerVariants = {
        hidden: { opacity: 0 },
        visible: {
            opacity: 1,
            transition: {
                staggerChildren: STAGGER_STANDARD,
                delayChildren: 0.1
            }
        }
    };

    const itemVariants = {
        hidden: { y: 15, opacity: 0 },
        visible: {
            y: 0,
            opacity: 1,
            transition: SPRING_FLUID
        },
        exit: { y: -15, opacity: 0, transition: { duration: 0.15 } }
    };

    const topContainerVariants = {
        hidden: { opacity: 0 },
        visible: {
            opacity: 1,
            transition: {
                staggerChildren: STAGGER_SLOW, // Individual feel
                delayChildren: 0.2
            }
        }
    };

    const userContainerVariants = {
        hidden: { opacity: 0 },
        visible: {
            opacity: 1,
            transition: {
                delayChildren: 0.1
            }
        }
    };

    const topCardVariants = {
        hidden: { y: 20, opacity: 0, scale: 0.95, filter: "blur(10px)" },
        visible: (i: number) => ({
            y: 0,
            opacity: 1,
            scale: 1,
            filter: "blur(0px)",
            transition: {
                ...SPRING_FLUID,
                delay: i * STAGGER_SLOW
            }
        })
    };

    const userCardVariants = {
        hidden: { y: 20, opacity: 0, scale: 0.95, filter: "blur(8px)" },
        visible: (i: number) => ({
            y: 0,
            opacity: 1,
            scale: 1,
            filter: "blur(0px)",
            transition: {
                ...SPRING_FLUID,
                delay: i * STAGGER_FAST
            }
        }),
        exit: { scale: 0.95, opacity: 0, filter: "blur(5px)", transition: { duration: 0.15 } }
    };

    const totalLifetimeTokens =
        (usage?.lifetime_tokens?.high || 0) +
        (usage?.lifetime_tokens?.stable || 0) +
        (usage?.lifetime_tokens?.optimization || 0) +
        (usage?.lifetime_tokens?.burn || 0);

    const renderExpandedUsage = (limit?: number) => {
        const isUsd = insightLane === "usd";
        let todayValue = "";
        let lifetimeValue = "";
        let tokenUsage = 0;

        if (isUsd) {
            todayValue = `$${(usage?.total_usd || 0).toFixed(4)}`;
            lifetimeValue = totalLifetimeTokens.toLocaleString();
        } else {
            tokenUsage = usage?.daily_tokens?.[insightLane] || 0;
            todayValue = tokenUsage.toLocaleString();
            lifetimeValue = (usage?.lifetime_tokens?.[insightLane] || 0).toLocaleString();
        }

        return (
            <motion.div
                layout
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.2 }}
                className="mt-4 rounded-xl border border-white/10 bg-black/40 p-4 space-y-4 text-xs overflow-hidden"
            >
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <span className={`px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest rounded-full border ${insightMeta.chip}`}>
                            {insightMeta.label}
                        </span>
                        <span className="text-[10px] text-neutral-500 font-mono">詳細</span>
                    </div>
                    <button
                        onClick={(e) => { e.stopPropagation(); setHistoryLane(insightLane); }}
                        className="px-3 py-1 text-[10px] font-bold uppercase tracking-widest rounded-full border border-neutral-700/60 bg-black/40 text-neutral-200 hover:bg-neutral-800/50 transition-colors"
                    >
                        履歴を見る
                    </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div className="bg-neutral-900/60 border border-neutral-800/70 rounded-xl p-3">
                        <div className="text-[10px] text-neutral-500 uppercase tracking-widest">
                            {isUsd ? "総コスト" : "今日の使用量"}
                        </div>
                        <div className={`mt-2 text-2xl font-mono font-semibold ${insightMeta.text}`}>
                            {todayValue}
                        </div>
                    </div>
                    <div className="bg-neutral-900/60 border border-neutral-800/70 rounded-xl p-3">
                        <div className="text-[10px] text-neutral-500 uppercase tracking-widest">累計トークン</div>
                        <div className="mt-2 text-2xl font-mono font-semibold text-neutral-200">
                            {lifetimeValue}
                        </div>
                    </div>
                    <div className="bg-neutral-900/60 border border-neutral-800/70 rounded-xl p-3">
                        <div className="text-[10px] text-neutral-500 uppercase tracking-widest">リセット</div>
                        <div className="mt-2 text-sm font-mono text-neutral-300">{resetLabel}</div>
                        {!isUsd && limit && (
                            <div className="mt-3 h-2 rounded-full bg-neutral-800 overflow-hidden">
                                <motion.div
                                    initial={{ width: 0 }}
                                    animate={{
                                        width: `${Math.min((tokenUsage / limit) * 100, 100)}%`
                                    }}
                                    transition={{ type: "spring", stiffness: 180, damping: 24 }}
                                    className={`h-full ${insightMeta.bar}`}
                                />
                            </div>
                        )}
                    </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <div className="bg-neutral-900/50 border border-neutral-800/60 rounded-xl p-4">
                        <div className="flex items-center justify-between mb-3">
                            <span className="text-[10px] font-bold uppercase tracking-widest text-neutral-500">This Week</span>
                            <span className={`text-[10px] font-bold uppercase tracking-widest ${insightMeta.text}`}>{insightMeta.label}</span>
                        </div>
                        {historyLoading ? (
                            <div className="flex items-center justify-center h-24 text-neutral-500">
                                <Loader2 className="w-4 h-4 animate-spin mr-2" />
                                <span className="text-[10px] font-mono">Loading...</span>
                            </div>
                        ) : weeklySeries.length > 0 ? (
                            <div className="h-24 flex items-end gap-2">
                                {weeklySeries.map((point) => {
                                    const height = weeklyMax > 0 ? (point.value / weeklyMax) * 100 : 0;
                                    const valueLabel = isUsd ? `$${point.value.toFixed(2)}` : point.value.toLocaleString();
                                    return (
                                        <div key={point.key} className="flex-1 flex flex-col items-center gap-2">
                                            <motion.div
                                                initial={{ height: 0 }}
                                                animate={{ height: `${Math.max(height, 4)}%` }}
                                                transition={{ type: "spring", stiffness: 260, damping: 26 }}
                                                className={`w-full rounded-md ${insightMeta.bar} opacity-80 hover:opacity-100`}
                                                title={`${point.label} ${valueLabel}`}
                                            />
                                            <span className="text-[9px] text-neutral-500 font-mono">{point.label}</span>
                                        </div>
                                    );
                                })}
                            </div>
                        ) : (
                            <div className="flex items-center justify-center h-24 text-neutral-500 text-[10px] font-mono">
                                週次データがまだありません
                            </div>
                        )}
                    </div>

                    <div className="bg-neutral-900/50 border border-neutral-800/60 rounded-xl p-4">
                        <div className="flex items-center justify-between mb-3">
                            <span className="text-[10px] font-bold uppercase tracking-widest text-neutral-500">Hourly Activity</span>
                            <span className={`text-[10px] font-bold uppercase tracking-widest ${insightMeta.text}`}>24h</span>
                        </div>
                        {historyLoading ? (
                            <div className="flex items-center justify-center h-24 text-neutral-500">
                                <Loader2 className="w-4 h-4 animate-spin mr-2" />
                                <span className="text-[10px] font-mono">Loading...</span>
                            </div>
                        ) : hourlySeries.length > 0 ? (
                            <div className="h-24 flex items-end gap-[3px]">
                                {hourlySeries.map((point) => {
                                    const height = hourlyMax > 0 ? (point.value / hourlyMax) * 100 : 0;
                                    const valueLabel = isUsd ? `$${point.value.toFixed(2)}` : point.value.toLocaleString();
                                    return (
                                        <motion.div
                                            key={point.key}
                                            initial={{ height: 0 }}
                                            animate={{ height: `${Math.max(height, 2)}%` }}
                                            transition={{ type: "spring", stiffness: 240, damping: 24 }}
                                            className={`w-full rounded-t-sm ${insightMeta.bar} opacity-50 hover:opacity-90`}
                                            title={`${point.label} ${valueLabel}`}
                                        />
                                    );
                                })}
                            </div>
                        ) : (
                            <div className="flex items-center justify-center h-24 text-neutral-500 text-[10px] font-mono">
                                時間別データがまだありません
                            </div>
                        )}
                        <div className="flex justify-between mt-2 text-[9px] text-neutral-600 font-mono">
                            <span>00:00</span>
                            <span>12:00</span>
                            <span>23:00</span>
                        </div>
                    </div>
                </div>
            </motion.div>
        );
    };

    const renderCard = (id: string) => {
        switch (id) {
            case "high":
                return (
                    <motion.div
                        key="high"
                        custom={0}
                        variants={topCardVariants}
                        layout
                        onClick={() => {
                            if (!isDraggingRef.current) {
                                const next = expandedCard === "high" ? null : "high";
                                setExpandedCard(next);
                                if (next) setInsightLane("high");
                            }
                        }}
                        onMouseMove={(e) => updateSpotlightPosition(e.currentTarget, e.clientX, e.clientY)}
                        onMouseEnter={(e) => activateSpotlight(e.currentTarget, e.clientX, e.clientY)}
                        onMouseLeave={(e) => deactivateSpotlight(e.currentTarget)}
                        style={{
                            willChange: "transform, opacity, filter",
                            translateZ: 0,
                            "--spotlight-color": "6, 182, 212"
                        } as React.CSSProperties}
                        className={`mercury-glass rounded-2xl p-4 relative overflow-hidden flex flex-col justify-between group cursor-pointer active:scale-95 h-full ${expandedCard === "high" ? "ring-2 ring-cyan-500/40 shadow-[0_0_30px_rgba(6,182,212,0.25)]" : ""}`}
                    >
                        <div className="pointer-events-none absolute top-0 right-0 p-2 opacity-10 font-black text-8xl text-cyan-500 select-none leading-none z-0">GEN</div>
                        <div className="relative z-10">
                            <div className="flex items-center gap-3 mb-1 text-cyan-400">
                                <Activity className="w-6 h-6" />
                                <h2 className="text-xl font-bold leading-snug">高速推論 (High)</h2>
                            </div>
                            <p className="text-sm text-neutral-200 font-medium leading-tight">リアルタイム応答</p>
                        </div>
                        <div className="space-y-2 relative z-10 mt-3 flex-1 flex flex-col justify-end">
                            <div>
                                <div className="flex justify-between items-baseline text-white">
                                    <span className="text-3xl md:text-5xl font-mono font-medium tracking-tight leading-none">
                                        <AnimatedCounter value={usage?.daily_tokens.high || 0} delay={0.1} />
                                    </span>
                                    <span className="text-sm text-neutral-600 leading-none">/ {limits.high.toLocaleString()}</span>
                                </div>
                                <div className="h-2 bg-neutral-800 rounded-full overflow-hidden mt-2">
                                    <motion.div
                                        className="h-full bg-cyan-500"
                                        initial={{ width: 0 }}
                                        animate={{ width: `${Math.min(((usage?.daily_tokens.high || 0) / limits.high) * 100, 100)}%` }}
                                        transition={{ type: "spring", ...SPRING_SLOW, delay: 0.1 }}
                                    />
                                </div>
                            </div>
                            <AnimatePresence initial={false} mode="popLayout">
                                {expandedCard === "high" && renderExpandedUsage(limits.high)}
                            </AnimatePresence>
                        </div>
                    </motion.div>
                );
            case "stable":
                return (
                    <motion.div
                        key="stable"
                        custom={1}
                        variants={topCardVariants}
                        layout
                        onClick={() => {
                            if (!isDraggingRef.current) {
                                const next = expandedCard === "stable" ? null : "stable";
                                setExpandedCard(next);
                                if (next) setInsightLane("stable");
                            }
                        }}
                        onMouseMove={(e) => updateSpotlightPosition(e.currentTarget, e.clientX, e.clientY)}
                        onMouseEnter={(e) => activateSpotlight(e.currentTarget, e.clientX, e.clientY)}
                        onMouseLeave={(e) => deactivateSpotlight(e.currentTarget)}
                        style={{
                            translateZ: 0,
                            "--spotlight-color": "34, 197, 94"
                        } as React.CSSProperties}
                        className={`mercury-glass rounded-2xl p-4 relative overflow-hidden flex flex-col justify-between group cursor-pointer active:scale-95 h-full ${expandedCard === "stable" ? "ring-2 ring-green-500/40 shadow-[0_0_30px_rgba(34,197,94,0.25)]" : ""}`}
                    >

                        <div className="pointer-events-none absolute top-0 right-0 p-2 opacity-10 font-black text-8xl text-green-500 select-none leading-none z-0">CHAT</div>
                        <div className="relative z-10">
                            <div className="flex items-center gap-3 mb-1 text-green-400">
                                <Zap className="w-6 h-6" />
                                <h2 className="text-xl font-bold leading-snug">会話モデル (Stable)</h2>
                            </div>
                            <p className="text-sm text-neutral-200 font-medium leading-tight">標準的な会話・応答</p>
                        </div>
                        <div className="space-y-2 relative z-10 mt-3">
                            <div className="flex justify-between items-baseline text-white">
                                <span className="text-3xl md:text-5xl font-mono font-medium tracking-tight leading-none">
                                    <AnimatedCounter value={usage?.daily_tokens.stable || 0} delay={0.2} />
                                </span>
                                {/* Shared Budget Calculation: Stable Limit = Total - Opt Usage */}
                                <span className="text-sm text-neutral-600 leading-none">/ {(limits.stable - (usage?.daily_tokens.optimization || 0)).toLocaleString()}</span>
                            </div>
                            <div className="h-2 bg-neutral-800 rounded-full overflow-hidden">
                                <motion.div
                                    className="h-full bg-green-500"
                                    initial={{ width: 0 }}
                                    animate={{ width: `${Math.min(((usage?.daily_tokens.stable || 0) / (limits.stable - (usage?.daily_tokens.optimization || 0))) * 100, 100)}%` }}
                                    transition={{ type: "spring", ...SPRING_SLOW, delay: 0.2 }}
                                />
                            </div>
                        </div>
                        <AnimatePresence initial={false} mode="popLayout">
                            {expandedCard === "stable" && renderExpandedUsage(limits.stable)}
                        </AnimatePresence>
                    </motion.div>
                );
            case "optimization":
                return (
                    <motion.div
                        key="optimization"
                        custom={2}
                        variants={topCardVariants}
                        layout
                        onClick={() => {
                            if (!isDraggingRef.current) {
                                const next = expandedCard === "optimization" ? null : "optimization";
                                setExpandedCard(next);
                                if (next) setInsightLane("optimization");
                            }
                        }}
                        onMouseMove={(e) => updateSpotlightPosition(e.currentTarget, e.clientX, e.clientY)}
                        onMouseEnter={(e) => activateSpotlight(e.currentTarget, e.clientX, e.clientY)}
                        onMouseLeave={(e) => deactivateSpotlight(e.currentTarget)}
                        style={{
                            translateZ: 0,
                            "--spotlight-color": "168, 85, 247"
                        } as React.CSSProperties}
                        className={`mercury-glass rounded-2xl p-4 relative overflow-hidden flex flex-col justify-between group cursor-pointer active:scale-95 h-full ${expandedCard === "optimization" ? "ring-2 ring-purple-500/40 shadow-[0_0_30px_rgba(168,85,247,0.25)]" : ""}`}
                    >

                        <div className="pointer-events-none absolute top-0 right-0 p-2 opacity-10 font-black text-8xl text-purple-500 select-none leading-none z-0">MEM</div>
                        <div className="relative z-10">
                            <div className="flex items-center gap-3 mb-1 text-purple-400">
                                <Database className="w-6 h-6" />
                                <h2 className="text-xl font-bold leading-snug">記憶整理 (Opt)</h2>
                            </div>
                            <p className="text-sm text-neutral-200 font-medium leading-tight">バックグラウンド処理</p>
                        </div>
                        <div className="space-y-2 relative z-10 mt-3">
                            <div className="flex justify-between items-baseline text-white">
                                <span className="text-3xl md:text-5xl font-mono font-medium tracking-tight leading-none">
                                    <AnimatedCounter value={usage?.daily_tokens.optimization || 0} delay={0.3} />
                                </span>
                                {/* Shared Budget Calculation: Opt Limit = Total - Stable Usage */}
                                <span className="text-sm text-neutral-600 leading-none">/ {(limits.optimization - (usage?.daily_tokens.stable || 0)).toLocaleString()}</span>
                            </div>
                            <div className="h-2 bg-neutral-800 rounded-full overflow-hidden">
                                <motion.div
                                    className="h-full bg-purple-500"
                                    initial={{ width: 0 }}
                                    animate={{ width: `${Math.min(((usage?.daily_tokens.optimization || 0) / (limits.optimization - (usage?.daily_tokens.stable || 0))) * 100, 100)}%` }}
                                    transition={{ type: "spring", ...SPRING_SLOW, delay: 0.3 }}
                                />
                            </div>
                        </div>
                        <AnimatePresence initial={false} mode="popLayout">
                            {expandedCard === "optimization" && renderExpandedUsage(limits.optimization)}
                        </AnimatePresence>
                    </motion.div>
                );
            case "usd": {
                const isUsdExpanded = expandedCard === "usd";
                return (
                    <motion.div
                        key="usd"
                        custom={3}
                        variants={topCardVariants}
                        layout
                        onClick={() => {
                            if (!isDraggingRef.current) {
                                const next = expandedCard === "usd" ? null : "usd";
                                setExpandedCard(next);
                                if (next) setInsightLane("usd");
                            }
                        }}
                        onMouseMove={(e) => updateSpotlightPosition(e.currentTarget, e.clientX, e.clientY)}
                        onMouseEnter={(e) => activateSpotlight(e.currentTarget, e.clientX, e.clientY)}
                        onMouseLeave={(e) => deactivateSpotlight(e.currentTarget)}
                        style={{
                            translateZ: 0,
                            "--spotlight-color": "255, 255, 255"
                        } as React.CSSProperties}
                        className={`mercury-glass rounded-2xl p-4 relative overflow-hidden flex flex-col items-center cursor-pointer active:scale-95 h-full ${expandedCard === "usd" ? "ring-2 ring-neutral-300/40 shadow-[0_0_30px_rgba(255,255,255,0.18)]" : ""}`}
                    >

                        <div className="pointer-events-none absolute top-0 right-0 p-2 opacity-10 font-black text-8xl text-neutral-600 select-none leading-none z-0">USD</div>
                        <div className={`flex flex-col items-center justify-center ${isUsdExpanded ? "" : "flex-1"}`}>
                            <h3 className="text-neutral-500 font-mono text-sm uppercase tracking-widest mb-2 leading-none relative z-10">推定コスト合計 (USD)</h3>
                            <div className="text-3xl md:text-6xl font-black text-white font-mono tracking-tighter leading-none my-2 relative z-10">
                                $<AnimatedCounter value={usage?.total_usd || 0} formatter={(v) => v.toFixed(4)} delay={0.4} />
                            </div>
                            <p className="text-sm text-neutral-500 leading-none relative z-10">現在のセッション累積</p>
                        </div>
                        <AnimatePresence initial={false} mode="popLayout">
                            {expandedCard === "usd" && renderExpandedUsage()}
                        </AnimatePresence>
                    </motion.div>
                );
            }
            case "neural":
                return (
                    <motion.div
                        key="neural"
                        custom={4}
                        variants={topCardVariants}
                        layout
                        style={{
                            translateZ: 0,
                            "--spotlight-color": "6, 182, 212"
                        } as React.CSSProperties}
                        className={`mercury-glass rounded-2xl p-0 relative overflow-hidden flex flex-col justify-center items-center h-full group col-span-1 md:col-span-1 cursor-pointer active:scale-95 transition-transform ${overloadMode ? "animate-shake" : ""}`}
                        onClick={() => {
                            if (!isDraggingRef.current) {
                                if (expandedCard === "neural") {
                                    setExpandedCard(null);
                                } else {
                                    setExpandedCard("neural");
                                }
                                // EASTER EGG: Overload
                                const newClicks = synapseClicks + 1;
                                setSynapseClicks(newClicks);
                                if (newClicks > 10) {
                                    setOverloadMode(true);
                                }
                            }
                        }}
                        onMouseMove={(e) => updateSpotlightPosition(e.currentTarget, e.clientX, e.clientY)}
                        onMouseEnter={(e) => activateSpotlight(e.currentTarget, e.clientX, e.clientY)}
                        onMouseLeave={(e) => deactivateSpotlight(e.currentTarget)}
                    >
                        <div className="absolute inset-0">
                            <NeuralBackground intensity={overloadMode ? 5.0 : (isThinking ? 1.0 : 0)} frozen={isFrozen} className="opacity-80" />
                        </div>
                        {/* Freeze Toggle (Visible on Hover or Expanded) */}
                        <div className="absolute top-2 right-2 z-20 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button
                                onClick={(e) => { e.stopPropagation(); setIsFrozen(!isFrozen); }}
                                className="p-1.5 rounded-full bg-black/40 hover:bg-black/80 text-white/50 hover:text-white backdrop-blur-sm border border-white/5 transition-all"
                                title={isFrozen ? "Resume Animation" : "Freeze Animation"}
                            >
                                {isFrozen ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
                            </button>
                        </div>
                        <div className="absolute bottom-4 left-4 z-10">
                            <h2 className="text-xl font-bold leading-snug text-white flex items-center gap-2">
                                <Cpu className={`w-5 h-5 ${isThinking ? "text-cyan-400 animate-pulse" : "text-neutral-500"}`} />
                                Neural Synapse
                            </h2>
                            <p className="text-xs text-neutral-400 font-mono mt-1">
                                {isThinking ? "ACTIVE PROCESSING" : "IDLE STATE"}
                                {expandedCard === "neural" ? <><br /><span className="text-[10px] text-cyan-300">SYNAPSE EXPANDED</span></> : null}
                            </p>
                        </div>
                        <AnimatePresence initial={false}>
                            {expandedCard === "neural" && (
                                <motion.div
                                    initial={{ opacity: 0, y: 8 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    exit={{ opacity: 0, y: 8 }}
                                    transition={{ duration: 0.2 }}
                                    className="absolute bottom-4 right-4 z-10 w-52 rounded-xl border border-cyan-500/20 bg-black/40 p-3 text-[11px] space-y-2"
                                >
                                    <div className="flex items-center justify-between text-neutral-300">
                                        <span>処理中ユーザー</span>
                                        <span className="font-mono text-cyan-200">{processingUsers}</span>
                                    </div>
                                    <div className="flex items-center justify-between text-neutral-300">
                                        <span>シナプスクリック</span>
                                        <span className="font-mono text-cyan-200">{synapseClicks}/10</span>
                                    </div>
                                    <div className="flex items-center justify-between text-neutral-400">
                                        <span>Overload</span>
                                        <span className={`font-mono ${overloadMode ? "text-amber-300" : "text-neutral-500"}`}>
                                            {overloadMode ? "ON" : "OFF"}
                                        </span>
                                    </div>
                                    <div className="flex items-center justify-between text-neutral-400">
                                        <span>Animation</span>
                                        <span className={`font-mono ${isFrozen ? "text-neutral-400" : "text-cyan-200"}`}>
                                            {isFrozen ? "FROZEN" : "LIVE"}
                                        </span>
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </motion.div>
                );
            default:
                return null;
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-neutral-950 flex items-center justify-center text-neutral-500 font-mono">
                <Loader2 className="w-8 h-8 animate-spin mr-3" />
                <span className="text-xl tracking-widest">ORA SYSTEM INITIALIZING...</span>
            </div>
        );
    }

    const isRedAlert = usage?.unlimited_mode || (usage?.unlimited_users && usage.unlimited_users.length > 0);

    return (
        <div className={`relative min-h-screen bg-neutral-950 text-neutral-200 font-sans w-full p-2 md:p-4 overflow-x-hidden ${screenshotMode ? 'cursor-none select-none' : ''}`}>
            {matrixMode && <MatrixRain />}
            {/* Beautiful Reload Shimmer & NERV Alert */}
            <AnimatePresence>
                {isRedAlert && (
                    <motion.div
                        initial={{ opacity: 0, y: -20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -20 }}
                        className="fixed top-0 left-0 right-0 z-[100] h-12 nerv-alert flex items-center justify-between px-4 md:px-8 backdrop-blur-md"
                    >
                        {/* Hex Grid Background */}
                        <div className="nerv-hex-grid"></div>

                        {/* Left Warning */}
                        <div className="flex items-center gap-4 relative z-10">
                            <div className="bg-red-600 text-black font-black text-xs md:text-sm px-2 py-1 nerv-blink border border-black">
                                EMERGENCY
                            </div>
                            <span className="text-red-600 font-bold text-lg md:text-2xl nerv-title tracking-[0.2em]">
                                SYSTEM OVERRIDE
                            </span>
                        </div>

                        {/* Center Scroll Text (Desktop) */}
                        <div className="hidden md:block relative z-10">
                            <span className="text-red-600/80 font-mono text-xs tracking-widest animate-pulse">
                                PATTERN RED // UNIDENTIFIED ACCESS DETECTED // SAFETY PROTOCOLS DISABLED
                            </span>
                        </div>

                        {/* Right Status */}
                        <div className="flex items-center gap-3 relative z-10">
                            <span className="text-red-500 font-serif font-bold text-xs md:text-sm">
                                {usage?.unlimited_mode ? "GLOBAL: INFINITE" : `USER BYPASS: ${usage?.unlimited_users?.length}`}
                            </span>
                            <AlertTriangle className="w-5 h-5 text-red-600 nerv-blink" />
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Global Warning Background Overlay */}
            <AnimatePresence>
                {isRedAlert && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 1 }}
                        className="fixed inset-0 z-[1] pointer-events-none"
                    >
                        {/* Red Tint & Vignette */}
                        <div className="absolute inset-0 bg-red-950/20 mix-blend-overlay"></div>
                        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_0%,rgba(50,0,0,0.4)_100%)]"></div>

                        {/* Hex Grid (Large, Faint but visible) */}
                        <div className="absolute inset-0 nerv-hex-grid opacity-[0.15] scale-150"></div>

                        {/* Scanlines */}
                        <div className="absolute inset-0 bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(255,0,0,0.06),rgba(255,0,0,0.02),rgba(255,0,0,0.06))] bg-[length:100%_4px,6px_100%] pointer-events-none"></div>
                    </motion.div>
                )}
            </AnimatePresence>



            {/* Refreshing Shimmer */}
            <AnimatePresence>
                {refreshing && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 pointer-events-none z-50 overflow-hidden"
                    >
                        <motion.div
                            animate={{ x: ["-100%", "100%"] }}
                            transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
                            className="absolute inset-0 bg-gradient-to-r from-transparent via-cyan-500/5 to-transparent w-full h-full"
                        />
                    </motion.div>
                )}
            </AnimatePresence>

            <LayoutGroup id="user-cards">
                <motion.div
                    className="w-full max-w-[2560px] mx-auto space-y-3 md:space-y-4 relative z-10"
                    variants={containerVariants}
                    initial="hidden"
                    animate="visible"
                >




                    {/* Header: Scaled & Tight */}
                    <motion.div variants={itemVariants} className="flex flex-col md:flex-row justify-between items-start md:items-end border-b border-neutral-800 pb-4 mb-2 gap-4">
                        <div>
                            <h1 className="text-3xl md:text-5xl font-black text-white tracking-tight mb-1 flex items-center gap-3 md:gap-6">
                                <span>ORA <span className="text-cyan-500">SYSTEM</span></span>
                                <span className="text-xs md:text-lg font-bold text-neutral-950 bg-neutral-200 px-2 md:px-3 py-0.5 md:py-1 rounded border border-neutral-800 whitespace-nowrap self-center mt-1 md:mt-2">
                                    {screenshotMode ? "PRIVACY SAFE" : "v3.9 FINAL"}
                                </span>
                            </h1>
                            <p className="text-neutral-200 font-medium font-mono text-xs md:text-sm flex items-center gap-2">
                                <Activity className="w-4 h-4 md:w-5 md:h-5" />
                                コスト追跡 & 自律最適化ダッシュボード
                            </p>
                        </div>
                        <div className="text-left md:text-right w-full md:w-auto flex flex-col items-end gap-2">
                            <button
                                onClick={toggleSimulation}
                                className={`px-2 py-0.5 border rounded text-[10px] font-mono transition-colors ${isSimulating
                                    ? "bg-cyan-900/40 border-cyan-500/50 text-cyan-400 animate-pulse"
                                    : "bg-neutral-900 border-neutral-800 text-neutral-600 hover:text-cyan-400 hover:border-cyan-900/50"
                                    }`}
                            >
                                {isSimulating ? "STOP SIMULATION (ESC)" : "DEMO: SIMULATE LOOP"}
                            </button>
                            <div className="text-[10px] md:text-xs text-neutral-600 font-mono mb-1 uppercase tracking-widest">Current System Time</div>
                            <SystemClock />
                        </div>
                    </motion.div>

                    {/* Global Usage Cards: Large Text / Tight Padding */}
                    {/* Reorderable Usage Cards */}
                    <Reorder.Group
                        axis="x"
                        onReorder={setItems}
                        values={items}
                        className={`grid gap-4 transition-all duration-300 grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 auto-rows-[minmax(200px,auto)]`}
                        as="div"
                        variants={topContainerVariants}
                    >
                        {/* Toggle Grouping at Top Right of Grid? No, place above user list. */}
                        {items.map((item) => {
                            const isExpanded = expandedCard === item;
                            return (
                                <Reorder.Item
                                    key={item}
                                    value={item}
                                    as="div"
                                    layout
                                    onDragStart={() => { isDraggingRef.current = true; }}
                                    onDragEnd={() => { setTimeout(() => { isDraggingRef.current = false; }, 100); }}
                                    // Remove CSS transition-all to prevent conflict with Framer Motion layout animation
                                    className={`${isExpanded ? "md:col-span-2 md:row-span-2 z-10" : "md:col-span-1 md:row-span-1 z-0"}`}
                                    transition={{
                                        layout: { type: "spring", stiffness: 300, damping: 30 }, // Snappy swap
                                        default: { duration: 0.2 }
                                    }}
                                    style={{ height: isExpanded ? "50vh" : "auto" }}
                                    animate={gravityMode ? {
                                        y: [0, -20 - (item.length % 5) * 2, 0, 15, 0],
                                        rotate: [0, 1 + (item.length % 2), -1, 0],
                                        transition: {
                                            duration: 5 + (item.length % 3),
                                            repeat: Infinity,
                                            ease: "easeInOut",
                                            delay: (item.length % 5) * 0.2
                                        }
                                    } : undefined}
                                >
                                    {renderCard(item)}
                                </Reorder.Item>
                            );
                        })}
                    </Reorder.Group>

                    {/* Lifetime Usage Row */}
                    <motion.div
                        variants={itemVariants}
                        className={`${isRedAlert ? "bg-neutral-900/30 backdrop-blur-sm" : "bg-neutral-900"} border border-neutral-800/50 rounded-xl p-3 md:p-4 flex flex-col lg:flex-row lg:items-center justify-between gap-4 transition-all duration-500`}
                    >
                        <span className="text-sm font-semibold text-neutral-400 uppercase tracking-wider whitespace-nowrap md:mr-8">全期間 (History)</span>
                        {/* Fixed: Grid instead of overflow-x-auto */}
                        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 w-full gap-4 md:gap-8">
                            <div className="flex flex-col">
                                <span className="text-[10px] md:text-xs text-neutral-600 leading-none mb-1">Stable Chat</span>
                                <span className="text-lg md:text-2xl font-mono text-green-400 leading-none">
                                    <AnimatedCounter value={usage?.lifetime_tokens?.stable || 0} />
                                </span>
                            </div>
                            <div className="flex flex-col">
                                <span className="text-[10px] md:text-xs text-neutral-600 leading-none mb-1">High Think</span>
                                <span className="text-lg md:text-2xl font-mono text-cyan-400 leading-none">
                                    <AnimatedCounter value={usage?.lifetime_tokens?.high || 0} />
                                </span>
                            </div>
                            <div className="flex flex-col">
                                <span className="text-[10px] md:text-xs text-neutral-600 leading-none mb-1">Optimization</span>
                                <span className="text-lg md:text-2xl font-mono text-purple-400 leading-none">
                                    <AnimatedCounter value={usage?.lifetime_tokens?.optimization || 0} />
                                </span>
                            </div>
                            <div className="flex flex-col lg:border-l border-neutral-800 lg:pl-8">
                                <span className="text-[10px] md:text-xs text-neutral-500 leading-none mb-1">Total Tokens</span>
                                <span className="text-lg md:text-2xl font-mono text-white leading-none">
                                    <AnimatedCounter value={
                                        (usage?.lifetime_tokens?.high || 0) +
                                        (usage?.lifetime_tokens?.stable || 0) +
                                        (usage?.lifetime_tokens?.optimization || 0) +
                                        (usage?.lifetime_tokens?.burn || 0)
                                    } />
                                </span>
                            </div>
                            <div className="flex flex-col lg:border-l border-neutral-800 lg:pl-8 col-span-2 md:col-span-1">
                                <span className="text-[10px] md:text-xs text-neutral-500 leading-none mb-1">Total USD</span>
                                <span className="text-lg md:text-2xl font-mono text-white leading-none">
                                    $<AnimatedCounter value={usage?.total_usd || 0} formatter={(v) => v.toFixed(4)} />
                                </span>
                            </div>
                        </div>
                    </motion.div>

                    {/* User Grid */}
                    <motion.div
                        variants={itemVariants}
                        className={`${isRedAlert ? "bg-neutral-900/30 backdrop-blur-sm" : "bg-neutral-900"} border border-neutral-800 rounded-2xl overflow-hidden shadow-2xl p-3 md:p-4 transition-all duration-500`}
                    >
                        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-4 gap-4">
                            <div className="flex items-center gap-4">
                                <h2 className="text-xl md:text-2xl font-bold text-white flex items-center gap-3">
                                    <Server className="w-5 h-5 md:w-6 md:h-6 text-indigo-500" />
                                    アクティビティ
                                </h2>
                                <span className="hidden md:block text-xs text-neutral-500 border-l border-neutral-800 pl-4 leading-none">
                                    Density: Scaled + Tight (16px)
                                </span>
                            </div>

                            {/* Status Legend */}
                            <div className="flex gap-4 md:gap-6">
                                <div className="flex items-center gap-2 text-xs text-neutral-500">
                                    <span className="w-2 h-2 rounded-full bg-neutral-500"></span> 待機中
                                </div>
                                <div className="flex items-center gap-2 text-xs text-neutral-500">
                                    <span className="w-2 h-2 rounded-full bg-cyan-500"></span> 処理中
                                </div>
                                <div className="flex items-center gap-2 text-xs text-neutral-500">
                                    <span className="w-2 h-2 rounded-full bg-green-500"></span> 最適化済
                                </div>
                            </div>
                        </div>


                        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-4 px-1 gap-3">
                            <div className="flex flex-wrap gap-2 w-full md:w-auto">
                                {/* Toggle Grouping */}
                                <button
                                    onClick={() => setGroupByServer(!groupByServer)}
                                    className="bg-neutral-800 hover:bg-neutral-700 text-neutral-400 hover:text-white px-2 py-1 md:px-3 md:py-1.5 rounded-lg text-[10px] md:text-xs font-medium transition-colors flex items-center gap-2 border border-neutral-700"
                                >
                                    {groupByServer ? <List className="w-3 h-3" /> : <LayoutGrid className="w-3 h-3" />}
                                    {groupByServer ? "全ユーザー" : "サーバー別"}
                                </button>

                                {/* Toggle Offline Users */}
                                <button
                                    onClick={() => setShowOffline(!showOffline)}
                                    className={`px-2 py-1 md:px-3 md:py-1.5 rounded-lg text-[10px] md:text-xs font-medium transition-all flex items-center gap-2 border ${showOffline
                                        ? "bg-indigo-900/40 border-indigo-500/50 text-indigo-300 hover:bg-indigo-800/50"
                                        : "bg-neutral-800 border-neutral-700 text-neutral-500 hover:text-neutral-400"
                                        }`}
                                >
                                    {showOffline ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
                                    {showOffline ? "オフラインを隠す" : `オフライン`}
                                </button>

                                <button
                                    onClick={() => setShowBots(!showBots)}
                                    className={`px-2 py-1 md:px-3 md:py-1.5 rounded-lg text-[10px] md:text-xs font-medium transition-all flex items-center gap-2 border ${showBots
                                        ? "bg-blue-900/40 border-blue-500/50 text-blue-300 hover:bg-blue-800/50"
                                        : "bg-neutral-800 border-neutral-700 text-neutral-500 hover:text-neutral-400"
                                        }`}
                                >
                                    <Bot className="w-3 h-3" />
                                    {showBots ? "BOTを隠す" : "BOTを表示"}
                                </button>

                                <button
                                    onClick={() => {
                                        if (autoSortServers) {
                                            // Switching from Auto -> Manual: Capture current order
                                            const currentOrder = sortedGroupedUsers.map(g => g.serverName);
                                            setManualOrder(currentOrder);
                                        }
                                        setAutoSortServers(!autoSortServers);
                                    }}
                                    className={`px-2 py-1 md:px-3 md:py-1.5 rounded-lg text-[10px] md:text-xs font-medium transition-all flex items-center gap-2 border ${autoSortServers
                                        ? "bg-cyan-900/40 border-cyan-500/50 text-cyan-300 hover:bg-cyan-800/50"
                                        : "bg-neutral-800 border-neutral-700 text-neutral-500 hover:text-neutral-400"
                                        }`}
                                >
                                    {autoSortServers ? <Zap className="w-3 h-3" /> : <Lock className="w-3 h-3" />}
                                    {autoSortServers ? "自動ソート" : "手動ソート"}
                                </button>
                            </div>

                            <button
                                onClick={() => setRefreshConfirmOpen(true)}
                                className="bg-neutral-800 hover:bg-neutral-700 text-neutral-400 hover:text-white px-2 py-1 md:px-3 md:py-1.5 rounded-lg text-[10px] md:text-xs font-medium transition-colors flex items-center gap-2 border border-neutral-700 ml-auto md:ml-0 active:scale-95"
                            >

                                <RefreshCcw className="w-3 h-3" />
                                強制更新
                            </button>
                        </div>

                        <div className="flex flex-col gap-8">
                            {groupByServer ? (
                                autoSortServers ? (
                                    // Auto Sort Mode (Standard List)
                                    visibleGroupedUsers.map(({ serverName, users }) => (
                                        <div key={serverName} className="flex flex-col gap-4">
                                            <motion.h3
                                                layout
                                                initial={{ opacity: 0, x: -20 }}
                                                animate={{ opacity: 1, x: 0 }}
                                                className="text-lg font-bold text-white/80 pl-4 border-l-4 border-cyan-500 flex items-center gap-2"
                                            >
                                                <Server className="w-4 h-4 text-cyan-400" />
                                                <span className={`transition-all ${screenshotMode ? "blur-md opacity-50" : ""}`}>
                                                    {serverName}
                                                </span>
                                                <span className="text-xs font-normal text-neutral-600 bg-neutral-900/50 px-2 py-0.5 rounded-full border border-neutral-800">
                                                    {users.length} Users
                                                </span>
                                            </motion.h3>

                                            <motion.div
                                                layout
                                                className="grid grid-cols-1 xl:grid-cols-2 2xl:grid-cols-3 gap-3"
                                            >
                                                <AnimatePresence initial={false}>
                                                    {users.map((user, index) => (
                                                        <UserCard
                                                            key={user.discord_user_id}
                                                            user={user}
                                                            index={index}
                                                            screenshotMode={screenshotMode}
                                                            setSelectedUser={setSelectedUser}
                                                            isSelected={selectedUser === user.discord_user_id}
                                                        />
                                                    ))}
                                                </AnimatePresence>
                                            </motion.div>
                                        </div>
                                    ))
                                ) : (
                                    // Manual Sort Mode (Reorderable)
                                    <Reorder.Group axis="y" values={visibleGroupedUsers.map(g => g.serverName)} onReorder={setManualOrder} className="flex flex-col gap-8">
                                        {visibleGroupedUsers.map(({ serverName, users }) => (
                                            <Reorder.Item key={serverName} value={serverName} className="flex flex-col gap-4 bg-neutral-900/20 rounded-xl p-2 border border-neutral-800/50 cursor-move">
                                                <div className="flex items-center gap-2 pl-2">
                                                    <GripVertical className="w-4 h-4 text-neutral-600" />
                                                    <h3 className="text-lg font-bold text-white/80 pl-2 border-l-4 border-neutral-600 flex items-center gap-2">
                                                        <Server className="w-4 h-4 text-neutral-400" />
                                                        <span className={`transition-all ${screenshotMode ? "blur-md opacity-50" : ""}`}>
                                                            {serverName}
                                                        </span>
                                                        <span className="text-xs font-normal text-neutral-600 bg-neutral-900/50 px-2 py-0.5 rounded-full border border-neutral-800">
                                                            {users.length} Users
                                                        </span>
                                                    </h3>
                                                </div>

                                                <div className="grid grid-cols-1 xl:grid-cols-2 2xl:grid-cols-3 gap-3 pointer-events-none lg:pointer-events-auto">
                                                    {users.map((user, index) => (
                                                        <UserCard
                                                            key={user.discord_user_id}
                                                            user={user}
                                                            index={index}
                                                            screenshotMode={screenshotMode}
                                                            setSelectedUser={setSelectedUser}
                                                            isSelected={selectedUser === user.discord_user_id}
                                                        />
                                                    ))}
                                                </div>
                                            </Reorder.Item>
                                        ))}
                                    </Reorder.Group>
                                )
                            ) : (
                                <motion.div
                                    layout
                                    className="grid grid-cols-1 xl:grid-cols-2 2xl:grid-cols-3 gap-3"
                                >
                                    <AnimatePresence initial={false}>
                                        {visibleAllUsers.map((user, index) => (
                                            <UserCard
                                                key={user.discord_user_id}
                                                user={user}
                                                index={index}
                                                screenshotMode={screenshotMode}
                                                setSelectedUser={setSelectedUser}
                                                isSelected={selectedUser === user.discord_user_id}
                                            />
                                        ))}
                                    </AnimatePresence>
                                </motion.div>
                            )}
                        </div>
                    </motion.div>
                </motion.div>


                {/* Float Button */}
                {
                    !screenshotMode && (
                        <button
                            onClick={toggleScreenshotMode}
                            className="fixed bottom-8 right-8 bg-black text-white p-4 rounded-full shadow-2xl hover:scale-110 active:scale-95 transition-transform z-50 group flex items-center justify-center gap-2 border border-neutral-700"
                        >
                            {screenshotMode ? <EyeOff className="w-6 h-6" /> : <Camera className="w-6 h-6" />}

                            <span className="absolute right-full mr-4 bg-black text-white text-sm px-3 py-1.5 rounded border border-neutral-800 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none font-medium">
                                Video Mode (Press ESC to Exit)
                            </span>
                        </button>
                    )
                }
                {/* Modal */}
                <AnimatePresence>
                    {selectedUser && (() => {
                        // Find user object for initial data
                        const initialUser = sortedAllUsers.find(u => u.discord_user_id === selectedUser) || null;
                        return (
                            <UserDetailModal
                                key={selectedUser}
                                userId={selectedUser}
                                initialUser={initialUser}
                                onClose={() => setSelectedUser(null)}
                            />
                        );
                    })()}
                </AnimatePresence>

                {/* Confirmation Modal */}
                <AnimatePresence>
                    {refreshConfirmOpen && (
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
                            onClick={() => setRefreshConfirmOpen(false)}
                        >
                            <motion.div
                                initial={{ scale: 0.9, y: 20 }}
                                animate={{ scale: 1, y: 0 }}
                                exit={{ scale: 0.9, y: 20 }}
                                onClick={(e) => e.stopPropagation()}
                                className="bg-neutral-900 border border-neutral-700 rounded-2xl p-6 max-w-sm w-full shadow-2xl relative overflow-hidden"
                            >
                                {/* Background FX */}
                                <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-cyan-500 to-purple-500" />

                                <h3 className="text-xl font-bold text-white mb-2 flex items-center gap-2">
                                    <RefreshCcw className="w-5 h-5 text-cyan-400" />
                                    強制更新の確認
                                </h3>
                                <p className="text-neutral-400 text-sm mb-6 leading-relaxed">
                                    全ユーザーのプロファイルを再スキャンします。<br />
                                    <span className="text-yellow-500/80 text-xs">※未登録(Ghost)ユーザーも自動的に最適化されます。</span>
                                </p>

                                <div className="flex justify-end gap-3">
                                    <button
                                        onClick={() => setRefreshConfirmOpen(false)}
                                        className="px-4 py-2 rounded-lg text-sm text-neutral-400 hover:text-white hover:bg-white/5 transition-colors"
                                    >
                                        キャンセル
                                    </button>
                                    <button
                                        onClick={async () => {
                                            try {
                                                await fetch("http://127.0.0.1:8000/api/system/refresh_profiles", { method: "POST" });
                                                setRefreshConfirmOpen(false);
                                                setRefreshSuccess(true);
                                                setTimeout(() => setRefreshSuccess(false), 3000); // Hide success after 3s
                                            } catch (e) {
                                                console.error("Error:", e);
                                                alert("エラーが発生しました: " + e);
                                            }
                                        }}
                                        className="px-4 py-2 rounded-lg text-sm font-bold bg-white text-black hover:scale-105 active:scale-95 transition-all shadow-lg shadow-cyan-500/20"
                                    >
                                        実行する
                                    </button>
                                </div>
                            </motion.div>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Success Toast */}
                <AnimatePresence>
                    {refreshSuccess && (
                        <motion.div
                            initial={{ opacity: 0, y: 50 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: 20 }}
                            className="fixed bottom-8 left-1/2 -translate-x-1/2 z-[110] bg-green-500/10 border border-green-500/50 text-green-400 px-6 py-3 rounded-full shadow-2xl backdrop-blur-md flex items-center gap-3"
                        >
                            <CheckCircle2 className="w-5 h-5" />
                            <span className="font-bold">最適化を開始しました</span>
                        </motion.div>
                    )}
                </AnimatePresence>
                {historyLane && (
                    <HistoryModal lane={historyLane} onClose={() => setHistoryLane(null)} />
                )}
            </LayoutGroup>
        </div >
    );
}

// Sub-component for User Card to memoize and clean up rendering
const UserCardBase = ({ user, index, screenshotMode, setSelectedUser, isSelected }: {
    user: User,
    index: number,
    screenshotMode: boolean,
    setSelectedUser: (id: string) => void,
    isSelected: boolean
}) => {
    // Determine "Processing" vs "Queued" based on GLOBAL Sorted List
    const statusLower = user.status?.toLowerCase() || "";
    const isPending = statusLower === "pending";
    const isNew = statusLower === "new";
    const isOptimized = statusLower === "optimized";
    const isProcessing = statusLower === "processing" || user.impression === "Processing...";
    const isError = statusLower === "error";
    const isQueued = isPending && !isProcessing;
    const optPercent = Math.min(Math.round(((user.cost_usage?.optimization || 0) / 200000) * 100), 99);

    const cardTransition = isSelected
        ? { type: "spring", stiffness: 320, damping: 28, mass: 0.9 }
        : {
            type: "spring",
            stiffness: 210,
            damping: 20,
            mass: 1,
            delay: Math.min(index * 0.02, 0.1)
        };

    // Helpers (Inline to avoid scope issues)
    const maskName = (name: string | null) => screenshotMode ? "User-Protected" : (name || "Unknown");
    const maskID = (id: string) => screenshotMode ? "****-****-****" : id;
    const maskAvatar = (name: string | null) => screenshotMode ? "?" : (name ? name.charAt(0).toUpperCase() : "?");

    // Animation style for hidden content
    const hiddenAnim = {
        opacity: isSelected ? 0 : 1,
        transition: { duration: 0.2 }
    };

    return (
        <motion.div
            layoutId={user.discord_user_id}
            custom={index}
            transition={cardTransition}
            whileHover={!isSelected ? {
                scale: 1.02,
                y: -5,
                rotateX: 4,
                rotateY: -2,
                transition: { type: "spring", stiffness: 300, damping: 20 }
            } : undefined}
            whileTap={{ scale: 0.98 }}
            onClick={() => setSelectedUser(user.discord_user_id)}
            style={{ willChange: "transform, opacity", translateZ: 0 }}
            className={`
  relative overflow-hidden rounded-xl border p-3 flex items-center gap-4 cursor-pointer group
                ${isOptimized
                    ? "bg-neutral-950/50 border-neutral-800/50 hover:bg-neutral-900/80"
                    : isProcessing
                        ? "bg-cyan-950/30 border-cyan-500/60 ring-1 ring-cyan-500/20 shadow-[0_0_15px_rgba(6,182,212,0.15)]"
                        : isError
                            ? "bg-red-950/20 border-red-500/50 ring-1 ring-red-500/10 shadow-[0_0_15px_rgba(239,68,68,0.1)]"
                            : isPending
                                ? "bg-amber-950/20 border-amber-500/40"
                                : "bg-neutral-900/50 border-neutral-800 text-neutral-500 opacity-60 grayscale-[0.5] hover:opacity-100 hover:grayscale-0"
                }
`}>
            {/* Background Layer */}
            <div
                className={`absolute inset-0 rounded-xl border transition-colors duration-300 bg-cover bg-center
                ${isOptimized
                        ? "bg-neutral-950/50 border-neutral-800/50 group-hover:bg-neutral-900/80"
                        : isProcessing
                            ? "bg-cyan-950/30 border-cyan-500/60 ring-1 ring-cyan-500/20 shadow-[0_0_15px_rgba(6,182,212,0.15)]"
                            : isError
                                ? "bg-red-950/30 border-red-500/60 ring-1 ring-red-500/20 shadow-[0_0_15px_rgba(239,68,68,0.2)]"
                                : isPending
                                    ? "bg-amber-950/20 border-amber-500/40 shadow-[0_0_10px_rgba(245,158,11,0.1)]"
                                    : "bg-neutral-900/50 border-neutral-800"
                    }
                ${!isProcessing && !isOptimized && !isPending && !isError ? "opacity-60 grayscale-[0.5] group-hover:grayscale-0" : ""}
                ${(user as any).banner_url ? "opacity-30 group-hover:opacity-50 grayscale-[0.8] group-hover:grayscale-0" : ""}
                `}
                style={{
                    backgroundImage: (user as any).banner_url ? `url(${(user as any).banner_url})` : undefined
                }}
            />

            {/* Overlay Gradient for Text Readability if Banner Exists */}
            {(user as any).banner_url && (
                <div className="absolute inset-0 bg-gradient-to-r from-neutral-950/90 via-neutral-950/80 to-transparent z-0 rounded-xl" />
            )}

            {/* Content Container */}
            <div className="relative z-10 flex items-center gap-4 w-full">

                {/* Status Bar Indicator - ALWAYS VISIBLE */}
                <div
                    className={`absolute left-[-0.75rem] top-[-0.75rem] bottom-[-0.75rem] w-1 rounded-l-xl z-20
                        ${isOptimized ? "bg-emerald-500"
                            : isProcessing ? "bg-cyan-400 shadow-[0_0_10px_cyan]"
                                : isError ? "bg-red-500 shadow-[0_0_10px_red]"
                                    : isPending ? "bg-amber-500 shadow-[0_0_10px_amber]"
                                        : "bg-neutral-600"}`}
                />

                {/* Avatar - ALWAYS VISIBLE */}
                <motion.div layoutId={`avatar-${user.discord_user_id}`} className="flex-shrink-0 ml-1 relative">
                    <div
                        className={`w-12 h-12 rounded-xl flex items-center justify-center font-bold text-xl shadow-lg transition-all overflow-hidden ${screenshotMode ? "blur-md" : ""
                            } ${isOptimized
                                ? "bg-neutral-800 text-neutral-600 border border-neutral-700"
                                : isProcessing
                                    ? "bg-cyan-950 text-cyan-400 border border-cyan-500/50"
                                    : "bg-neutral-800 text-neutral-600 border border-neutral-700"
                            }`}>
                        {isProcessing ? (
                            <Loader2 className="w-5 h-5 animate-spin" />
                        ) : (user as any).avatar_url ? (
                            <img
                                src={(user as any).avatar_url}
                                alt=""
                                className="w-full h-full rounded-xl object-cover"
                            />
                        ) : (
                            maskAvatar(user.display_name || "Unknown")
                        )}
                    </div>

                    {/* Discord Status Indicator */}
                    <div className={`absolute -bottom-1 -right-1 w-4 h-4 rounded-full border-2 border-neutral-950 flex items-center justify-center z-20
                        ${user.discord_status === "online" ? "bg-green-500" :
                            user.discord_status === "idle" ? "bg-amber-500" :
                                user.discord_status === "dnd" ? "bg-red-500" :
                                    "bg-neutral-600/50" // Offline
                        }
                    `}>
                        {user.discord_status === "idle" && (
                            <div className="w-2 h-2 bg-neutral-950 rounded-full -mt-1 -ml-1" /> // Moon shape for idle? Or just solid amber. Standard is solid amber with moon cutout usually, but solid amber dot is fine.
                        )}
                        {user.discord_status === "dnd" && (
                            <div className="w-2 h-0.5 bg-neutral-950 rounded-full" /> // Do Not Disturb (Minus sign)
                        )}
                    </div>
                </motion.div>


                {/* Hidden Content Wrapper (Fades out when selected) */}
                <motion.div animate={hiddenAnim} className="flex-1 min-w-0 flex items-center gap-4 pl-1">

                    {/* Impression Badge */}
                    {(user.impression || isProcessing || isPending || isError) && (
                        <div className={`absolute top-[-0.75rem] right-[-0.75rem] px-2 py-0.5 text-[10px] font-bold border-l border-b rounded-bl-lg backdrop-blur-sm z-10 transition-colors max-w-[120px] truncate
                            ${isProcessing ? "bg-cyan-900/80 text-cyan-200 border-cyan-500/30 shadow-[0_0_8px_rgba(6,182,212,0.3)]" :
                                isError ? "bg-red-950/90 text-red-200 border-red-500/40 shadow-[0_0_10px_rgba(239,68,68,0.4)]" :
                                    isPending ? "bg-amber-950/80 text-amber-400 border-amber-500/30" :
                                        "bg-cyan-950/80 text-cyan-400 border-cyan-500/20 group-hover:bg-cyan-900 group-hover:text-cyan-200"}
                        `} title={user.impression || ""}>
                            {user.impression || (isProcessing ? "分析実行中..." : isPending ? "キュー待機中..." : "")}
                        </div>
                    )}

                    {/* Main Info - Grid Layout */}
                    <div className="flex-grow min-w-0 grid grid-cols-12 gap-4 items-center">
                        {/* Identity */}
                        <div className="col-span-4 lg:col-span-4">
                            <div className="flex items-center gap-2 overflow-hidden">
                                <span className={`font-bold text-lg md:text-xl block truncate leading-tight transition-all 
                                    ${screenshotMode ? "blur-sm opacity-50" : ""}
                                    ${isProcessing ? "text-cyan-100" : "text-white"}
                                `}>
                                    {maskName(user.display_name || "Unknown")}
                                </span>
                                {user.is_nitro && (
                                    <span className="flex-shrink-0 inline-flex items-center gap-0.5 bg-pink-500/20 text-pink-300 text-[10px] px-1.5 py-0.5 rounded border border-pink-500/30">
                                        <Rocket className="w-3 h-3" />
                                        NITRO
                                    </span>
                                )}
                                {user.is_bot && (
                                    <span className="flex-shrink-0 inline-flex items-center gap-0.5 bg-indigo-500/20 text-indigo-300 text-[10px] px-1.5 py-0.5 rounded border border-indigo-500/30">
                                        <Bot className="w-3 h-3" />
                                        BOT
                                    </span>
                                )}
                            </div>
                            <span className={`text-[10px] md:text-sm font-mono truncate block mt-0.5 leading-none transition-all ${screenshotMode ? "blur-sm" : ""} ${isProcessing ? "text-cyan-500/70" : "text-neutral-500"}`}>
                                {isProcessing ? "PROCESSING..." : `ID: ${maskID(user.real_user_id || user.discord_user_id)}` + (user.message_count ? ` • ${user.message_count} Msgs` : "")}
                            </span>

                            {/* Traits Tags */}
                            {user.traits && user.traits.length > 0 && !isProcessing && (
                                <div className="flex flex-wrap gap-1 mt-1 opacity-90 relative z-10">
                                    {user.traits.slice(0, 3).map((t, i) => (
                                        <span key={i} className="text-[9px] px-1.5 py-0.5 rounded-sm bg-neutral-800/80 text-neutral-400 border border-neutral-700/50 leading-none truncate max-w-[100px] shadow-sm">
                                            {t}
                                        </span>
                                    ))}
                                    {user.traits.length > 3 && (
                                        <span className="text-[9px] text-neutral-600 px-1 py-0.5 font-mono">+{user.traits.length - 3}</span>
                                    )}
                                </div>
                            )}
                        </div>

                        {/* Mode & Cost */}
                        <div className="col-span-3 lg:col-span-3 flex flex-col items-start gap-1">
                            {user.mode?.includes("Private") ? (
                                <span className="inline-flex items-center gap-1 md:gap-2 px-1.5 md:py-0.5 rounded bg-neutral-800 text-neutral-300 border border-neutral-700 text-[10px] md:text-sm font-bold leading-none">
                                    <Lock className="w-3 h-3 md:w-4 md:h-4" />
                                    プライベート
                                </span>
                            ) : user.mode?.includes("API") ? (
                                <span className="inline-flex items-center gap-1 md:gap-2 px-1.5 md:py-1 rounded bg-cyan-950/40 text-cyan-400 border border-cyan-500/30 text-xs md:text-xl font-black leading-none tracking-tight">
                                    <Cloud className="w-3 h-3 md:w-5 md:h-5" />
                                    API
                                </span>
                            ) : (
                                <span className="text-neutral-700 text-xs">-</span>
                            )}
                            <div className="flex items-center gap-1 md:gap-2 text-[10px] md:text-xs leading-none ml-0.5">
                                <span className="text-neutral-500 font-medium">USD</span>
                                <span className="text-white font-mono text-xs md:text-base font-bold">
                                    $<AnimatedCounter value={user.cost_usage?.total_usd || 0} formatter={(v) => v.toFixed(4)} delay={0} />
                                </span>
                            </div>
                        </div>

                        {/* Stats */}
                        <div className="col-span-4 lg:col-span-4 flex flex-col gap-1 md:gap-1.5">
                            {/* High Usage */}
                            <div className="flex justify-between items-center text-[10px] md:text-xs leading-none">
                                <span className="text-neutral-400 font-medium">High</span>
                                <span className="text-cyan-200 font-mono text-[10px] md:text-sm">
                                    <AnimatedCounter value={user.cost_usage?.high || 0} delay={0} />
                                </span>
                            </div>
                            <div className="h-1 md:h-1.5 bg-neutral-800 rounded-full overflow-hidden w-full">
                                <motion.div className="h-full bg-cyan-500/50" initial={{ width: 0 }} animate={{ width: `${Math.min(((user.cost_usage?.high || 0) / (200000 / 10)) * 100, 100)}%` }} transition={{ type: "spring", stiffness: 100, damping: 20, delay: 0.2 }} />
                            </div>

                            {/* Opt Usage */}
                            <div className="flex justify-between items-center text-[10px] md:text-xs leading-none">
                                <span className="text-neutral-400 font-medium">Opt</span>
                                <span className="text-purple-300 font-mono text-[10px] md:text-sm">
                                    <AnimatedCounter value={user.cost_usage?.optimization || 0} delay={0} />
                                </span>
                            </div>
                            <div className="h-1 md:h-1.5 bg-neutral-800 rounded-full overflow-hidden w-full">
                                <motion.div className="h-full bg-purple-500/50" initial={{ width: 0 }} animate={{ width: `${Math.min(((user.cost_usage?.optimization || 0) / 200000) * 100, 100)}%` }} transition={{ type: "spring", stiffness: 100, damping: 20, delay: 0.3 }} />
                            </div>
                        </div>

                        {/* Status Icon */}
                        <div className="col-span-1 flex justify-end">
                            {isError ? (
                                <div className="text-red-500 shadow-[0_0_10px_rgba(239,68,68,0.5)]">
                                    <AlertTriangle className="w-6 h-6" />
                                </div>
                            ) : isOptimized ? (
                                <div className="text-green-500">
                                    <CheckCircle2 className="w-6 h-6" />
                                </div>
                            ) : isProcessing ? (
                                <CircularProgress
                                    size={32}
                                    strokeWidth={3}
                                    color="text-cyan-400"
                                    label={`${optPercent}%`}
                                    percent={optPercent}
                                />
                            ) : isPending ? (
                                <div className="text-amber-500 opacity-60">
                                    <RefreshCcw className="w-5 h-5 animate-spin-slow" />
                                </div>
                            ) : (
                                <div className="w-6 h-6 rounded-full border-2 border-neutral-700 border-dashed animate-spin-slow opacity-20" />
                            )}
                        </div>

                    </div>
                    {/* End Grid */}
                </motion.div >
                {/* End Hidden Content Wrapper */}
            </div >
            {/* End Content Container */}
        </motion.div >
    );
};

const UserCard = React.memo(UserCardBase, (prev, next) => {
    // Custom Comparator for React.memo
    // Returns TRUE if props are equal (DO NOT RENDER)
    if (prev.index !== next.index) return false;
    if (prev.screenshotMode !== next.screenshotMode) return false;
    if (prev.isSelected !== next.isSelected) return false;
    // Check User Data (Key fields only)
    if (prev.user.discord_user_id !== next.user.discord_user_id) return false;
    if (prev.user.status !== next.user.status) return false;
    if (prev.user.impression !== next.user.impression) return false;
    if (prev.user.points !== next.user.points) return false;
    if (prev.user.discord_status !== next.user.discord_status) return false;
    if (prev.user.display_name !== next.user.display_name) return false;
    if (prev.user.message_count !== next.user.message_count) return false;

    // Check cost usage for progress bars
    const hA = prev.user.cost_usage?.high || 0;
    const hB = next.user.cost_usage?.high || 0;
    if (hA !== hB) return false;

    const oA = prev.user.cost_usage?.optimization || 0;
    const oB = next.user.cost_usage?.optimization || 0;
    if (oA !== oB) return false;

    return true;
});
