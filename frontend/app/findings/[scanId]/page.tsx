"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { motion } from "framer-motion";
import { AlertTriangle, CheckCircle, Code, Bug, ArrowLeft, GitCommit, Wand2, ExternalLink } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

interface Finding {
    id: string;
    filePath: string;
    lineNumber: number;
    severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
    vulnType: string;
    description: string;
    codeSnippet: string;
    fixSuggestion: string;
    commitHash: string | null;
    commitAuthor: string | null;
}

interface FixStatus {
    state: "idle" | "running" | "done" | "error";
    logs: string[];
    prUrl: string | null;
}

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

export default function FindingDetailsPage() {
    const params = useParams();
    const scanId = params.scanId as string;

    const [findings, setFindings] = useState<Finding[]>([]);
    const [loading, setLoading]   = useState(true);
    const [fix, setFix]           = useState<FixStatus>({ state: "idle", logs: [], prUrl: null });
    const esRef                   = useRef<EventSource | null>(null);

    useEffect(() => {
        if (scanId) {
            fetch(`${API}/api/findings/${scanId}`)
                .then(r => r.json())
                .then(data => { setFindings(data); setLoading(false); })
                .catch(() => setLoading(false));
        }
    }, [scanId]);

    const handleGenerateFixes = async () => {
        if (fix.state === "running") return;
        setFix({ state: "running", logs: ["Queuing fix job..."], prUrl: null });
        esRef.current?.close();

        try {
            const res = await fetch(`${API}/api/scans/${scanId}/fix`, { method: "POST" });
            if (!res.ok) {
                const err = await res.json().catch(() => ({ message: res.statusText }));
                setFix(f => ({ ...f, state: "error", logs: [...f.logs, `Error: ${err.message || res.statusText}`] }));
                return;
            }

            const data = await res.json();

            // If PR already exists, show it
            if (data.prUrl) {
                setFix({ state: "done", logs: ["Fix PR already exists."], prUrl: data.prUrl });
                return;
            }

            setFix(f => ({ ...f, logs: [...f.logs, "Fix job queued. Waiting for AI patches..."] }));

            const es = new EventSource(`${API}/api/scans/${scanId}/stream`);
            esRef.current = es;

            es.addEventListener("FIX_STARTED", (e) => {
                const d = JSON.parse(e.data);
                setFix(f => ({ ...f, logs: [...f.logs, `Fixing ${d.data?.filesToFix} file(s)...`] }));
            });

            es.addEventListener("FILE_FIXED", (e) => {
                const d = JSON.parse(e.data);
                setFix(f => ({ ...f, logs: [...f.logs, `Fixed: ${d.data?.file} (${d.data?.findingsFixed} issue(s))`] }));
            });

            es.addEventListener("FIX_FAILED", (e) => {
                const d = JSON.parse(e.data);
                setFix(f => ({ ...f, logs: [...f.logs, `Skipped: ${d.data?.file} — ${d.data?.error}`] }));
            });

            es.addEventListener("PR_CREATED", (e) => {
                const d = JSON.parse(e.data);
                setFix(f => ({ ...f, state: "done", logs: [...f.logs, "PR created!"], prUrl: d.data?.prUrl }));
                es.close();
            });

            es.onerror = () => {
                setFix(f => ({ ...f, state: "error", logs: [...f.logs, "Stream connection lost."] }));
                es.close();
            };

        } catch (err) {
            setFix(f => ({ ...f, state: "error", logs: [...f.logs, String(err)] }));
        }
    };

    const getSeverityColor = (sev: string) => {
        switch (sev) {
            case "CRITICAL": return "text-red-500 border-red-500/50 bg-red-500/10";
            case "HIGH":     return "text-orange-500 border-orange-500/50 bg-orange-500/10";
            case "MEDIUM":   return "text-yellow-500 border-yellow-500/50 bg-yellow-500/10";
            case "LOW":      return "text-green-500 border-green-500/50 bg-green-500/10";
            default:         return "text-gray-500 border-gray-500/50 bg-gray-500/10";
        }
    };

    return (
        <div className="mx-auto max-w-4xl">
            <Link href="/findings" className="mb-6 inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-white transition-colors">
                <ArrowLeft className="h-4 w-4" /> Back to Scans
            </Link>

            <div className="mb-8 flex items-start justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-white">Scan Results</h1>
                    <p className="text-muted-foreground font-mono text-sm mt-1">ID: {scanId}</p>
                </div>

                {findings.length > 0 && (
                    <div className="flex flex-col items-end gap-2">
                        <button
                            onClick={handleGenerateFixes}
                            disabled={fix.state === "running"}
                            className={cn(
                                "flex items-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold transition-all",
                                fix.state === "done"
                                    ? "bg-green-500/20 text-green-400 border border-green-500/30 cursor-default"
                                    : fix.state === "running"
                                    ? "bg-white/10 text-white/50 cursor-not-allowed"
                                    : "bg-purple-500/20 text-purple-300 border border-purple-500/30 hover:bg-purple-500/30"
                            )}
                        >
                            {fix.state === "running"
                                ? <div className="h-4 w-4 animate-spin rounded-full border-2 border-purple-300 border-t-transparent" />
                                : <Wand2 className="h-4 w-4" />
                            }
                            {fix.state === "done" ? "Fixes Applied" : fix.state === "running" ? "Generating..." : "Generate Fixes"}
                        </button>

                        {fix.prUrl && (
                            <a href={fix.prUrl} target="_blank" rel="noopener noreferrer"
                               className="flex items-center gap-1 text-xs text-green-400 hover:underline">
                                <ExternalLink className="h-3 w-3" /> View Pull Request
                            </a>
                        )}
                    </div>
                )}
            </div>

            {/* Fix progress log */}
            {fix.logs.length > 0 && (
                <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mb-6 rounded-xl border border-purple-500/20 bg-purple-500/5 p-4 font-mono text-xs"
                >
                    {fix.logs.map((l, i) => (
                        <div key={i} className={cn(
                            "leading-relaxed",
                            l.startsWith("Error") || l.startsWith("Skipped") ? "text-red-400" :
                            l.startsWith("Fixed") || l.includes("PR created") ? "text-green-400" :
                            "text-purple-300"
                        )}>{"> "}{l}</div>
                    ))}
                </motion.div>
            )}

            {loading ? (
                <div className="text-muted-foreground">Loading findings...</div>
            ) : findings.length === 0 ? (
                <div className="flex flex-col items-center justify-center rounded-2xl border border-white/10 bg-white/5 p-12 text-center">
                    <div className="mb-4 rounded-full bg-green-500/20 p-4">
                        <CheckCircle className="h-8 w-8 text-green-500" />
                    </div>
                    <h3 className="text-xl font-semibold text-white">All Clear</h3>
                    <p className="text-muted-foreground">No vulnerabilities detected in this scan.</p>
                </div>
            ) : (
                <div className="space-y-6">
                    {findings.map((finding, i) => (
                        <motion.div
                            key={finding.id}
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: i * 0.05 }}
                            className="overflow-hidden rounded-xl border border-white/10 bg-black/40 backdrop-blur-sm"
                        >
                            {/* Header */}
                            <div className="flex items-start justify-between border-b border-white/5 p-4 bg-white/5">
                                <div className="flex gap-4">
                                    <div className={cn("rounded-md px-2 py-1 text-xs font-bold border", getSeverityColor(finding.severity))}>
                                        {finding.severity}
                                    </div>
                                    <div>
                                        <h3 className="font-semibold text-white">{finding.vulnType}</h3>
                                        <div className="mt-1 font-mono text-xs text-muted-foreground">
                                            {finding.filePath}:{finding.lineNumber}
                                        </div>
                                        {finding.commitAuthor && (
                                            <div className="mt-1.5 flex items-center gap-1.5 text-xs text-muted-foreground">
                                                <GitCommit className="h-3 w-3" />
                                                <span>{finding.commitAuthor}</span>
                                                {finding.commitHash && (
                                                    <span className="font-mono text-white/40">{finding.commitHash.slice(0, 7)}</span>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>

                            {/* Body */}
                            <div className="p-4 space-y-4">
                                <p className="text-sm text-gray-300 leading-relaxed">{finding.description}</p>

                                {finding.codeSnippet && (
                                    <div className="rounded-lg border border-white/10 bg-black/50 p-3">
                                        <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
                                            <Code className="h-3 w-3" /> Vulnerable Code
                                        </div>
                                        <pre className="overflow-x-auto text-sm text-red-300 font-mono">
                                            <code>{finding.codeSnippet}</code>
                                        </pre>
                                    </div>
                                )}

                                {finding.fixSuggestion && (
                                    <div className="rounded-lg border border-green-500/20 bg-green-500/5 p-3">
                                        <div className="mb-2 flex items-center gap-2 text-xs text-green-400">
                                            <Bug className="h-3 w-3" /> Suggested Fix
                                        </div>
                                        <pre className="overflow-x-auto text-sm text-green-300 font-mono">
                                            <code>{finding.fixSuggestion}</code>
                                        </pre>
                                    </div>
                                )}
                            </div>
                        </motion.div>
                    ))}
                </div>
            )}
        </div>
    );
}
