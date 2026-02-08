"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import { TerminalOutput } from "@/components/TerminalOutput";
import { Play, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

interface Log {
    id: string;
    timestamp: string;
    message: string;
    type: "info" | "success" | "warning" | "error";
}

export default function ScanPage() {
    const [repoUrl, setRepoUrl] = useState("");
    const [isDeepScan, setIsDeepScan] = useState(false);
    const [isScanning, setIsScanning] = useState(false);
    const [logs, setLogs] = useState<Log[]>([]);

    const handleScan = async () => {
        if (!repoUrl) return;

        setIsScanning(true);
        setLogs([{ id: "init", timestamp: new Date().toLocaleTimeString(), message: "Initializing scan agent...", type: "info" }]);

        try {
            const res = await fetch("http://localhost:8000/scan", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ repo_url: repoUrl, deep_scan: isDeepScan }),
            });

            if (!res.ok) throw new Error("Scan failed to start");

            const data = await res.json();

            setLogs(prev => [
                ...prev,
                { id: "start", timestamp: new Date().toLocaleTimeString(), message: `Target acquired: ${repoUrl}`, type: "success" },
                { id: "files", timestamp: new Date().toLocaleTimeString(), message: `Analyzed ${data.total_files} files.`, type: "info" },
                { id: "findings", timestamp: new Date().toLocaleTimeString(), message: `Found ${data.total_findings} vulnerabilities.`, type: data.total_findings > 0 ? "warning" : "success" },
                { id: "complete", timestamp: new Date().toLocaleTimeString(), message: "Scan complete.", type: "success" },
            ]);
        } catch (err) {
            setLogs(prev => [...prev, { id: "err", timestamp: new Date().toLocaleTimeString(), message: String(err), type: "error" }]);
        } finally {
            setIsScanning(false);
        }
    };

    return (
        <div className="mx-auto max-w-6xl space-y-8">
            <div className="space-y-2">
                <h1 className="text-3xl font-bold tracking-tight text-white">Target Scanner</h1>
                <p className="text-muted-foreground">Initiate a deep security audit on any public repository.</p>
            </div>

            {/* Two-column layout: Controls on left, Terminal on right */}
            <div className="grid gap-8 lg:grid-cols-2">
                {/* Left Column - Controls */}
                <div className="space-y-6">
                    {/* Input Card */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-md"
                    >
                        <label className="block text-sm font-medium text-white mb-3">
                            Repository URL
                        </label>
                        <input
                            type="text"
                            placeholder="https://github.com/username/repo"
                            value={repoUrl}
                            onChange={(e) => setRepoUrl(e.target.value)}
                            className="w-full rounded-xl border border-white/10 bg-black/60 px-4 py-4 font-mono text-sm text-white placeholder-white/30 focus:border-green-500/50 focus:outline-none focus:ring-2 focus:ring-green-500/20 transition-all"
                        />

                        {/* Deep Scan Toggle */}
                        <div className="mt-6 flex items-center justify-between">
                            <div
                                className="flex cursor-pointer items-center gap-3"
                                onClick={() => setIsDeepScan(!isDeepScan)}
                            >
                                <div className={cn(
                                    "h-6 w-11 rounded-full p-1 transition-colors",
                                    isDeepScan ? "bg-green-500" : "bg-white/20"
                                )}>
                                    <div className={cn(
                                        "h-4 w-4 rounded-full bg-white shadow-sm transition-transform",
                                        isDeepScan ? "translate-x-5" : "translate-x-0"
                                    )} />
                                </div>
                                <div className="text-sm">
                                    <span className="block font-medium text-white">Deep Analysis</span>
                                    <span className="text-xs text-muted-foreground">Slower, more accurate</span>
                                </div>
                            </div>
                        </div>

                        {/* Scan Button */}
                        <button
                            onClick={handleScan}
                            disabled={isScanning || !repoUrl}
                            className={cn(
                                "mt-6 flex w-full items-center justify-center gap-2 rounded-xl py-4 font-semibold text-black transition-all",
                                isScanning
                                    ? "bg-white/50 cursor-not-allowed"
                                    : "bg-white hover:bg-gray-100 hover:scale-[1.02] active:scale-[0.98]"
                            )}
                        >
                            {isScanning ? (
                                <div className="h-5 w-5 animate-spin rounded-full border-2 border-black border-t-transparent" />
                            ) : (
                                <>
                                    <Play className="h-4 w-4" /> Initialize Scan
                                </>
                            )}
                        </button>
                    </motion.div>

                    {/* AI Info Card */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.1 }}
                        className="rounded-2xl border border-purple-500/20 bg-gradient-to-br from-purple-500/10 to-blue-500/10 p-6"
                    >
                        <div className="flex items-center gap-2 mb-3 text-purple-300">
                            <Sparkles className="h-4 w-4" />
                            <span className="text-sm font-semibold">AI Capabilities</span>
                        </div>
                        <p className="text-sm text-purple-200/70 leading-relaxed">
                            Scanner uses a <b>hybrid AI architecture</b>. Fast triage identifies hotspots, then deep analysis verifies high-risk findings.
                        </p>
                    </motion.div>
                </div>

                {/* Right Column - Terminal */}
                <motion.div
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.15 }}
                    className="flex flex-col"
                >
                    <div className="mb-3 flex items-center justify-between">
                        <span className="text-sm font-medium text-white">Live Output</span>
                        <span className="text-xs text-muted-foreground font-mono">
                            {isScanning ? "● ACTIVE" : "○ IDLE"}
                        </span>
                    </div>
                    <TerminalOutput
                        logs={logs}
                        className="flex-1 min-h-[450px] lg:min-h-[500px]"
                    />
                </motion.div>
            </div>
        </div>
    );
}
