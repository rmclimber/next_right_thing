"use client";

import { authenticatedRequest } from "./authenticated-api";

export type ContentType = "article" | "podcast_episode" | "video" | "research_article" | "book";

export type ContentItem = {
  id: string;
  content_type: ContentType;
  duration_minutes: number | null;
  content_source_id: string;
  external_id: string;
  title: string;
  url: string;
  summary: string | null;
  published_at: string | null;
  discovered_at: string;
  created_at: string;
  updated_at: string;
  status: "active" | "completed" | "archived";
  snoozed_until: string | null;
  completed_at: string | null;
  content_source?: {
    id: string;
    name: string;
    url: string;
  };
};

export type ContentItemFilter = "all" | "snoozed" | "completed" | "archived";

export type ContentItemListResponse = {
  content_items: ContentItem[];
  next_cursor: string | null;
};

export async function listContentItems({ filter = "all", limit = 50, cursor = null }: {
  filter?: ContentItemFilter; limit?: number; cursor?: string | null;
} = {}): Promise<ContentItemListResponse> {
  const query = new URLSearchParams({ filter, limit: String(limit) });
  if (cursor !== null) query.set("cursor", cursor);
  const response = await authenticatedRequest<ContentItemListResponse>(`/content-items?${query}`);
  if (!response || !Array.isArray(response.content_items) || response.content_items.length > limit ||
      !(response.next_cursor === null || (typeof response.next_cursor === "string" &&
        response.next_cursor.length > 0 && response.next_cursor.length <= 2048 &&
        /^[A-Za-z0-9_-]+$/.test(response.next_cursor)))) {
    throw new Error("Content Items pagination is unavailable. Please retry after the API has been updated.");
  }
  return response;
}
