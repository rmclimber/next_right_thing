"use client";

import { PropsWithChildren } from "react";
import { useEffect } from "react";

import { configureAmplify } from "@/lib/amplify-client";

export function AmplifyProvider({ children }: PropsWithChildren) {
  useEffect(() => {
    configureAmplify();
  }, []);

  return children;
}
