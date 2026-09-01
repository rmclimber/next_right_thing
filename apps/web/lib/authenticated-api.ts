"use client";

import { fetchAuthSession } from "aws-amplify/auth";

import { configureAmplify } from "./amplify-client";
import { getPublicConfig } from "./config";

export class ApiError extends Error {
  status: number;

  constructor(status: number) {
    super(`Request failed with status ${status}.`);
    this.name = "ApiError";
    this.status = status;
  }
}

async function getAccessToken(): Promise<string> {
  configureAmplify();

  const session = await fetchAuthSession();
  const accessToken = session.tokens?.accessToken?.toString();

  if (!accessToken) {
    throw new Error("No access token was found for the current session.");
  }

  return accessToken;
}

export async function authenticatedRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
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
    throw new ApiError(response.status);
  }

  return (await response.json()) as T;
}
