import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "What you keep when you draw from your savings in 2026 - Eggnest",
  description:
    "See what you keep from each dollar you draw from a traditional IRA or 401(k), a Roth IRA, investments or cash in 2026, after federal and state income tax and any benefits you lose, and what it adds to Medicare premiums in 2028.",
  robots: { index: false },
};

export default function USDrawdownLayout({ children }: { children: React.ReactNode }) {
  return children;
}
