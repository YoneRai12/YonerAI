"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface ToolStat {
    name: string;
    count: number;
    avg_latency: number;
}

interface RecentCall {
    id: string;
    tool: string;
    status: string;
    latency: number;
    created_at: string;
}

interface DashboardData {
    total_runs: number;
    tools: ToolStat[];
    recent_tool_calls: RecentCall[];
}

export default function Dashboard() {
    const [data, setData] = useState<DashboardData | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetch("http://localhost:8001/v1/dashboard")
            .then((res) => res.json())
            .then((d) => {
                setData(d);
                setLoading(false);
            })
            .catch((err) => {
                console.error("Dashboard failed:", err);
                setLoading(false);
            });
    }, []);

    if (loading) {
        return (
            <div className="min-h-screen bg-[#0a0a0c] text-cyan-500 flex items-center justify-center font-mono">
                <div className="animate-pulse">INITIALIZING SYSTEM MONITOR...</div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-[#0a0a0c] text-gray-300 font-sans p-8">
            {/* Header */}
            <div className="max-w-7xl mx-auto flex justify-between items-center mb-12">
                <div>
                    <h1 className="text-4xl font-black text-white tracking-widest uppercase italic">
                        ORA <span className="text-cyan-500 font-light">Core</span>
                    </h1>
                    <p className="text-xs text-cyan-500/50 mt-1 font-mono tracking-tighter">
                        NERVE CENTER // SYSTEM STATUS: NOMINAL
                    </p>
                </div>
                <Link
                    href="/"
                    className="px-6 py-2 border border-cyan-500/30 text-cyan-500 hover:bg-cyan-500/10 transition-all text-xs font-mono uppercase tracking-widest"
                >
                    &lt; Return to Terminal
                </Link>
            </div>

            <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-8">

                {/* Metric Card: Total Runs */}
                <div className="bg-white/5 border border-white/10 p-6 backdrop-blur-md rounded-2xl">
                    <h3 className="text-xs font-mono text-cyan-500/70 uppercase mb-2">Total Cognitive Cycles</h3>
                    <div className="text-5xl font-bold text-white mb-1">
                        {data?.total_runs.toLocaleString()}
                    </div>
                    <div className="text-[10px] text-gray-500 font-mono italic">Total runs managed by Core</div>
                </div>

                {/* Metric Card: Tool Count */}
                <div className="bg-white/5 border border-white/10 p-6 backdrop-blur-md rounded-2xl">
                    <h3 className="text-xs font-mono text-cyan-500/70 uppercase mb-2">Active Tools</h3>
                    <div className="text-5xl font-bold text-white mb-1">
                        {data?.tools.length}
                    </div>
                    <div className="text-[10px] text-gray-500 font-mono italic">Enabled in global registry</div>
                </div>

                {/* Metric Card: Avg Latency */}
                <div className="bg-white/5 border border-white/10 p-6 backdrop-blur-md rounded-2xl">
                    <h3 className="text-xs font-mono text-cyan-500/70 uppercase mb-2">Avg System Latency</h3>
                    <div className="text-5xl font-bold text-white mb-1">
                        {Math.round(data?.tools.reduce((acc, curr) => acc + curr.avg_latency, 0) || 0 / (data?.tools.length || 1))}
                        <span className="text-xl ml-1 text-cyan-500">ms</span>
                    </div>
                    <div className="text-[10px] text-gray-500 font-mono italic">Global tool responsiveness</div>
                </div>

                {/* Tool Performance Table */}
                <div className="md:col-span-2 bg-white/5 border border-white/10 p-8 rounded-2xl">
                    <h2 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
                        <span className="w-2 h-2 bg-cyan-500 rounded-full animate-ping"></span>
                        Tool Performance Matrix
                    </h2>
                    <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm">
                            <thead className="text-gray-500 border-b border-white/10">
                                <tr>
                                    <th className="pb-4 font-mono font-normal">TOOL_IDENTIFIER</th>
                                    <th className="pb-4 font-mono font-normal">INVOCATIONS</th>
                                    <th className="pb-4 font-mono font-normal">AVG_LATENCY</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-white/5">
                                {data?.tools.map((t) => (
                                    <tr key={t.name} className="hover:bg-white/5 transition-colors group">
                                        <td className="py-4 text-cyan-400 font-mono">{t.name}</td>
                                        <td className="py-4 font-bold">{t.count}</td>
                                        <td className="py-4">
                                            <span className={`${t.avg_latency > 1000 ? 'text-orange-400' : 'text-green-400'}`}>
                                                {Math.round(t.avg_latency)}ms
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* Recent Activity Log */}
                <div className="bg-white/5 border border-white/10 p-8 rounded-2xl">
                    <h2 className="text-xl font-bold text-white mb-6">Real-time Log</h2>
                    <div className="space-y-6">
                        {data?.recent_tool_calls.map((c) => (
                            <div key={c.id} className="border-l-2 border-cyan-500/30 pl-4 py-1">
                                <div className="flex justify-between items-start mb-1">
                                    <span className="text-xs font-mono text-cyan-500 uppercase">{c.tool}</span>
                                    <span className={`text-[10px] px-2 py-0.5 rounded ${c.status === 'completed' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                                        }`}>
                                        {c.status}
                                    </span>
                                </div>
                                <div className="text-[10px] text-gray-500 font-mono">
                                    {new Date(c.created_at).toLocaleTimeString()} // {c.latency}ms
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

            </div>

            <style jsx global>{`
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@200;400;700;900&family=JetBrains+Mono:wght@300;400&display=swap');
        
        body {
          font-family: 'Outfit', sans-serif;
        }
        .font-mono {
          font-family: 'JetBrains Mono', monospace;
        }
      `}</style>
        </div>
    );
}
