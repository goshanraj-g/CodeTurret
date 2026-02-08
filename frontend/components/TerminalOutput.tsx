"use client";

import React, { useEffect, useRef } from "react";
import { motion } from "framer-motion";

interface Log {
    id: string;
    timestamp: string;
    message: string;
    type: "info" | "success" | "warning" | "error";
}

interface TerminalOutputProps {
    logs: Log[];
    className?: string;
}

export function TerminalOutput({ logs, className }: TerminalOutputProps) {
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [logs]);

    return (
        <div className={`relative overflow-hidden rounded-lg border border-white/5 bg-black/40 font-mono text-sm shadow-2xl backdrop-blur-sm ${className}`}>
            {/* Header */}
            <div className="flex items-center gap-2 border-b border-white/5 bg-white/5 px-4 py-2">
                <div className="flex gap-1.5">
                    <div className="h-3 w-3 rounded-full bg-red-500/20" />
                    <div className="h-3 w-3 rounded-full bg-yellow-500/20" />
                    <div className="h-3 w-3 rounded-full bg-green-500/20" />
                </div>
                <div className="ml-2 text-xs text-muted-foreground">scanner_output.log</div>
            </div>

            {/* Content */}
            <div ref={scrollRef} className="h-64 max-h-96 overflow-y-auto p-4 scroll-smooth">
                {logs.length === 0 ? (
                    <div className="text-muted-foreground italic">Coverage scan initialized... waiting for target.</div>
                ) : (
                    logs.map((log) => (
                        <motion.div
                            key={log.id}
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            className="mb-1 flex gap-3"
                        >
                            <span className="shrink-0 text-muted-foreground/50">[{log.timestamp}]</span>
                            <span
                                className={
                                    log.type === "error" ? "text-red-400" :
                                        log.type === "success" ? "text-green-400" :
                                            log.type === "warning" ? "text-yellow-400" : "text-gray-300"
                                }
                            >
                                {log.type === "info" && "> "}
                                {log.message}
                            </span>
                        </motion.div>
                    ))
                )}
                {/* Blinking cursor */}
                <motion.div
                    animate={{ opacity: [0, 1, 0] }}
                    transition={{ repeat: Infinity, duration: 0.8 }}
                    className="ml-1 inline-block h-4 w-2 bg-green-500/50 align-middle"
                />
            </div>
        </div>
    );
}
