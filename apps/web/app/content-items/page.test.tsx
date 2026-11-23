import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { authMocks, amplifyMocks } from "@/test/mocks";
import type { ContentItem } from "@/lib/content-items-api";

const { listContentItems } = vi.hoisted(() => ({ listContentItems: vi.fn() }));

vi.mock("@/lib/amplify-client", () => amplifyMocks);
vi.mock("@/lib/content-items-api", () => ({ listContentItems }));

import ContentItemsPage from "./page";

const source = { id: "source-1", name: "Professional Reading", url: "https://example.com/feed" };

function item(overrides: Partial<ContentItem>): ContentItem {
  return {
    id: "item-1",
    content_type: "article",
    duration_minutes: null,
    content_source_id: source.id,
    external_id: "external-1",
    title: "First article",
    url: "https://example.com/article",
    summary: "A concise summary.",
    published_at: "2026-10-10T00:00:00Z",
    discovered_at: "2026-10-11T00:00:00Z",
    created_at: "2026-10-11T00:00:00Z",
    updated_at: "2026-10-11T00:00:00Z",
    status: "active",
    snoozed_until: null,
    completed_at: null,
    content_source: source,
    ...overrides,
  };
}

describe("ContentItemsPage", () => {
  beforeEach(() => {
    listContentItems.mockReset();
    authMocks.getCurrentUser.mockReset();
    authMocks.getCurrentUser.mockResolvedValue({ username: "test-user" });
  });

  it("renders an article with nullable duration and no extra type badge", async () => {
    listContentItems.mockResolvedValue({ next_cursor: null, content_items: [item({ duration_minutes: null })] });
    render(<ContentItemsPage />);
    expect(await screen.findByRole("link", { name: "First article" })).toBeInTheDocument();
    expect(screen.getByText("A concise summary.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open article" })).toHaveAttribute("href", "https://example.com/article");
    expect(screen.queryByText("Article", { exact: true })).not.toBeInTheDocument();
  });

  it("renders item source and disposition filters without changing API order", async () => {
    listContentItems.mockResolvedValue({
      next_cursor: null, content_items: [
        item({ id: "active", title: "Newest active" }),
        item({ id: "snoozed", title: "Snoozed article", snoozed_until: "2099-01-01T00:00:00Z" }),
        item({ id: "expired", title: "Expired snooze", snoozed_until: "2000-01-01T00:00:00Z" }),
        item({ id: "completed", title: "Completed article", status: "completed", completed_at: "2026-10-12T00:00:00Z" }),
        item({ id: "archived", title: "Archived article", status: "archived" }),
      ],
    });
    const user = userEvent.setup();

    render(<ContentItemsPage />);

    await screen.findByRole("link", { name: "Newest active" });
    expect(screen.getAllByText("Professional Reading")).not.toHaveLength(0);
    expect(screen.getByText(/Snoozed until/)).toBeInTheDocument();
    expect(screen.getAllByText("Completed")).not.toHaveLength(0);
    expect(screen.getAllByText("Archived")).not.toHaveLength(0);
    expect(screen.getAllByRole("heading", { level: 3 }).map((heading) => heading.textContent)).toEqual([
      "Newest active", "Snoozed article", "Expired snooze", "Completed article", "Archived article",
    ]);

    listContentItems.mockResolvedValue({ next_cursor: null, content_items: [item({title: "Server snoozed match"})] });
    await user.click(screen.getByRole("button", { name: "Snoozed" }));
    expect(await screen.findByRole("link", { name: "Server snoozed match" })).toBeInTheDocument();
    expect(listContentItems).toHaveBeenLastCalledWith({ filter: "snoozed", limit: 50, cursor: null });
    expect(screen.queryByRole("link", { name: "Expired snooze" })).not.toBeInTheDocument();

  });

  it.each([42, null])("distinguishes podcast episodes with duration %s and an external listening link", async (duration_minutes) => {
    listContentItems.mockResolvedValue({ next_cursor: null, content_items: [item({
      content_type: "podcast_episode", duration_minutes, title: "Professional podcast",
      url: "https://example.com/audio.mp3", summary: "Episode <strong>description</strong>.",
    })] });
    render(<ContentItemsPage />);
    expect(await screen.findByText("Podcast episode")).toBeInTheDocument();
    expect(screen.getByText(duration_minutes === null ? "Duration unknown" : "42 min")).toBeInTheDocument();
    expect(screen.getByText("Episode description .")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Listen externally" })).toHaveAttribute("href", "https://example.com/audio.mp3");
    expect(screen.getByRole("link", { name: "Listen externally" })).toHaveAttribute("target", "_blank");
    expect(screen.queryByRole("link", { name: "Open article" })).not.toBeInTheDocument();
  });

  it("shows an empty state when no Content Items are available", async () => {
    listContentItems.mockResolvedValue({ next_cursor: null, content_items: [] });
    render(<ContentItemsPage />);
    expect(await screen.findByText("No Content Items yet")).toBeInTheDocument();
  });

  it("shows an API error state when Content Items cannot be loaded", async () => {
    listContentItems.mockRejectedValue(new Error("offline"));
    render(<ContentItemsPage />);
    expect(await screen.findByText(/Content Items could not be loaded/)).toBeInTheDocument();
  });
  it("navigates pages, retries a failed Next, and preserves history", async () => {
    const user = userEvent.setup();
    listContentItems.mockResolvedValueOnce({ next_cursor: "page-two", content_items: [item({})] })
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({ next_cursor: null, content_items: [item({ title: "Second page" })] })
      .mockResolvedValueOnce({ next_cursor: "page-two", content_items: [item({})] });
    render(<ContentItemsPage />);
    await screen.findByText("Showing 1 items · Page 1");
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Next" }));
    await screen.findByText(/Content Items could not be loaded/);
    expect(screen.queryByText(/Page 2/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    await screen.findByText("Showing 1 items · Page 2");
    expect(listContentItems).toHaveBeenLastCalledWith({filter: "all", limit: 50, cursor: "page-two"});
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Previous" }));
    await screen.findByText("Showing 1 items · Page 1");
    expect(listContentItems).toHaveBeenLastCalledWith({filter: "all", limit: 50, cursor: null});
  });

  it("resets page two on filter change and shows a filtered empty state", async () => {
    const user = userEvent.setup();
    listContentItems.mockResolvedValueOnce({ next_cursor: "two", content_items: [item({})] })
      .mockResolvedValueOnce({ next_cursor: null, content_items: [item({})] })
      .mockResolvedValueOnce({ next_cursor: null, content_items: [] });
    render(<ContentItemsPage />);
    await screen.findByText(/Page 1/);
    await user.click(screen.getByRole("button", { name: "Next" }));
    await screen.findByText(/Page 2/);
    await user.click(screen.getByRole("button", { name: "Completed" }));
    await screen.findByText("No completed items yet.");
    expect(screen.getByText("Showing 0 items · Page 1")).toBeInTheDocument();
    expect(listContentItems).toHaveBeenLastCalledWith({filter: "completed", limit: 50, cursor: null});
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    expect(screen.queryByText("No Content Items yet")).not.toBeInTheDocument();
  });

  it("ignores a stale response and disables duplicate navigation during loading", async () => {
    const user = userEvent.setup();
    let resolveOld!: (value: unknown) => void;
    listContentItems.mockReturnValueOnce(new Promise((resolve) => { resolveOld = resolve; }))
      .mockResolvedValueOnce({ next_cursor: null, content_items: [item({title: "Current filter"})] });
    render(<ContentItemsPage />);
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Archived" }));
    await screen.findByRole("link", {name: "Current filter"});
    await act(async () => { resolveOld({ next_cursor: "stale", content_items: [item({title: "Stale page"})] }); });
    expect(screen.queryByRole("link", {name: "Stale page"})).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

});
