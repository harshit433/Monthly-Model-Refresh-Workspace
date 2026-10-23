import { useCallback, useEffect, useState } from "react";

function isDark(): boolean {
  const t = document.documentElement.getAttribute("data-theme");
  if (t) return t === "dark";
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function useTheme() {
  const [dark, setDark] = useState(isDark());

  useEffect(() => {
    try {
      const s = localStorage.getItem("rs-theme");
      if (s) document.documentElement.setAttribute("data-theme", s);
    } catch { /* ignore */ }
    setDark(isDark());
  }, []);

  const toggle = useCallback(() => {
    const next = isDark() ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try { localStorage.setItem("rs-theme", next); } catch { /* ignore */ }
    setDark(next === "dark");
  }, []);

  return { dark, toggle };
}
