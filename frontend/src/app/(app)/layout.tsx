"use client";

import type { ReactNode } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { ChevronDown, LogOut, Plus, Zap, Activity, TestTube2, Server, LayoutDashboard, Users, Link2 } from "lucide-react";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/auth";
import { cn } from "@/lib/utils";

const NAV = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Agents", href: "/agents", icon: Zap },
  { label: "Traces", href: "/traces", icon: Activity },
  { label: "Test Suites", href: "/test-suites", icon: TestTube2 },
  { label: "Ekipler", href: "/teams", icon: Users },
  { label: "Modeller", href: "/providers", icon: Server },
  { label: "Bağlantılar", href: "/connections", icon: Link2 },
];

function NavTabs() {
  const pathname = usePathname();
  return (
    <nav className="flex items-center gap-0.5">
      {NAV.map(({ label, href, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors",
              active
                ? "bg-zinc-800/80 text-zinc-100"
                : "text-zinc-500 hover:bg-zinc-900 hover:text-zinc-300",
            )}
          >
            <Icon size={13} className={active ? "text-indigo-400" : ""} />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

function OrgBadge({
  name,
  role,
}: {
  name: string;
  role: string | null;
}) {
  return (
    <div className="flex items-center gap-2 rounded-md border border-zinc-800 px-2.5 py-1.5 text-xs">
      <span className="font-medium text-zinc-200">{name}</span>
      {role && (
        <span className="text-zinc-600">{role}</span>
      )}
      <ChevronDown size={12} className="text-zinc-600" />
    </div>
  );
}

function TopBar() {
  const router = useRouter();
  const { user, logout } = useAuth();

  return (
    <header className="sticky top-0 z-30 flex h-12 items-center border-b border-zinc-900 bg-[#09090b]/90 px-4 backdrop-blur-sm">
      <div className="flex flex-1 items-center gap-3">
        <Link href="/">
          <Logo size={22} showWordmark={false} />
        </Link>

        {/* Divider */}
        <span className="h-4 w-px bg-zinc-800" />

        {user?.org_id && <NavTabs />}
      </div>

      {/* Right side */}
      <div className="flex items-center gap-2">
        {user?.org_name || user?.org_slug ? (
          <button
            onClick={() => router.push("/select-org")}
            className="flex items-center"
          >
            <OrgBadge
              name={user.org_name ?? user.org_slug ?? ""}
              role={user.role}
            />
          </button>
        ) : (
          <button
            onClick={() => router.push("/create-org")}
            className={cn(
              "flex items-center gap-1.5 rounded-md border border-dashed border-zinc-800",
              "px-2.5 py-1.5 text-xs text-zinc-500 transition-colors hover:border-zinc-700 hover:text-zinc-400",
            )}
          >
            <Plus size={12} />
            Create workspace
          </button>
        )}
        {user && (
          <span className="ml-1 hidden text-xs text-zinc-600 sm:inline">{user.email}</span>
        )}
        <Button
          variant="ghost"
          size="sm"
          onClick={logout}
          title="Sign out"
        >
          <LogOut size={14} />
        </Button>
      </div>
    </header>
  );
}

export default function AppLayout({ children }: { children: ReactNode }) {
  const { loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <span className="h-5 w-5 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="flex min-h-dvh flex-col">
      <TopBar />
      <main className="flex flex-1 flex-col">{children}</main>
    </div>
  );
}
