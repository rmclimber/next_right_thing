"use client";

import { authenticatedRequest } from "./authenticated-api";

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

export async function listGoals(): Promise<GoalListResponse> {
  return authenticatedRequest<GoalListResponse>("/goals");
}

export async function createGoal(input: CreateGoalInput): Promise<Goal> {
  return authenticatedRequest<Goal>("/goals", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function updateGoal(id: string, input: UpdateGoalInput): Promise<Goal> {
  return authenticatedRequest<Goal>(`/goals/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}
