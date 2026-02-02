
import "./globals.css";
import { Inter } from "next/font/google";
import Sidebar from "./components/Sidebar";

const inter = Inter({ subsets: ["latin"] });

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <title>ORA Dashboard</title>
      </head>
      <body className={`${inter.className} flex h-screen w-screen bg-[#212121] text-gray-100`}>
        <Sidebar />
        {/* Main Content */}
        <main className="flex-1 h-full relative flex flex-col overflow-hidden">
          {children}
        </main>
      </body>
    </html>
  );
}
