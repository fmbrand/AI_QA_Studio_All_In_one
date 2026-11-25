import type { Metadata } from "next";

import { Providers } from "@/components/providers/providers";
import { themeInitScript } from "@/components/providers/theme-provider";

import "./globals.css";

export const metadata: Metadata = {
  title: { default: "AI QA Studio", template: "%s · AI QA Studio" },
  description: "Project-aware QA engineering workspace",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
