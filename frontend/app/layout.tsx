import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { CircularNav } from "@/components/CircularNav";
import { cn } from "@/lib/utils";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "CodeBouncer",
  description: "AI-Powered Security Auditor",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={cn(inter.variable, mono.variable, "min-h-screen bg-background font-sans text-foreground selection:bg-green-500/30 selection:text-green-200")}>
        <div className="absolute inset-0 z-[-1] bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-green-900/10 via-background to-background" />
        <main className="relative z-0 min-h-screen p-6 md:p-12 pb-24">
          {children}
        </main>
        <CircularNav />
      </body>
    </html>
  );
}
