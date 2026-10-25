import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ThemeToggle } from "./theme-toggle";

describe("ThemeToggle", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.className = "";
    document.documentElement.style.colorScheme = "";
  });

  it("uses and persists an explicit preference over the system preference", async () => {
    window.localStorage.setItem("nrt-theme", "dark");
    window.matchMedia = vi.fn().mockReturnValue({ matches: false });
    const user = userEvent.setup();

    render(<ThemeToggle />);

    await waitFor(() => expect(document.documentElement).toHaveClass("dark"));
    expect(screen.getByRole("button", { name: "Switch to light theme" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Switch to light theme" }));
    expect(document.documentElement).not.toHaveClass("dark");
    expect(document.documentElement.style.colorScheme).toBe("light");
    expect(window.localStorage.getItem("nrt-theme")).toBe("light");
  });

  it("falls back to the system preference when no preference is saved", async () => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: true });

    render(<ThemeToggle />);

    await waitFor(() => expect(document.documentElement).toHaveClass("dark"));
    expect(window.localStorage.getItem("nrt-theme")).toBeNull();
  });
});
