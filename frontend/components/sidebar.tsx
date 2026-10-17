"use client";

import { useLayoutEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useI18n } from "@/lib/i18n";
import { NAV_ITEMS, isActive } from "@/lib/nav";
import { playSound } from "@/lib/sound";
import { cn } from "@/lib/utils";

export function Sidebar() {
  const pathname = usePathname();
  const { t } = useI18n();
  const itemRefs = useRef<(HTMLAnchorElement | null)[]>([]);
  const [drop, setDrop] = useState({ top: 0, height: 0, ready: false });

  const index = Math.max(
    0,
    NAV_ITEMS.findIndex((item) =>
      item.href === "/" ? pathname === "/" : pathname.startsWith(item.href)
    )
  );

  useLayoutEffect(() => {
    const measure = () => {
      const el = itemRefs.current[index];
      if (el) {
        setDrop({ top: el.offsetTop, height: el.offsetHeight, ready: true });
      }
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [index, pathname]);

  return (
    <aside className="fixed inset-y-3 left-3 z-30 hidden w-[224px] flex-col lg:flex">
      <div className="lg-3 lg-edge flex h-full flex-col overflow-hidden rounded-[28px]">
        <nav className="relative flex-1 space-y-0.5 overflow-y-auto px-2.5 pb-3 pt-4">
          <div
            aria-hidden
            className="sidebar-droplet"
            style={{
              opacity: drop.ready ? 1 : 0,
              height: drop.height,
              transform: `translateY(${drop.top}px)`,
            }}
          >
            <div key={index} className="sidebar-droplet-blob" />
          </div>

          {NAV_ITEMS.map((item, i) => {
            const active = isActive(pathname, item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                ref={(el) => {
                  itemRefs.current[i] = el;
                }}
                href={item.href}
                onClick={() => {
                  if (!active) playSound("nav");
                }}
                className={cn(
                  "press relative z-10 flex items-center gap-2.5 rounded-2xl px-3 py-2 text-[13px] font-medium transition-colors duration-300",
                  active
                    ? "text-foreground"
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

        <div className="px-5 py-4 text-[11px] leading-relaxed text-muted-foreground">
          {t("nav.footer")}
        </div>
      </div>
    </aside>
  );
}
