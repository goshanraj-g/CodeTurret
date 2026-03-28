"use client";

import React, { useState, useRef } from "react";
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

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

export default function ScanPage() {
    const [repoUrl, setRepoUrl]     = useState("");
    const [isDeepScan, setIsDeepScan] = useState(false);
    const [isScanning, setIsScanning] = useState(false);
    const [logs, setLogs]           = useState<Log[]>([]);
    const [scanId, setScanId]       = useState<string | null>(null);
    const esRef                     = useRef<EventSource | null>(null);

    const addLog = (id: string, message: string, type: Log["type"]) =>
        setLogs(prev => [...prev, { id, timestamp: new Date().toLocaleTimeString(), message, type }]);

    const handleScan = async () => {
        if (!repoUrl || isScanning) return;

        // Close any existing stream
        esRef.current?.close();
        setLogs([]);
        setIsScanning(true);
        setScanId(null);

        addLog("init", "Queuing scan job...", "info");

        try {
            const res = await fetch(`${API}/api/scans`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ repoUrl, deepScan: isDeepScan }),
            });

            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: res.statusText }));
                throw new Error(err.detail || "Failed to queue scan");
            }

            const data = await res.json();
            const id: string = data.scanId;
            setScanId(id);
            addLog("queued", `Scan queued — ID: ${id}`, "success");
            addLog("target", `Target: ${repoUrl}`, "info");

            // Open SSE stream
            const es = new EventSource(`${API}${data.streamUrl}`);
            esRef.current = es;

            es.addEventListener("SCAN_STATUS", (e) => {
                const d = JSON.parse(e.data);
                addLog("status", `Status: ${d.data?.status}`, "info");
            });

            es.addEventListener("SCAN_STARTED", (e) => {
                const d = JSON.parse(e.data);
                addLog("started", `Scanning ${d.data?.totalFiles} files...`, "info");
            });

            es.addEventListener("FILE_SCANNED", (e) => {
                const d = JSON.parse(e.data);
                const f = d.data;
                const type = f.findings > 0 ? "warning" : "info";
                addLog(`file-${f.file}`, `${f.file} — ${f.findings > 0 ? `${f.findings} finding(s) [${f.severity}]` : "clean"}`, type);
            });

            es.addEventListener("FILE_SKIPPED", (e) => {
                const d = JSON.parse(e.data);
                addLog(`skip-${d.data?.file}`, `Skipped: ${d.data?.file}`, "info");
            });

            es.addEventListener("SCAN_COMPLETE", (e) => {
                const d = JSON.parse(e.data);
                const count = d.data?.totalFindings ?? 0;
                addLog("complete", `Scan complete — ${count} vulnerabilit${count === 1 ? "y" : "ies"} found.`, count > 0 ? "warning" : "success");
                if (count > 0) addLog("nav", `View findings → /findings/${data.scanId}`, "info");
                setIsScanning(false);
                es.close();
            });

            es.addEventListener("SCAN_FAILED", (e) => {
                const d = JSON.parse(e.data);
                addLog("failed", `Scan failed: ${d.data?.error}`, "error");
                setIsScanning(false);
                es.close();
            });

            es.onerror = () => {
                addLog("conn-err", "Stream connection lost.", "error");
                setIsScanning(false);
                es.close();
            };

        } catch (err) {
            addLog("err", String(err), "error");
            setIsScanning(false);
        }
    };

    return (
        <div className="mx-auto max-w-6xl space-y-8">
            <div className="space-y-2">
                <h1 className="text-3xl font-bold tracking-tight text-white">Target Scanner</h1>
                <p className="text-muted-foreground">Initiate a deep security audit on any public repository.</p>
            </div>

            <div className="grid gap-8 lg:grid-cols-2">
                {/* Left Column - Controls */}
                <div className="space-y-6">
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
                            onKeyDown={(e) => e.key === "Enter" && handleScan()}
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
                                    <span className="text-xs text-muted-foreground">Slower, more accurate (Gemini Pro)</span>
                                </div>
                            </div>
                        </div>

                        <button
                            onClick={handleScan}
                            disabled={isScanning || !repoUrl}
                            className={cn(
                                "mt-6 flex w-full items-center justify-center gap-2 rounded-xl py-4 font-semibold text-black transition-all",
                                isScanning || !repoUrl
                                    ? "bg-white/50 cursor-not-allowed"
                                    : "bg-white hover:bg-gray-100 hover:scale-[1.02] active:scale-[0.98]"
                            )}
                        >
                            {isScanning ? (
                                <div className="h-5 w-5 animate-spin rounded-full border-2 border-black border-t-transparent" />
                            ) : (
                                <><Play className="h-4 w-4" /> Initialize Scan</>
                            )}
                        </button>
                    </motion.div>

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
                            Hybrid AI architecture: <b>Gemini Flash</b> for rapid triage, <b>Gemini Pro</b> for deep analysis on high-risk findings.
                            Results stream in real-time via SSE.
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
                        <span className={cn(
                            "text-xs font-mono",
                            isScanning ? "text-green-400" : "text-muted-foreground"
                        )}>
                            {isScanning ? "● STREAMING" : "○ IDLE"}
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
