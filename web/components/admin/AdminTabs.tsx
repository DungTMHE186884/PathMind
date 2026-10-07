"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ArrowLeft, BarChart3, Boxes, Receipt, Users } from "lucide-react";
import { useTranslation } from "react-i18next";

const TABS = [
  { href: "/admin/plans", label: "Plans & Models", icon: Boxes },
  { href: "/admin/users", label: "Users", icon: Users },
  { href: "/admin/payments", label: "Payments", icon: Receipt },
  { href: "/admin/insights", label: "Insights", icon: BarChart3 },
] as const;

/** Shared header navigation for the /admin pages. */
export default function AdminTabs({
  pendingPayments,
}: {
  pendingPayments?: number;
}) {
  const { t } = useTranslation();
  const pathname = usePathname() ?? "";
  return (
    <div className="mb-6 flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
      <Link
        href="/chat"
        className="inline-flex items-center gap-1.5 text-xs text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)]"
      >
        <ArrowLeft size={14} />
        {t("Back to learning space")}
      </Link>
      <nav className="flex flex-wrap items-center gap-1.5 rounded-xl border border-[var(--border)] bg-muted/50 p-1">
        {TABS.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs transition-all ${
                active
                  ? "bg-primary font-semibold text-primary-foreground shadow-sm"
                  : "font-medium text-[var(--muted-foreground)] hover:bg-[var(--card)] hover:text-[var(--foreground)]"
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {t(label)}
              {href === "/admin/payments" && !!pendingPayments && (
                <span className="rounded-full bg-warning px-1.5 text-[10px] font-bold text-[var(--background)]">
                  {pendingPayments}
                </span>
              )}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
