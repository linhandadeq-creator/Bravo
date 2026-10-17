"use client";

export type FontSizePref = "sm" | "md" | "lg";
export type BackdropPref = "photo" | "gradient" | "solid" | "custom";

export interface UiPrefs {
  fontSize: FontSizePref;
  backdrop: BackdropPref;
  customImage: string | null;
  blur: number; // 0-100 (50 = standard glass)
}

export const DEFAULT_PREFS: UiPrefs = {
  fontSize: "md",
  backdrop: "photo",
  customImage: null,
  blur: 50,
};

const KEY = "bravo.ui";
export const UI_CHANGE_EVENT = "bravo-ui-change";

export const FONT_SIZE_PX: Record<FontSizePref, string> = {
  sm: "15px",
  md: "16px",
  lg: "17.5px",
};

function readPrefs(): UiPrefs {
  if (typeof window === "undefined") return { ...DEFAULT_PREFS };
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return { ...DEFAULT_PREFS };
    const parsed = JSON.parse(raw) as Partial<UiPrefs>;
    return {
      fontSize: parsed.fontSize === "sm" || parsed.fontSize === "lg" ? parsed.fontSize : "md",
      backdrop:
        parsed.backdrop === "gradient" ||
        parsed.backdrop === "solid" ||
        parsed.backdrop === "custom"
          ? parsed.backdrop
          : "photo",
      customImage: typeof parsed.customImage === "string" ? parsed.customImage : null,
      blur:
        typeof parsed.blur === "number" && Number.isFinite(parsed.blur)
          ? Math.max(0, Math.min(100, Math.round(parsed.blur)))
          : DEFAULT_PREFS.blur,
    };
  } catch {
    return { ...DEFAULT_PREFS };
  }
}

export function loadPrefs(): UiPrefs {
  return readPrefs();
}

export function savePrefs(prefs: UiPrefs): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(prefs));
  } catch {
    // localStorage full (e.g. oversized custom image) — ignore.
  }
  applyPrefs(prefs);
  window.dispatchEvent(new CustomEvent(UI_CHANGE_EVENT, { detail: prefs }));
}

export function resetPrefs(): UiPrefs {
  if (typeof window === "undefined") return { ...DEFAULT_PREFS };
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    // ignore
  }
  applyPrefs(DEFAULT_PREFS);
  window.dispatchEvent(new CustomEvent(UI_CHANGE_EVENT, { detail: DEFAULT_PREFS }));
  return { ...DEFAULT_PREFS };
}

function blurScale(blur: number): number {
  // 0 → no frost; 50 → standard (×1); 100 → double frost.
  return blur / 50;
}

export function applyPrefs(prefs: UiPrefs): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.style.fontSize = FONT_SIZE_PX[prefs.fontSize] ?? FONT_SIZE_PX.md;
  root.dataset.backdrop = prefs.backdrop;
  if (prefs.backdrop === "custom" && prefs.customImage) {
    root.style.setProperty("--custom-backdrop", `url("${prefs.customImage}")`);
  } else {
    root.style.removeProperty("--custom-backdrop");
  }
  const scale = blurScale(prefs.blur);
  root.style.setProperty("--blur-1", `${(18 * scale).toFixed(1)}px`);
  root.style.setProperty("--blur-2", `${(26 * scale).toFixed(1)}px`);
  root.style.setProperty("--blur-3", `${(40 * scale).toFixed(1)}px`);
}
