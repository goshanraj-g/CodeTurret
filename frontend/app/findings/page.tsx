"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { FileText, Calendar, AlertTriangle, CheckCircle, Search } from "lucide-react";

interface Scan {
    scan_id: string;
    repo_name: string;
    started_at: string;
    status: string;
    findings_count: number;
}

export default function FindingsPage() {
    const [scans, setScans] = useState<Scan[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetch("http://localhost:8000/scans")
            .then((res) => res.json())
            .then((data) => {
                setScans(data);
                setLoading(false);
            })
            .catch((err) => {
                console.error("Failed to load scans", err);
                setLoading(false);
            });
    }, []);

    return (
        <div className="mx-auto max-w-5xl">
            <div className="mb-8 flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-white">Scan Reports</h1>
                    <p className="text-muted-foreground">Archive of all security audits and their results.</p>
                </div>
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <input
                        type="text"
                        placeholder="Search reports..."
                        className="rounded-full border border-white/10 bg-white/5 pl-10 pr-4 py-2 text-sm text-white placeholder-white/20 focus:border-white/20 focus:outline-none"
                    />
                </div>
            </div>

            {loading ? (
                <div className="text-center text-muted-foreground py-10">Loading scan history...</div>
            ) : (
                <div className="grid gap-4">
                    {scans.map((scan, i) => (
                        <motion.div
                            key={scan.scan_id}
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: i * 0.05 }}
                        >
                            <Link
                                href={`/findings/${scan.scan_id}`}
                                className="group flex items-center justify-between rounded-xl border border-white/5 bg-white/5 p-4 transition-all hover:bg-white/10 hover:border-white/10"
                            >
                                <div className="flex items-center gap-4">
                                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-500/10 text-blue-400">
                                        <FileText className="h-5 w-5" />
                                    </div>
                                    <div>
                                        <div className="font-mono font-medium text-white group-hover:text-blue-400 transition-colors">
                                            {scan.repo_name}
                                        </div>
                                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                            <Calendar className="h-3 w-3" />
                                            {new Date(scan.started_at).toLocaleString()}
                                        </div>
                                    </div>
                                </div>

                                <div className="flex items-center gap-6">
                                    <div className="text-right">
                                        <div className="text-xs text-muted-foreground">Findings</div>
                                        <div className={`font-mono font-bold ${scan.findings_count > 0 ? "text-red-400" : "text-green-400"}`}>
                                            {scan.findings_count}
                                        </div>
                                    </div>
                                    <div className="text-right">
                                        <div className="text-xs text-muted-foreground">Status</div>
                                        <div className="flex items-center gap-1.5 font-medium text-white">
                                            {scan.status === "COMPLETED" ? (
                                                <>
                                                    <CheckCircle className="h-3 w-3 text-green-500" /> Completed
                                                </>
                                            ) : (
                                                <>
                                                    <AlertTriangle className="h-3 w-3 text-yellow-500" /> {scan.status}
                                                </>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </Link>
                        </motion.div>
                    ))}

                    {scans.length === 0 && (
                        <div className="rounded-xl border border-dashed border-white/10 p-10 text-center text-muted-foreground">
                            No scans found. Run a scan to generate reports.
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
