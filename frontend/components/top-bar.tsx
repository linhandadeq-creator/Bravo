"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, Moon, Sun, X } from "lucide-react";

import { useTheme } from "@/components/theme-provider";
import { GlassSegmented } from "@/components/ui/segmented";
import { useI18n } from "@/lib/i18n";
import { NAV_ITEMS, isActive } from "@/lib/nav";
import { cn } from "@/lib/utils";

const SECTION_BY_PREFIX: [string, string][] = [
  ["/generate", "page.generate.title"],
  ["/projects", "page.projects.title"],
  ["/variants", "page.variants.title"],
  ["/hla", "page.hla.title"],
  ["/expression", "page.expression.title"],
  ["/neoantigens", "page.neoantigens.title"],
  ["/simulation", "page.simulation.title"],
  ["/validation", "page.validation.title"],
  ["/reports", "page.reports.title"],
  ["/settings", "page.settings.title"],
];

export function TopBar() {
  const pathname = usePathname();
  const { t } = useI18n();
  const { resolved, setTheme } = useTheme();
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  const sectionKey =
    SECTION_BY_PREFIX.find(([prefix]) =>
      prefix === "/" ? pathname === "/" : pathname.startsWith(prefix)
    )?.[1] ?? "page.dashboard.title";

  return (
    <header className="sticky top-3 z-20 mb-4">
      <div
        className={cn(
          "lg-2 lg-edge flex h-12 items-center gap-3 rounded-full px-3 pl-4 transition-all duration-300",
          scrolled && "lg-3 lg-edge-strong"
        )}
      >
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          aria-label="Menu"
          aria-expanded={open}
          className="press lg-1 lg-edge flex h-8 w-8 items-center justify-center rounded-full text-muted-foreground hover:text-foreground lg:hidden"
        >
          {open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
        </button>
        <span className="text-[15px] font-semibold tracking-tight">
          {t(sectionKey)}
        </span>
        <div className="flex-1" />
        <GlassSegmented
          size="sm"
          value={resolved === "dark" ? "dark" : "light"}
          onChange={setTheme}
          options={[
            {
              value: "light",
              label: <Sun className="h-3.5 w-3.5" strokeWidth={1.75} />,
            },
            {
              value: "dark",
              label: <Moon className="h-3.5 w-3.5" strokeWidth={1.75} />,
            },
          ]}
        />
      </div>

      {open ? (
        <div className="lg-3 lg-edge-strong mt-2 rounded-[26px] p-2 lg:hidden">
          <nav className="grid grid-cols-2 gap-1">
            {NAV_ITEMS.map((item) => {
              const active = isActive(pathname, item.href);
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setOpen(false)}
                  className={cn(
                    "press flex items-center gap-2 rounded-2xl px-3 py-2 text-[13px] font-medium",
                    active
                      ? "lg-2 lg-edge text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <Icon
                    className={cn("h-4 w-4", active && "text-accent")}
                    strokeWidth={1.75}
                  />
                  {t(item.key)}
                </Link>
              );
            })}
          </nav>
        </div>
      ) : null}
    </header>
  );
}
