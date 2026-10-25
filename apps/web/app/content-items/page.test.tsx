import { render, screen } from "@testing-library/react";
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

  it("renders item source and disposition filters without changing API order", async () => {
    listContentItems.mockResolvedValue({
      content_items: [
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

    await user.click(screen.getByRole("button", { name: "Snoozed" }));
    expect(screen.getByRole("link", { name: "Snoozed article" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Expired snooze" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Completed" }));
    expect(screen.getByRole("link", { name: "Completed article" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Archived" }));
    expect(screen.getByRole("link", { name: "Archived article" })).toBeInTheDocument();
  });

  it("shows an empty state when no Content Items are available", async () => {
    listContentItems.mockResolvedValue({ content_items: [] });
    render(<ContentItemsPage />);
    expect(await screen.findByText("No Content Items yet")).toBeInTheDocument();
  });

  it("shows an API error state when Content Items cannot be loaded", async () => {
    listContentItems.mockRejectedValue(new Error("offline"));
    render(<ContentItemsPage />);
    expect(await screen.findByText(/Content Items could not be loaded/)).toBeInTheDocument();
  });
});
