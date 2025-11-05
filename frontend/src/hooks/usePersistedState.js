import { useEffect, useState } from "react";

const storage = typeof window !== "undefined" ? window.sessionStorage : null;

function readItem(key, ttlMs) {
  if (!storage) return null;
  try {
    const raw = storage.getItem(key);
    if (!raw) return null;
    const obj = JSON.parse(raw);
    if (ttlMs && obj?.t && Date.now() - obj.t > ttlMs) {
      storage.removeItem(key);
      return null;
    }
    return obj?.v ?? null;
  } catch {
    return null;
  }
}

function writeItem(key, value) {
  if (!storage) return;
  try {
    storage.setItem(key, JSON.stringify({ v: value, t: Date.now() }));
  } catch {}
}

export function clearPersistedState(key) {
  if (!storage) return;
  try {
    storage.removeItem(key);
  } catch {}
}

export default function usePersistedState(
  key,
  initialValue,
  { ttlMs = 30 * 60_000 } = {}
) {
  const [value, setValue] = useState(() => {
    const v = readItem(key, ttlMs);
    return v !== null ? v : initialValue;
  });

  useEffect(() => {
    writeItem(key, value);
  }, [key, value]);

  return [value, setValue];
}
