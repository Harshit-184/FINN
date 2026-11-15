import type { Metadata, Viewport } from "next";
import { Suspense } from "react";
import Tabs from "@/components/Tabs";
import "./globals.css";

export const metadata: Metadata = {
  title: "FINN",
  description: "What changed in your portfolio today, and what deserves a second look.",
  manifest: "/manifest.webmanifest",
};
export const viewport: Viewport = { themeColor: "#0e1620", width: "device-width", initialScale: 1, viewportFit: "cover" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <main className="mx-auto max-w-xl px-3 pb-24 pt-4"><Suspense>{children}</Suspense></main>
        <Suspense><Tabs /></Suspense>
      </body>
    </html>
  );
}
