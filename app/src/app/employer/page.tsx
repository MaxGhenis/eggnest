import type { Metadata } from "next";

import EmployerPage from "./EmployerPage";

export const metadata: Metadata = {
  title: "EggNest Employer - Compensation scenario calculator",
  description:
    "Model compensation packages with loaded employer cost, market position, and employee after-tax value under explicit assumptions.",
};

export default function Page() {
  return <EmployerPage />;
}
