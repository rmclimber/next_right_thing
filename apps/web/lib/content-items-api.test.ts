import { beforeEach, describe, expect, it, vi } from "vitest";
const { authenticatedRequest } = vi.hoisted(() => ({ authenticatedRequest: vi.fn() }));
vi.mock("./authenticated-api", () => ({ authenticatedRequest }));
import { listContentItems } from "./content-items-api";

describe("listContentItems", () => {
  beforeEach(() => authenticatedRequest.mockReset());

  it("requests bounded server-filtered pages and encodes the cursor", async () => {
    authenticatedRequest.mockResolvedValue({ content_items: [], next_cursor: null });
    await listContentItems();
    expect(authenticatedRequest).toHaveBeenLastCalledWith("/content-items?filter=all&limit=50");
    await listContentItems({ filter: "completed", limit: 1, cursor: "opaque-token" });
    expect(authenticatedRequest).toHaveBeenLastCalledWith("/content-items?filter=completed&limit=1&cursor=opaque-token");
  });

  it.each([undefined, "", 42, {}, "bad token", "x".repeat(2049)])("rejects invalid or missing next_cursor %s", async (next_cursor) => {
    authenticatedRequest.mockResolvedValue({ content_items: [], next_cursor });
    await expect(listContentItems()).rejects.toThrow(/pagination is unavailable/);
  });

  it("rejects an old unbounded response and accepts opaque tokens", async () => {
    authenticatedRequest.mockResolvedValueOnce({ content_items: Array(51).fill({}), next_cursor: null });
    await expect(listContentItems()).rejects.toThrow(/pagination is unavailable/);
    authenticatedRequest.mockResolvedValueOnce({ content_items: [], next_cursor: "valid_token-1" });
    await expect(listContentItems()).resolves.toEqual({ content_items: [], next_cursor: "valid_token-1" });
  });
});
