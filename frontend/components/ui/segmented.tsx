"use client";

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function GlassSegmented<T extends string>({
  options,
  value,
  onChange,
  size = "md",
  className,
}: {
  options: { value: T; label: ReactNode }[];
  value: T;
  onChange: (value: T) => void;
  size?: "sm" | "md";
  className?: string;
}) {
  const count = options.length;
  const index = Math.max(
    0,
    options.findIndex((option) => option.value === value)
  );
  const pad = size === "sm" ? 2 : 3;

  return (
    <div className={cn("glass-seg", className)} style={{ padding: pad }}>
      <div
        aria-hidden
        className="glass-seg-thumb"
        style={{
          left: pad,
          width: `calc((100% - ${pad * 2}px) / ${count})`,
          transform: `translateX(${index * 100}%)`,
        }}
      />
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          data-active={option.value === value}
          onClick={() => onChange(option.value)}
          className={cn(
            "glass-seg-item press flex items-center justify-center gap-1.5 whitespace-nowrap",
            size === "sm" ? "px-3 py-1 text-[12px]" : "px-4 py-1.5 text-[13px]"
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
