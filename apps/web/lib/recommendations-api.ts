"use client";

import { authenticatedRequest } from "./authenticated-api";

export type RecommendationContentItem = {
  id: string;
  title: string;
  url: string;
  summary: string | null;
  published_at: string | null;
  discovered_at: string;
};

export type Recommendation = {
  recommendation_event_id: string;
  action_type: "read_content_item";
  content_item: RecommendationContentItem;
  estimated_duration_minutes: number;
  reason: string;
};

export type NextRecommendationResponse = {
  recommendation: Recommendation | null;
};

export async function getNextRecommendation(
  availableMinutes: number,
): Promise<NextRecommendationResponse> {
  const query = new URLSearchParams({ available_minutes: String(availableMinutes) });

  return authenticatedRequest<NextRecommendationResponse>(
    `/recommendations/next?${query.toString()}`,
  );
}
