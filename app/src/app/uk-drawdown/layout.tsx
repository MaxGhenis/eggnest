import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "What you keep when you draw from your savings - EggNest",
  description:
    "See what you keep from each pound you draw from a pension pot, ISA or other savings in the 2026/27 tax year, after income tax, National Insurance and any change in Pension Credit.",
  robots: { index: false },
};

export default function UKDrawdownLayout({ children }: { children: React.ReactNode }) {
  return children;
}
