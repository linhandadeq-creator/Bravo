"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useI18n } from "@/lib/i18n";
import { QUICK_NAV, isActive } from "@/lib/nav";
import { cn } from "@/lib/utils";

const ITEMS = QUICK_NAV;

const PAD = 6;

export function TabBar() {
  const pathname = usePathname();
  const { t } = useI18n();

  const index = Math.max(
    0,
    ITEMS.findIndex((item) => isActive(pathname, item.href))
  );

  return (
    <nav className="fixed inset-x-3 bottom-3 z-30 lg:hidden">
      <div
        className="lg-3 lg-edge-strong relative grid items-stretch rounded-[26px]"
        style={{ padding: PAD, gridTemplateColumns: `repeat(${ITEMS.length}, minmax(0, 1fr))` }}
      >
        {/* liquid droplet indicator */}
        <div
          aria-hidden
          className="tab-droplet"
          style={{
            left: PAD,
            width: `calc((100% - ${PAD * 2}px) / ${ITEMS.length})`,
            transform: `translateX(${index * 100}%)`,
          }}
        >
          <div key={index} className="tab-droplet-blob" />
        </div>

        {ITEMS.map((item) => {
          const active = isActive(pathname, item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "press relative z-10 flex flex-col items-center gap-0.5 rounded-2xl px-1 py-1.5 text-[10px] font-medium transition-colors duration-300",
                active ? "text-accent" : "text-muted-foreground"
              )}
            >
              <Icon className="h-[18px] w-[18px]" strokeWidth={1.75} />
              {t(item.key)}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
