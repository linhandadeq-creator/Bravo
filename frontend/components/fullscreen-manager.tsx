"use client";

import { useEffect } from "react";

import {
  enterFullscreen,
  getFullscreenPref,
  isFullscreen,
  setFullscreenPref,
  subscribeFullscreenChange,
} from "@/lib/fullscreen";

/**
 * Applies the saved fullscreen preference. Browsers require a user gesture to
 * enter fullscreen, so if the preference is "on" we enter on the first
 * pointer/keyboard interaction after load. Exiting (e.g. via Esc) updates the
 * saved preference.
 */
export function FullscreenManager() {
  useEffect(() => {
    const sync = () => setFullscreenPref(isFullscreen());
    const unsubscribe = subscribeFullscreenChange(sync);

    let armed = getFullscreenPref() && !isFullscreen();
    const onGesture = () => {
      if (!armed) return;
      armed = false;
      window.removeEventListener("pointerdown", onGesture);
      window.removeEventListener("keydown", onGesture);
      void enterFullscreen();
    };
    if (armed) {
      window.addEventListener("pointerdown", onGesture);
      window.addEventListener("keydown", onGesture);
    }

    return () => {
      unsubscribe();
      window.removeEventListener("pointerdown", onGesture);
      window.removeEventListener("keydown", onGesture);
    };
  }, []);

  return null;
}
