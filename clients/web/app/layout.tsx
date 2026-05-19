import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Activity, MessageSquare, ShieldCheck, Terminal } from "lucide-react";

import "./globals.css";

export const metadata: Metadata = {
  title: "YonerAI Public Mock Chat",
  description: "Credential-free local mock chat surface for the public Core API message contract.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="flex h-screen w-screen bg-[#212121] text-gray-100">
        <aside className="hidden h-full w-[260px] flex-shrink-0 flex-col border-r border-white/10 bg-[#171717] md:flex">
          <div className="border-b border-white/10 p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#10a37f]">
                <Activity className="h-5 w-5 text-white" />
              </div>
              <div>
                <p className="text-sm font-semibold text-white">YonerAI</p>
                <p className="text-xs text-gray-400">Public Core MVP</p>
              </div>
            </div>
          </div>

          <nav className="flex-1 space-y-1 p-3">
            <SidebarItem icon={<MessageSquare className="h-4 w-4" />} label="Mock chat" active />
            <SidebarItem icon={<Terminal className="h-4 w-4" />} label="Core API" />
            <SidebarItem icon={<ShieldCheck className="h-4 w-4" />} label="Public-safe boundary" />
          </nav>

          <div className="border-t border-white/10 p-4 text-xs text-gray-400">
            <p className="font-medium text-gray-200">Local checkpoint</p>
            <p className="mt-1 leading-relaxed">Offline mock only. No provider key, Discord token, or memory store.</p>
          </div>
        </aside>

        <main className="relative flex h-full flex-1 flex-col overflow-hidden">{children}</main>
      </body>
    </html>
  );
}

function SidebarItem({
  icon,
  label,
  active = false,
}: {
  icon: ReactNode;
  label: string;
  active?: boolean;
}) {
  return (
    <div
      className={`flex items-center gap-3 rounded-md px-3 py-3 text-sm ${
        active ? "bg-[#212121] text-white" : "text-gray-400"
      }`}
    >
      {icon}
      <span className="truncate">{label}</span>
    </div>
  );
}
