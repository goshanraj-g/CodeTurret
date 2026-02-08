"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { ArrowRight, ShieldCheck, ShieldAlert, Activity, GitBranch } from "lucide-react";

const stats = [
  { label: "Active Repos", value: "12", icon: GitBranch, color: "text-blue-400" },
  { label: "Total Scans", value: "148", icon: Activity, color: "text-purple-400" },
  { label: "Critical Issues", value: "3", icon: ShieldAlert, color: "text-red-400" },
  { label: "Resolved", value: "96%", icon: ShieldCheck, color: "text-green-400" },
];

export default function Home() {
  return (
    <div className="flex flex-col gap-8">
      {/* Hero Section */}
      <section className="flex flex-col gap-4 py-10">
        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-5xl font-bold tracking-tight text-white md:text-7xl"
        >
          Repo<span className="text-green-500">Sentinel</span>
        </motion.h1>
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="max-w-xl text-lg text-muted-foreground"
        >
          Next-generation AI security auditor. Autonomous vulnerability detection and remediation for your codebase.
        </motion.p>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="flex gap-4 pt-4"
        >
          <Link
            href="/scan"
            className="group flex items-center gap-2 rounded-full bg-white px-6 py-3 font-medium text-black transition-transform hover:scale-105"
          >
            Start New Scan
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
          </Link>
          <Link
            href="/findings"
            className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-6 py-3 font-medium text-white transition-colors hover:bg-white/10"
          >
            View Reports
          </Link>
        </motion.div>
      </section>

      {/* Stats Grid */}
      <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.3 + i * 0.1 }}
            className="flex flex-col gap-2 rounded-2xl border border-white/5 bg-white/5 p-6 backdrop-blur-sm transition-colors hover:bg-white/10"
          >
            <div className="flex items-center justify-between">
              <stat.icon className={`h-6 w-6 ${stat.color}`} />
              <span className={`text-xs font-mono uppercase ${stat.color} opacity-80`}>
                Signal
              </span>
            </div>
            <div className="mt-2">
              <div className="text-3xl font-bold text-white">{stat.value}</div>
              <div className="text-sm text-muted-foreground">{stat.label}</div>
            </div>
          </motion.div>
        ))}
      </section>

      {/* Recent Activity Mockup */}
      <section className="rounded-3xl border border-white/10 bg-black/40 p-8 backdrop-blur-md">
        <h2 className="mb-6 text-xl font-semibold">System Activity</h2>
        <div className="space-y-4">
          {[1, 2, 3].map((_, i) => (
            <div key={i} className="flex items-center justify-between border-b border-white/5 pb-4 last:border-0 last:pb-0">
              <div className="flex items-center gap-4">
                <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
                <div>
                  <div className="font-mono text-sm text-white">goshanraj-g/RepoSentinel</div>
                  <div className="text-xs text-muted-foreground">Scan #8F2A • 2 mins ago</div>
                </div>
              </div>
              <div className="font-mono text-xs text-green-400">COMPLETED</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
