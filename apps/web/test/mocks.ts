import { vi } from "vitest";

export const navigationMocks = {
  pathname: "/recommendations",
  replace: vi.fn(),
};

export const authMocks = {
  getCurrentUser: vi.fn(),
  signOut: vi.fn(),
};

export const amplifyMocks = {
  configureAmplify: vi.fn(),
};
