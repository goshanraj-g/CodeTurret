"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
    ShieldAlert,
    LayoutDashboard,
    Terminal,
    Settings,
    Menu,
    X
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const items = [
    { icon: LayoutDashboard, label: "Dashboard", href: "/" },
    { icon: ShieldAlert, label: "Scanner", href: "/scan" },
    { icon: Terminal, label: "Findings", href: "/findings" },
    { icon: Settings, label: "Config", href: "/config" },
];

export function CircularNav() {
    const [isOpen, setIsOpen] = useState(false);
    const pathname = usePathname();

    const toggle = () => setIsOpen(!isOpen);

    return (
        <div className="fixed bottom-8 right-8 z-50 flex flex-col items-center justify-center">
            <AnimatePresence>
                {isOpen && (
                    <div className="absolute bottom-16 flex flex-col items-center gap-4">
                        {items.map((item, index) => (
                            <motion.div
                                key={item.href}
                                initial={{ opacity: 0, y: 20, scale: 0.8 }}
                                animate={{ opacity: 1, y: 0, scale: 1 }}
                                exit={{ opacity: 0, y: 10, scale: 0.8 }}
                                transition={{ delay: index * 0.05 }}
                            >
                                <Link
                                    href={item.href}
                                    className={cn(
                                        "group flex items-center gap-3 rounded-full border border-border bg-black/50 p-3 backdrop-blur-md transition-all hover:bg-white/10 hover:border-white/20",
                                        pathname === item.href && "border-green-500/50 bg-green-500/10 text-green-400"
                                    )}
                                >
                                    <item.icon className="h-5 w-5" />
                                    <span className="sr-only group-hover:not-sr-only group-hover:block whitespace-nowrap text-sm font-medium">
                                        {item.label}
                                    </span>
                                </Link>
                            </motion.div>
                        ))}
                    </div>
                )}
            </AnimatePresence>

            <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
                onClick={toggle}
                className={cn(
                    "flex h-14 w-14 items-center justify-center rounded-full border border-white/10 bg-black/80 shadow-[0_0_20px_rgba(0,0,0,0.5)] backdrop-blur-xl transition-colors hover:border-white/30",
                    isOpen ? "text-red-400 border-red-500/30 bg-red-500/10" : "text-white"
                )}
            >
                <AnimatePresence mode="wait">
                    {isOpen ? (
                        <motion.div
                            key="close"
                            initial={{ rotate: -90, opacity: 0 }}
                            animate={{ rotate: 0, opacity: 1 }}
                            exit={{ rotate: 90, opacity: 0 }}
                        >
                            <X className="h-6 w-6" />
                        </motion.div>
                    ) : (
                        <motion.div
                            key="menu"
                            initial={{ rotate: 90, opacity: 0 }}
                            animate={{ rotate: 0, opacity: 1 }}
                            exit={{ rotate: -90, opacity: 0 }}
                        >
                            <Menu className="h-6 w-6" />
                        </motion.div>
                    )}
                </AnimatePresence>
            </motion.button>
        </div>
    );
}
