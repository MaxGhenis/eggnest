import type { Metadata, Viewport } from "next";
import { DM_Sans, Fraunces } from "next/font/google";
import "./globals.css";

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-body",
  display: "swap",
});

export const metadata: Metadata = {
  title: "EggNest - Financial planning simulator",
  description:
    "Monte Carlo financial simulation with real tax calculations. See your actual probability of success, not just guesses.",
  icons: {
    icon: "/favicon.svg",
  },
};

export const viewport: Viewport = {
  themeColor: "#d97706",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={`${fraunces.variable} ${dmSans.variable} min-h-screen bg-gradient-page text-[var(--color-text)] font-[var(--font-body)]`}>
        {children}
      </body>
    </html>
  );
}
