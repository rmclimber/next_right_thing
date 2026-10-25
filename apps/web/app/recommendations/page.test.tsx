import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { authMocks, amplifyMocks } from "@/test/mocks";
import type { Recommendation } from "@/lib/recommendations-api";

const { applyContentItemAction, getNextRecommendation } = vi.hoisted(() => ({
  applyContentItemAction: vi.fn(),
  getNextRecommendation: vi.fn(),
}));

vi.mock("@/lib/amplify-client", () => amplifyMocks);
vi.mock("@/lib/recommendations-api", () => ({ getNextRecommendation, applyContentItemAction }));

import RecommendationsPage from "./page";

const recommendation: Recommendation = {
  recommendation_event_id: "event-1", action_type: "read_content_item",
  content_item: { id: "item-1", title: "A useful article", url: "https://example.com/article", summary: "A useful <strong>summary</strong>.", published_at: "2026-10-10T00:00:00Z", discovered_at: "2026-10-11T00:00:00Z", content_source: { id: "source-1", name: "Professional Reading", url: "https://example.com/feed" } },
  estimated_duration_minutes: 15, reason: "It fits your available time.",
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => { resolve = resolvePromise; });
  return { promise, resolve };
}

describe("RecommendationsPage", () => {
  beforeEach(() => { authMocks.getCurrentUser.mockResolvedValue({ username: "test-user" }); });

  it("requests a recommendation and renders its user-visible details", async () => {
    getNextRecommendation.mockResolvedValueOnce({ recommendation });
    const user = userEvent.setup();
    render(<RecommendationsPage />);
    expect(await screen.findByRole("button", { name: "5 min" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "15 min" }));
    await user.click(screen.getByRole("button", { name: "Find my next thing" }));
    expect(getNextRecommendation).toHaveBeenCalledWith(15);
    expect(await screen.findByRole("heading", { name: "A useful article" })).toBeInTheDocument();
    expect(screen.getByText("Professional Reading")).toBeInTheDocument();
    expect(screen.getByText("About 15 min")).toBeInTheDocument();
    expect(screen.getByText("It fits your available time.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open" })).toHaveAttribute("href", "https://example.com/article");
  });

  it("shows normal empty and error states", async () => {
    getNextRecommendation.mockResolvedValueOnce({ recommendation: null });
    const user = userEvent.setup();
    render(<RecommendationsPage />);
    await user.click(await screen.findByRole("button", { name: "Find my next thing" }));
    expect(await screen.findByText("No recommendation is available right now.")).toBeInTheDocument();
    getNextRecommendation.mockRejectedValueOnce(new Error("offline"));
    await user.click(screen.getByRole("button", { name: "Find my next thing" }));
    expect(await screen.findByText(/A recommendation could not be loaded/)).toBeInTheDocument();
  });

  it.each(["snooze", "complete", "archive"] as const)("applies %s and only then loads the next recommendation", async (action) => {
    const actionRequest = deferred<{ content_item_state: unknown }>();
    getNextRecommendation.mockResolvedValueOnce({ recommendation }).mockResolvedValueOnce({ recommendation: null });
    applyContentItemAction.mockReturnValueOnce(actionRequest.promise);
    const user = userEvent.setup();
    render(<RecommendationsPage />);
    await user.click(await screen.findByRole("button", { name: "Find my next thing" }));
    await screen.findByRole("heading", { name: "A useful article" });
    await user.click(screen.getByRole("button", { name: new RegExp(`^${action}$`, "i") }));
    expect(applyContentItemAction).toHaveBeenCalledWith("item-1", action, "event-1");
    expect(screen.getByRole("button", { name: "Saving..." })).toBeDisabled();
    for (const visibleAction of ["Snooze", "Archive"]) {
      expect(screen.getByRole("button", { name: visibleAction })).toBeDisabled();
    }
    actionRequest.resolve({ content_item_state: {} });
    await waitFor(() => expect(getNextRecommendation).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("No recommendation is available right now.")).toBeInTheDocument();
  });

  it("keeps the current recommendation and does not advance when an action fails", async () => {
    getNextRecommendation.mockResolvedValueOnce({ recommendation });
    applyContentItemAction.mockRejectedValueOnce(new Error("offline"));
    const user = userEvent.setup();
    render(<RecommendationsPage />);
    await user.click(await screen.findByRole("button", { name: "Find my next thing" }));
    await user.click(await screen.findByRole("button", { name: "Archive" }));
    expect(await screen.findByText(/That action could not be saved/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "A useful article" })).toBeInTheDocument();
    expect(getNextRecommendation).toHaveBeenCalledTimes(1);
  });

  it("does not mark an item complete when its content link is opened", async () => {
    getNextRecommendation.mockResolvedValueOnce({ recommendation });
    const user = userEvent.setup();
    render(<RecommendationsPage />);
    await user.click(await screen.findByRole("button", { name: "Find my next thing" }));
    await user.click(await screen.findByRole("link", { name: "Open" }));
    expect(applyContentItemAction).not.toHaveBeenCalled();
  });

  it("prevents duplicate concurrent recommendation requests", async () => {
    const request = deferred<{ recommendation: Recommendation | null }>();
    getNextRecommendation.mockReturnValueOnce(request.promise);
    const user = userEvent.setup();
    render(<RecommendationsPage />);
    await user.dblClick(await screen.findByRole("button", { name: "Find my next thing" }));
    expect(getNextRecommendation).toHaveBeenCalledTimes(1);
    request.resolve({ recommendation: null });
    expect(await screen.findByText("No recommendation is available right now.")).toBeInTheDocument();
  });
});
