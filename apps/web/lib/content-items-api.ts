"use client";

import { authenticatedRequest } from "./authenticated-api";

export type ContentItem = {
  id: string;
  content_source_id: string;
  external_id: string;
  title: string;
  url: string;
  summary: string | null;
  published_at: string | null;
  discovered_at: string;
  created_at: string;
  updated_at: string;
};

export type ContentItemListResponse = {
  content_items: ContentItem[];
};

export async function listContentItems(): Promise<ContentItemListResponse> {
  return authenticatedRequest<ContentItemListResponse>("/content-items");
}
