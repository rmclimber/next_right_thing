import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { authMocks, amplifyMocks } from "@/test/mocks";
import type { ContentSource } from "@/lib/content-sources-api";

const { createContentSource, listContentSources, updateContentSource } = vi.hoisted(() => ({
  createContentSource: vi.fn(),
  listContentSources: vi.fn(),
  updateContentSource: vi.fn(),
}));

vi.mock("@/lib/amplify-client", () => amplifyMocks);
vi.mock("@/lib/content-sources-api", () => ({
  listContentSources,
  createContentSource,
  updateContentSource,
}));

import ContentSourcesPage from "./page";

function source(overrides: Partial<ContentSource>): ContentSource {
  return {
    id: "source-1",
    name: "Professional Feed",
    source_type: "rss",
    url: "https://example.com/feed",
    status: "active",
    created_at: "2026-10-10T00:00:00Z",
    updated_at: "2026-10-10T00:00:00Z",
    last_fetch_status: null,
    last_fetch_attempt_at: null,
    last_fetch_success_at: null,
    last_fetch_error: null,
    ...overrides,
  };
}

describe("ContentSourcesPage", () => {
  beforeEach(() => {
    authMocks.getCurrentUser.mockResolvedValue({ username: "test-user" });
  });

  it("renders lifecycle status separately from source fetch health", async () => {
    listContentSources.mockResolvedValue({
      content_sources: [
        source({ name: "Healthy paused", status: "paused", last_fetch_status: "healthy", last_fetch_success_at: "2026-10-11T00:00:00Z" }),
        source({ id: "never", name: "New feed" }),
        source({ id: "invalid", name: "Broken feed", last_fetch_status: "invalid_feed", last_fetch_attempt_at: "2026-10-11T00:00:00Z", last_fetch_error: "Bad XML" }),
        source({ id: "error", name: "Unavailable feed", last_fetch_status: "fetch_error", last_fetch_attempt_at: "2026-10-11T00:00:00Z" }),
      ],
    });

    render(<ContentSourcesPage />);

    const healthySource = (await screen.findByRole("heading", { name: "Healthy paused" })).closest("li");
    const newSource = screen.getByRole("heading", { name: "New feed" }).closest("li");
    const invalidSource = screen.getByRole("heading", { name: "Broken feed" }).closest("li");
    const errorSource = screen.getByRole("heading", { name: "Unavailable feed" }).closest("li");

    expect(healthySource).not.toBeNull();
    expect(newSource).not.toBeNull();
    expect(invalidSource).not.toBeNull();
    expect(errorSource).not.toBeNull();
    expect(within(healthySource!).getAllByText("Paused")).not.toHaveLength(0);
    expect(within(healthySource!).getByText("Healthy")).toBeInTheDocument();
    expect(within(newSource!).getByText("Never checked")).toBeInTheDocument();
    expect(within(invalidSource!).getByText("Invalid feed")).toBeInTheDocument();
    expect(within(errorSource!).getByText("Fetch error")).toBeInTheDocument();
  });

  it("shows an API error state when sources cannot be loaded", async () => {
    listContentSources.mockRejectedValueOnce(new Error("offline"));

    render(<ContentSourcesPage />);

    expect(await screen.findByText(/Content Sources could not be loaded/)).toBeInTheDocument();
  });
});
