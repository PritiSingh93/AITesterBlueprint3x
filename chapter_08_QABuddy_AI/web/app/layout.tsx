import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "QABuddyAI",
  description:
    "Ask one question — get a cited answer grounded in our frameworks, test cases, JIRA history, PRDs, and Jenkins results.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
