"use client";

import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from "react";

import { cn } from "@/lib/utils";
import { playSound } from "@/lib/sound";

type Tone = "error" | "success" | "info";
type Toast = { id: number; message: string; tone: Tone };

const ToastContext = createContext<{ push: (message: string, tone?: Tone) => void }>({
  push: () => undefined,
});

const TONE_CLASS: Record<Tone, string> = {
  error: "border-destructive/30 bg-destructive/10 text-destructive",
  success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  info: "text-foreground",
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);

  const push = useCallback((message: string, tone: Tone = "info") => {
    const id = Date.now() + Math.random();
    playSound(tone === "success" ? "success" : tone === "error" ? "error" : "chime");
    setItems((prev) => [...prev, { id, message, tone }]);
    window.setTimeout(
      () => setItems((prev) => prev.filter((item) => item.id !== id)),
      6000
    );
  }, []);

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div className="pointer-events-none fixed inset-x-3 bottom-24 z-50 flex flex-col items-end gap-2 lg:bottom-4 lg:left-auto lg:right-4 lg:w-[min(92vw,360px)]">
        {items.map((item) => (
          <div
            key={item.id}
            role="status"
            className={cn(
              "animate-pop lg-3 lg-edge-strong pointer-events-auto w-full rounded-2xl px-4 py-3 text-[13px] shadow-lg",
              TONE_CLASS[item.tone]
            )}
          >
            {item.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
