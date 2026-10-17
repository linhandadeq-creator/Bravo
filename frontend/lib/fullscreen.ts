"use client";

const KEY = "bravo.fullscreen";

type FsElement = HTMLElement & {
  webkitRequestFullscreen?: () => Promise<void> | void;
};
type FsDocument = Document & {
  webkitFullscreenElement?: Element | null;
  webkitFullscreenEnabled?: boolean;
  webkitExitFullscreen?: () => Promise<void> | void;
};

export function fullscreenSupported(): boolean {
  if (typeof document === "undefined") return false;
  const doc = document as FsDocument;
  return Boolean(document.fullscreenEnabled ?? doc.webkitFullscreenEnabled);
}

export function isFullscreen(): boolean {
  if (typeof document === "undefined") return false;
  const doc = document as FsDocument;
  return Boolean(document.fullscreenElement ?? doc.webkitFullscreenElement);
}

export async function enterFullscreen(): Promise<boolean> {
  if (typeof document === "undefined") return false;
  const el = document.documentElement as FsElement;
  try {
    if (el.requestFullscreen) await el.requestFullscreen();
    else if (el.webkitRequestFullscreen) await el.webkitRequestFullscreen();
    else return false;
    return true;
  } catch {
    return false;
  }
}

export async function exitFullscreen(): Promise<void> {
  if (typeof document === "undefined") return;
  const doc = document as FsDocument;
  try {
    if (document.exitFullscreen) await document.exitFullscreen();
    else if (doc.webkitExitFullscreen) await doc.webkitExitFullscreen();
  } catch {
    // ignore
  }
}

export function getFullscreenPref(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

export function setFullscreenPref(on: boolean): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(KEY, on ? "1" : "0");
  } catch {
    // ignore
  }
}

export function subscribeFullscreenChange(cb: () => void): () => void {
  if (typeof document === "undefined") return () => undefined;
  const handler = () => cb();
  document.addEventListener("fullscreenchange", handler);
  document.addEventListener("webkitfullscreenchange", handler as EventListener);
  return () => {
    document.removeEventListener("fullscreenchange", handler);
    document.removeEventListener("webkitfullscreenchange", handler as EventListener);
  };
}
