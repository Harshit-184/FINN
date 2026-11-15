"use client";
import { useEffect, useState } from "react";
import { load, type Source } from "./api";

export function useLoad<T>(path: string, file: string) {
  const [state, set] = useState<{ data?: T; source?: Source; error?: string }>({});
  useEffect(() => {
    let live = true;
    set({});
    load<T>(path, file).then((r) => live && set(r)).catch((e) => live && set({ error: String(e.message ?? e) }));
    return () => { live = false; };
  }, [path, file]);
  return state;
}
