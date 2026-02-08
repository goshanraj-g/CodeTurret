"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { motion } from "framer-motion";
import { AlertTriangle, CheckCircle, Code, Bug, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

interface Finding {
    finding_id: string;
    file_path: string;
    line_number: number;
    severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
    vuln_type: string;
    description: string;
    code_snippet: string;
    fix_suggestion: string;
}

export default function FindingDetailsPage() {
    const params = useParams();
    const [findings, setFindings] = useState<Finding[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (params.scanId) {
            fetch(`http://localhost:8000/findings/${params.scanId}`)
                .then((res) => res.json())
                .then((data) => {
                    setFindings(data);
                    setLoading(false);
                })
                .catch((err) => {
                    console.error(err);
                    setLoading(false);
                });
        }
    }, [params.scanId]);

    const getSeverityColor = (sev: string) => {
        switch (sev) {
            case "CRITICAL": return "text-red-500 border-red-500/50 bg-red-500/10";
            case "HIGH": return "text-orange-500 border-orange-500/50 bg-orange-500/10";
            case "MEDIUM": return "text-yellow-500 border-yellow-500/50 bg-yellow-500/10";
            case "LOW": return "text-green-500 border-green-500/50 bg-green-500/10";
            default: return "text-gray-500 border-gray-500/50 bg-gray-500/10";
        }
    };

    return (
        <div className="mx-auto max-w-4xl">
            <Link
                href="/findings"
                className="mb-6 inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-white transition-colors"
            >
                <ArrowLeft className="h-4 w-4" /> Back to Scans
            </Link>

            <div className="mb-8">
                <h1 className="text-3xl font-bold text-white">Scan Results</h1>
                <p className="text-muted-foreground font-mono text-sm mt-1">ID: {params.scanId}</p>
            </div>

            {loading ? (
                <div>Loading findings...</div>
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
                            key={finding.finding_id}
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: i * 0.1 }}
                            className="overflow-hidden rounded-xl border border-white/10 bg-black/40 backdrop-blur-sm"
                        >
                            {/* Header */}
                            <div className="flex items-start justify-between border-b border-white/5 p-4 bg-white/5">
                                <div className="flex gap-4">
                                    <div className={cn("rounded-md px-2 py-1 text-xs font-bold border", getSeverityColor(finding.severity))}>
                                        {finding.severity}
                                    </div>
                                    <div>
                                        <h3 className="font-semibold text-white flex items-center gap-2">
                                            {finding.vuln_type}
                                        </h3>
                                        <div className="mt-1 font-mono text-xs text-muted-foreground">
                                            {finding.file_path}:{finding.line_number}
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Body */}
                            <div className="p-4 space-y-4">
                                <p className="text-sm text-gray-300 leading-relaxed">
                                    {finding.description}
                                </p>

                                {finding.code_snippet && (
                                    <div className="rounded-lg border border-white/10 bg-black/50 p-3">
                                        <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
                                            <Code className="h-3 w-3" /> Vulnerable Code
                                        </div>
                                        <pre className="overflow-x-auto text-sm text-red-300 font-mono">
                                            <code>{finding.code_snippet}</code>
                                        </pre>
                                    </div>
                                )}

                                {finding.fix_suggestion && (
                                    <div className="rounded-lg border border-green-500/20 bg-green-500/5 p-3">
                                        <div className="mb-2 flex items-center gap-2 text-xs text-green-400">
                                            <Bug className="h-3 w-3" /> Suggested Fix
                                        </div>
                                        <pre className="overflow-x-auto text-sm text-green-300 font-mono">
                                            <code>{finding.fix_suggestion}</code>
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
