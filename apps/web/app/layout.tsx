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
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: "(function(){try{var theme=localStorage.getItem('nrt-theme');if(theme!=='light'&&theme!=='dark'){theme=window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'}document.documentElement.classList.toggle('dark',theme==='dark');document.documentElement.style.colorScheme=theme}catch(e){}})()",
          }}
        />
      </head>
      <body>
        <AmplifyProvider>{children}</AmplifyProvider>
      </body>
    </html>
  );
}
