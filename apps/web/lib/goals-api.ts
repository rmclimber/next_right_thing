"use client";

import { fetchAuthSession } from "aws-amplify/auth";

import { configureAmplify } from "./amplify-client";
import { getPublicConfig } from "./config";

export type GoalStatus = "active" | "paused" | "completed" | "archived";

export type Goal = {
  id: string;
  title: string;
  description: string | null;
  status: GoalStatus;
  target_date: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
};

export type GoalListResponse = {
  goals: Goal[];
};

export type CreateGoalInput = {
  title: string;
  description?: string | null;
  target_date?: string | null;
};

export type UpdateGoalInput = {
  title?: string;
  description?: string | null;
  target_date?: string | null;
  status?: GoalStatus;
};

async function getAccessToken(): Promise<string> {
  configureAmplify();

  const session = await fetchAuthSession();
  const accessToken = session.tokens?.accessToken?.toString();

  if (!accessToken) {
    throw new Error("No access token was found for the current session.");
  }

  return accessToken;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const accessToken = await getAccessToken();
  const { apiBaseUrl } = getPublicConfig();
  const headers = new Headers(init.headers);

  headers.set("Authorization", `Bearer ${accessToken}`);

  if (init.body) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}.`);
  }

  return (await response.json()) as T;
}

export async function listGoals(): Promise<GoalListResponse> {
  return request<GoalListResponse>("/goals");
}

export async function createGoal(input: CreateGoalInput): Promise<Goal> {
  return request<Goal>("/goals", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function updateGoal(id: string, input: UpdateGoalInput): Promise<Goal> {
  return request<Goal>(`/goals/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}
