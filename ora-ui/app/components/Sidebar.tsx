"use client";

import { usePathname } from "next/navigation";
import { Plus, MessageSquare, Settings, User } from "lucide-react";

export default function Sidebar() {
    const pathname = usePathname();

    // Hide on dashboard
    if (pathname?.startsWith("/dashboard")) {
        return null;
    }

    return (
        <aside className="w-[260px] bg-[#171717] flex flex-col h-full flex-shrink-0 transition-width duration-300 hidden md:flex">

            {/* New Chat Button */}
            <div className="p-3">
                <button className="flex items-center gap-3 w-full px-3 py-3 rounded-md border border-white/20 hover:bg-[#212121] transition-colors text-sm text-white text-left">
                    <Plus className="w-4 h-4" />
                    <span>New chat</span>
                </button>
            </div>

            {/* History List */}
            <div className="flex-1 overflow-y-auto px-3 py-2 space-y-2 scrollbar-hidden">
                <p className="px-3 text-xs font-medium text-gray-500 py-2">Today</p>
                <HistoryItem label="Python Script Help" />
                <HistoryItem label="Recipe for Curry" />
                <HistoryItem label="Debugging Login" />

                <p className="px-3 text-xs font-medium text-gray-500 py-2 mt-4">Yesterday</p>
                <HistoryItem label="Trip Planning" />
            </div>

            {/* User / Settings */}
            <div className="p-3 border-t border-white/10 space-y-1">
                <SidebarItem icon={<User className="w-4 h-4" />} label="YoneRai12" />
                <SidebarItem icon={<Settings className="w-4 h-4" />} label="Settings" />
            </div>
        </aside>
    );
}

function HistoryItem({ label }: { label: string }) {
    return (
        <button className="flex items-center gap-3 w-full px-3 py-3 rounded-md hover:bg-[#212121] transition-colors text-sm text-gray-300 truncate text-left group">
            <MessageSquare className="w-4 h-4 text-gray-400 group-hover:text-white" />
            <span className="truncate">{label}</span>
        </button>
    )
}

function SidebarItem({ icon, label }: { icon: any, label: string }) {
    return (
        <button className="flex items-center gap-3 w-full px-3 py-3 rounded-md hover:bg-[#212121] transition-colors text-sm text-white text-left">
            {icon}
            <span>{label}</span>
        </button>
    )
}
