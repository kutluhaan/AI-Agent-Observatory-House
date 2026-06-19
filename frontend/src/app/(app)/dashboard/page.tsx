"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Activity, Zap, TestTube2 } from "lucide-react";
import { useAuth } from "@/contexts/auth";

const QUICK_LINKS = [
  {
    icon: Zap,
    label: "Agents",
    description: "Build and run AI agents",
    href: "/agents",
    enabled: true,
  },
  {
    icon: Activity,
    label: "Traces",
    description: "Observe agent execution",
    href: "/traces",
    enabled: true,
  },
  {
    icon: TestTube2,
    label: "Test Suites",
    description: "Automated agent testing",
    href: "/test-suites",
    enabled: true,
  },
];

export default function DashboardPage() {
  const { user } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (user && !user.org_id) {
      router.replace("/create-org");
    }
  }, [user, router]);

  if (!user?.org_id) return null;

  const firstName = user.full_name?.split(" ")[0] ?? "there";

  return (
    <div className="mx-auto w-full max-w-2xl px-6 py-12">
      <div className="mb-10">
        <h1 className="text-2xl font-semibold text-zinc-100">
          Good morning, {firstName}
        </h1>
        <p className="mt-1.5 text-sm text-zinc-500">
          {user.org_name ?? user.org_slug} workspace
        </p>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {QUICK_LINKS.map(({ icon: Icon, label, description, href, enabled }) => {
          const card = (
            <div
              className={
                "group relative flex h-full flex-col gap-2 rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-5 transition-colors " +
                (enabled ? "hover:border-zinc-700 hover:bg-zinc-900/70" : "opacity-50")
              }
            >
              <Icon size={18} className="text-indigo-400" />
              <div>
                <p className="text-sm font-medium text-zinc-200">{label}</p>
                <p className="text-xs text-zinc-500">{description}</p>
              </div>
              {!enabled && (
                <span className="absolute right-3 top-3 rounded-full bg-zinc-800 px-2 py-0.5 text-[10px] text-zinc-500">
                  soon
                </span>
              )}
            </div>
          );
          return enabled ? (
            <Link key={label} href={href}>
              {card}
            </Link>
          ) : (
            <div key={label}>{card}</div>
          );
        })}
      </div>

      <div className="mt-8 rounded-xl border border-zinc-800/50 bg-zinc-900/20 p-5">
        <p className="text-xs text-zinc-600 leading-relaxed">
          <span className="font-medium text-zinc-500">Observatory</span> is an
          AI agent observability and testing platform. Build agents, monitor
          traces, and run automated test suites — all in one place.
        </p>
      </div>
    </div>
  );
}
