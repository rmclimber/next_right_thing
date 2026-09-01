"use client";

import { authenticatedRequest } from "./authenticated-api";

export type ContentSourceType = "rss";

export type ContentSourceStatus = "active" | "paused" | "archived";

export type ContentSource = {
  id: string;
  name: string;
  source_type: ContentSourceType;
  url: string;
  status: ContentSourceStatus;
  created_at: string;
  updated_at: string;
};

export type ContentSourceListResponse = {
  content_sources: ContentSource[];
};

export type CreateContentSourceInput = {
  name: string;
  url: string;
};

export type UpdateContentSourceInput = {
  name?: string;
  url?: string;
  status?: ContentSourceStatus;
};

export async function listContentSources(): Promise<ContentSourceListResponse> {
  return authenticatedRequest<ContentSourceListResponse>("/content-sources");
}

export async function createContentSource(
  input: CreateContentSourceInput,
): Promise<ContentSource> {
  return authenticatedRequest<ContentSource>("/content-sources", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function updateContentSource(
  id: string,
  input: UpdateContentSourceInput,
): Promise<ContentSource> {
  return authenticatedRequest<ContentSource>(
    `/content-sources/${encodeURIComponent(id)}`,
    {
      method: "PATCH",
      body: JSON.stringify(input),
    },
  );
}
