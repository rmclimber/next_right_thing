import type { Metadata } from "next";
import { PropsWithChildren } from "react";

import { AmplifyProvider } from "./amplify-provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "Next Right Thing",
  description: "Authentication validation for Next Right Thing.",
};

export default function RootLayout({ children }: PropsWithChildren) {
  return (
    <html lang="en">
      <body>
        <AmplifyProvider>{children}</AmplifyProvider>
      </body>
    </html>
  );
}
