"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

export type Theme = "light" | "dark" | "system";

type ThemeValue = {
  theme: Theme;
  resolved: "light" | "dark";
  setTheme: (theme: Theme) => void;
};

const ThemeContext = createContext<ThemeValue>({
  theme: "system",
  resolved: "light",
  setTheme: () => undefined,
});

function systemPrefersDark() {
  return (
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
  );
}

function apply(theme: Theme) {
  const dark = theme === "dark" || (theme === "system" && systemPrefersDark());
  document.documentElement.classList.toggle("dark", dark);
  return dark ? "dark" : "light";
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>("system");
  const [resolved, setResolved] = useState<"light" | "dark">("light");

  useEffect(() => {
    const saved = (window.localStorage.getItem("bravo.theme") as Theme) || "system";
    setThemeState(saved);
    setResolved(apply(saved));
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      const current = (window.localStorage.getItem("bravo.theme") as Theme) || "system";
      if (current === "system") setResolved(apply("system"));
    };
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  const setTheme = useCallback((next: Theme) => {
    const root = document.documentElement;
    // enable a short, global crossfade for the light/dark switch
    root.classList.add("theme-transition");
    window.setTimeout(() => root.classList.remove("theme-transition"), 2200);
    setThemeState(next);
    window.localStorage.setItem("bravo.theme", next);
    setResolved(apply(next));
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, resolved, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
