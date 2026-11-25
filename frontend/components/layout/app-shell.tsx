"use client";

import { Check, ChevronsUpDown, FlaskConical, LogOut, Menu, Monitor, Moon, Sun, X } from "lucide-react";
import Link from "next/link";
import { useParams, usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/components/providers/auth-provider";
import { useTheme, type Theme } from "@/components/providers/theme-provider";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useMe } from "@/lib/queries";
import { cn, ROLE_LABELS } from "@/lib/utils";

import { NAV_ITEMS } from "./nav";

function ProjectSwitcher() {
  const { data } = useMe();
  const params = useParams<{ projectId?: string }>();
  const router = useRouter();
  const memberships = data?.memberships ?? [];
  const current = memberships.find((m) => m.project_id === params.projectId);
  const active = memberships.filter((m) => m.project_status === "active");
  const archived = memberships.filter((m) => m.project_status === "archived");

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          className="flex w-full items-center justify-between gap-2 rounded-md border bg-background px-3 py-2 text-left text-sm hover:bg-accent"
          aria-label="Switch project"
        >
          <span className="min-w-0">
            <span className="block text-xs text-muted-foreground">Project</span>
            <span className="block truncate font-medium">{current?.project_name ?? "Select a project"}</span>
          </span>
          <ChevronsUpDown className="size-4 shrink-0 text-muted-foreground" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-64">
        {active.length === 0 && archived.length === 0 && <DropdownMenuLabel>No projects yet</DropdownMenuLabel>}
        {active.map((m) => (
          <DropdownMenuItem key={m.project_id} onSelect={() => router.push(`/projects/${m.project_id}`)}>
            <Check className={cn(m.project_id === params.projectId ? "opacity-100" : "opacity-0")} />
            <span className="truncate">{m.project_name}</span>
            <span className="ml-auto text-xs text-muted-foreground">{ROLE_LABELS[m.role]}</span>
          </DropdownMenuItem>
        ))}
        {archived.length > 0 && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuLabel>Archived</DropdownMenuLabel>
            {archived.map((m) => (
              <DropdownMenuItem key={m.project_id} onSelect={() => router.push(`/projects/${m.project_id}`)}>
                <Check className={cn(m.project_id === params.projectId ? "opacity-100" : "opacity-0")} />
                <span className="truncate text-muted-foreground">{m.project_name}</span>
              </DropdownMenuItem>
            ))}
          </>
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => router.push("/projects")}>All projects</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

const THEMES: { value: Theme; label: string; icon: typeof Sun }[] = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
];

function UserMenu() {
  const { user, logout } = useAuth();
  const { theme, setTheme } = useTheme();
  const router = useRouter();
  if (!user) return null;
  const initials = user.name
    .split(/\s+/)
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm hover:bg-accent">
          <span className="flex size-8 items-center justify-center rounded-full bg-primary/15 text-xs font-semibold text-primary">
            {initials}
          </span>
          <span className="min-w-0">
            <span className="block truncate font-medium">{user.name}</span>
            <span className="block truncate text-xs text-muted-foreground">{user.email}</span>
          </span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" side="top" className="w-56">
        <DropdownMenuLabel>Theme</DropdownMenuLabel>
        {THEMES.map(({ value, label, icon: Icon }) => (
          <DropdownMenuItem key={value} onSelect={() => setTheme(value)}>
            <Icon />
            {label}
            {theme === value && <Check className="ml-auto" />}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onSelect={async () => {
            await logout();
            router.replace("/login");
          }}
        >
          <LogOut />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <div className="flex h-full flex-col gap-4 p-3">
      <Link href="/dashboard" className="flex items-center gap-2 px-2 pt-1" onClick={onNavigate}>
        <span className="flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <FlaskConical className="size-4" />
        </span>
        <span className="font-semibold">AI QA Studio</span>
      </Link>
      <ProjectSwitcher />
      <nav aria-label="Main" className="flex-1 overflow-y-auto">
        <ul className="grid gap-0.5">
          {NAV_ITEMS.map(({ href, label, icon: Icon, phase }) => {
            const active = pathname === href || pathname.startsWith(`${href}/`);
            return (
              <li key={href}>
                <Link
                  href={href}
                  onClick={onNavigate}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors",
                    active ? "bg-primary/10 font-medium text-primary" : "text-foreground/80 hover:bg-accent",
                  )}
                >
                  <Icon className="size-4 shrink-0" />
                  <span className="flex-1 truncate">{label}</span>
                  {phase && <span className="text-[10px] uppercase text-muted-foreground">Phase {phase}</span>}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
      <UserMenu />
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 border-r bg-sidebar md:block">
        <SidebarContent />
      </aside>
      {open && (
        <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 border-r bg-sidebar">
            <Button
              variant="ghost"
              size="icon"
              className="absolute right-2 top-2"
              onClick={() => setOpen(false)}
              aria-label="Close navigation"
            >
              <X />
            </Button>
            <SidebarContent onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b bg-background/95 px-4 md:hidden">
          <Button variant="ghost" size="icon" onClick={() => setOpen(true)} aria-label="Open navigation">
            <Menu />
          </Button>
          <span className="font-semibold">AI QA Studio</span>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 md:px-8 md:py-8">{children}</main>
      </div>
    </div>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <div className="mt-1 text-sm text-muted-foreground">{description}</div>}
      </div>
      {actions && <div className="flex shrink-0 gap-2">{actions}</div>}
    </div>
  );
}
