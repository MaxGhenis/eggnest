import { Suspense } from "react";
import RothReportPageClient from "./roth-report-page-client";

interface RothReportPageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export default async function RothReportPage({
  searchParams,
}: RothReportPageProps) {
  const resolvedSearchParams = await searchParams;
  const encodedReport = resolvedSearchParams.report;
  const reportValue = Array.isArray(encodedReport)
    ? encodedReport[0] ?? null
    : encodedReport ?? null;

  return (
    <Suspense fallback={null}>
      <RothReportPageClient
        key={reportValue ?? "missing-report"}
        encodedReport={reportValue}
      />
    </Suspense>
  );
}
