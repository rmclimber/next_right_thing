import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { navigationMocks } from "@/test/mocks";
import { AuthenticatedNavigation } from "./authenticated-navigation";

describe("AuthenticatedNavigation", () => {
  beforeEach(() => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: false });
  });

  it("keeps all destinations visible and marks only the current route active", async () => {
    navigationMocks.pathname = "/content-items";
    const onSignOut = vi.fn();
    const user = userEvent.setup();

    render(<AuthenticatedNavigation onSignOut={onSignOut} />);

    expect(screen.getByRole("link", { name: "Next Right Thing" })).toHaveAttribute("href", "/recommendations");
    expect(screen.getByRole("link", { name: "Goals" })).toHaveAttribute("href", "/dashboard");
    expect(screen.getByRole("link", { name: "Content Sources" })).toHaveAttribute("href", "/content-sources");
    expect(screen.getByRole("link", { name: "Content Items" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Next Right Thing" })).not.toHaveAttribute("aria-current");

    await user.click(screen.getByRole("button", { name: "Sign Out" }));
    expect(onSignOut).toHaveBeenCalledOnce();
  });
});
