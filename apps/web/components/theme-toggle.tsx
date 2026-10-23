"use client";

import { useEffect, useState } from "react";

const storageKey = "nrt-theme";

type Theme = "light" | "dark";

function resolvedTheme(): Theme {
  const saved = window.localStorage.getItem(storageKey);
  if (saved === "light" || saved === "dark") {
    return saved;
  }

  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle("dark", theme === "dark");
  document.documentElement.style.colorScheme = theme;
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme | null>(null);

  useEffect(() => {
    const initialTheme = resolvedTheme();
    applyTheme(initialTheme);
    setTheme(initialTheme);
  }, []);

  function toggleTheme() {
    const nextTheme = (theme ?? resolvedTheme()) === "dark" ? "light" : "dark";
    window.localStorage.setItem(storageKey, nextTheme);
    applyTheme(nextTheme);
    setTheme(nextTheme);
  }

  return (
    <button
      aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
      className="button theme-toggle"
      onClick={toggleTheme}
      type="button"
    >
      {theme === "dark" ? "Light" : "Dark"}
    </button>
  );
}
