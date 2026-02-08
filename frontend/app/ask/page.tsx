"use client";

import React, { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MessageSquare, Send, Bot, User, Sparkles, Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { cn } from "@/lib/utils";

interface Message {
    id: string;
    role: "user" | "assistant";
    content: string;
    timestamp: string;
}

export default function AskPage() {
    const [repoName, setRepoName] = useState("");
    const [question, setQuestion] = useState("");
    const [messages, setMessages] = useState<Message[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [activeRepo, setActiveRepo] = useState<string | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    const handleAsk = async () => {
        const repo = activeRepo || repoName;
        if (!repo || !question.trim()) return;

        if (!activeRepo) setActiveRepo(repo);

        const userMsg: Message = {
            id: crypto.randomUUID(),
            role: "user",
            content: question,
            timestamp: new Date().toLocaleTimeString(),
        };
        setMessages((prev) => [...prev, userMsg]);
        setQuestion("");
        setIsLoading(true);

        try {
            const res = await fetch("http://localhost:8000/ask", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ repo_name: repo, question: userMsg.content }),
            });

            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: "Request failed" }));
                throw new Error(err.detail || "Request failed");
            }

            const data = await res.json();

            const assistantMsg: Message = {
                id: crypto.randomUUID(),
                role: "assistant",
                content: data.answer,
                timestamp: new Date().toLocaleTimeString(),
            };
            setMessages((prev) => [...prev, assistantMsg]);
        } catch (err) {
            const errorMsg: Message = {
                id: crypto.randomUUID(),
                role: "assistant",
                content: `Error: ${err instanceof Error ? err.message : String(err)}`,
                timestamp: new Date().toLocaleTimeString(),
            };
            setMessages((prev) => [...prev, errorMsg]);
        } finally {
            setIsLoading(false);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleAsk();
        }
    };

    const resetChat = () => {
        setMessages([]);
        setActiveRepo(null);
        setRepoName("");
        setQuestion("");
    };

    return (
        <div className="mx-auto max-w-4xl space-y-8">
            <div className="space-y-2">
                <h1 className="text-3xl font-bold tracking-tight text-white">Repo Intelligence</h1>
                <p className="text-muted-foreground">Ask questions about your scan results using natural language.</p>
            </div>

            <div className="grid gap-8 lg:grid-cols-[1fr_300px]">
                {/* Chat Area */}
                <div className="flex flex-col">
                    {/* Messages Container */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="flex-1 rounded-2xl border border-white/10 bg-black/40 backdrop-blur-md overflow-hidden"
                    >
                        {/* Chat Header */}
                        <div className="flex items-center justify-between border-b border-white/10 px-6 py-4">
                            <div className="flex items-center gap-3">
                                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-500/10 text-purple-400">
                                    <MessageSquare className="h-4 w-4" />
                                </div>
                                <div>
                                    <span className="text-sm font-medium text-white">
                                        {activeRepo ? activeRepo : "New Conversation"}
                                    </span>
                                    <div className="flex items-center gap-1.5">
                                        <div className={cn(
                                            "h-1.5 w-1.5 rounded-full",
                                            activeRepo ? "bg-green-500 animate-pulse" : "bg-white/20"
                                        )} />
                                        <span className="text-xs text-muted-foreground font-mono">
                                            {activeRepo ? "CONNECTED" : "WAITING"}
                                        </span>
                                    </div>
                                </div>
                            </div>
                            {messages.length > 0 && (
                                <button
                                    onClick={resetChat}
                                    className="text-xs text-muted-foreground hover:text-white transition-colors"
                                >
                                    Clear
                                </button>
                            )}
                        </div>

                        {/* Messages */}
                        <div className="h-[450px] overflow-y-auto p-6 space-y-4 scrollbar-thin">
                            {messages.length === 0 && (
                                <div className="flex h-full flex-col items-center justify-center text-center">
                                    <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-white/10 bg-white/5 mb-4">
                                        <Bot className="h-8 w-8 text-purple-400" />
                                    </div>
                                    <p className="text-sm text-muted-foreground max-w-xs">
                                        Select a repository and ask about vulnerabilities, severity trends, or remediation advice.
                                    </p>
                                </div>
                            )}

                            <AnimatePresence initial={false}>
                                {messages.map((msg) => (
                                    <motion.div
                                        key={msg.id}
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        className={cn(
                                            "flex gap-3",
                                            msg.role === "user" ? "justify-end" : "justify-start"
                                        )}
                                    >
                                        {msg.role === "assistant" && (
                                            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-purple-500/10 text-purple-400">
                                                <Bot className="h-4 w-4" />
                                            </div>
                                        )}
                                        <div className={cn(
                                            "max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed",
                                            msg.role === "user"
                                                ? "bg-white/10 text-white"
                                                : "border border-white/10 bg-white/5 text-gray-200"
                                        )}>
                                            {msg.role === "user" ? (
                                                <p className="whitespace-pre-wrap">{msg.content}</p>
                                            ) : (
                                                <div className="prose prose-invert prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5 prose-headings:text-white prose-headings:mt-3 prose-headings:mb-1 prose-strong:text-white prose-code:text-purple-300 prose-code:bg-white/10 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:before:content-none prose-code:after:content-none">
                                                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                                                </div>
                                            )}
                                            <span className="mt-1.5 block text-[10px] text-muted-foreground font-mono">
                                                {msg.timestamp}
                                            </span>
                                        </div>
                                        {msg.role === "user" && (
                                            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/10 text-white">
                                                <User className="h-4 w-4" />
                                            </div>
                                        )}
                                    </motion.div>
                                ))}
                            </AnimatePresence>

                            {isLoading && (
                                <motion.div
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    className="flex gap-3"
                                >
                                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-purple-500/10 text-purple-400">
                                        <Bot className="h-4 w-4" />
                                    </div>
                                    <div className="flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
                                        <Loader2 className="h-4 w-4 animate-spin text-purple-400" />
                                        <span className="text-sm text-muted-foreground">Analyzing scan data...</span>
                                    </div>
                                </motion.div>
                            )}

                            <div ref={messagesEndRef} />
                        </div>

                        {/* Input Area */}
                        <div className="border-t border-white/10 p-4">
                            {!activeRepo && (
                                <div className="mb-3">
                                    <input
                                        type="text"
                                        placeholder="Repository name (e.g. CodeBouncer)"
                                        value={repoName}
                                        onChange={(e) => setRepoName(e.target.value)}
                                        className="w-full rounded-xl border border-white/10 bg-black/60 px-4 py-3 font-mono text-sm text-white placeholder-white/30 focus:border-green-500/50 focus:outline-none focus:ring-2 focus:ring-green-500/20 transition-all"
                                    />
                                </div>
                            )}
                            <div className="flex gap-3">
                                <input
                                    type="text"
                                    placeholder={activeRepo ? "Ask a follow-up question..." : "What vulnerabilities were found?"}
                                    value={question}
                                    onChange={(e) => setQuestion(e.target.value)}
                                    onKeyDown={handleKeyDown}
                                    disabled={isLoading}
                                    className="flex-1 rounded-xl border border-white/10 bg-black/60 px-4 py-3 text-sm text-white placeholder-white/30 focus:border-purple-500/50 focus:outline-none focus:ring-2 focus:ring-purple-500/20 transition-all disabled:opacity-50"
                                />
                                <button
                                    onClick={handleAsk}
                                    disabled={isLoading || !question.trim() || (!activeRepo && !repoName)}
                                    className={cn(
                                        "flex h-[46px] w-[46px] shrink-0 items-center justify-center rounded-xl transition-all",
                                        isLoading || !question.trim() || (!activeRepo && !repoName)
                                            ? "bg-white/5 text-white/20 cursor-not-allowed"
                                            : "bg-purple-500/20 text-purple-400 hover:bg-purple-500/30 hover:scale-105 active:scale-95"
                                    )}
                                >
                                    <Send className="h-4 w-4" />
                                </button>
                            </div>
                        </div>
                    </motion.div>
                </div>

                {/* Right Sidebar */}
                <div className="space-y-6">
                    {/* AI Info Card */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.1 }}
                        className="rounded-2xl border border-purple-500/20 bg-gradient-to-br from-purple-500/10 to-blue-500/10 p-6"
                    >
                        <div className="flex items-center gap-2 mb-3 text-purple-300">
                            <Sparkles className="h-4 w-4" />
                            <span className="text-sm font-semibold">Cortex AI</span>
                        </div>
                        <p className="text-sm text-purple-200/70 leading-relaxed">
                            Powered by <b>Snowflake Cortex</b>. Queries your scan findings and provides contextual security analysis.
                        </p>
                    </motion.div>

                    {/* Example Questions */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.2 }}
                        className="rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-sm"
                    >
                        <span className="text-sm font-medium text-white mb-4 block">Try asking</span>
                        <div className="space-y-2">
                            {[
                                "What are the critical vulnerabilities?",
                                "Which files are most at risk?",
                                "Are there any SQL injection issues?",
                                "Summarize the last scan results",
                            ].map((q, i) => (
                                <button
                                    key={i}
                                    onClick={() => {
                                        setQuestion(q);
                                    }}
                                    className="w-full rounded-lg border border-white/5 bg-white/5 px-3 py-2 text-left text-xs text-muted-foreground transition-all hover:bg-white/10 hover:text-white hover:border-white/10"
                                >
                                    {q}
                                </button>
                            ))}
                        </div>
                    </motion.div>
                </div>
            </div>
        </div>
    );
}
