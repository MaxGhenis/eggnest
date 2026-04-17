"use client";

import { useEffect, useMemo, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import {
  optimizeRothConversions,
  type RothOptimizationResult,
} from "../../../lib/api";
import {
  buildRothReportHref,
  decodeRothReportRequestPayload,
} from "../../../lib/rothReportLink";
import { RothOptimizationReportView } from "../../../components/simulator/ComparisonPanel";

interface RothReportPageClientProps {
  encodedReport: string | null;
}

export default function RothReportPageClient({
  encodedReport,
}: RothReportPageClientProps) {
  const [result, setResult] = useState<RothOptimizationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const requestPayload = useMemo(
    () => (encodedReport ? decodeRothReportRequestPayload(encodedReport) : null),
    [encodedReport],
  );
  const requestError = useMemo(() => {
    if (!encodedReport) {
      return "Missing report payload.";
    }
    if (!requestPayload) {
      return "This Roth report link is invalid or expired.";
    }
    return null;
  }, [encodedReport, requestPayload]);

  useEffect(() => {
    if (!requestPayload || requestError) {
      return;
    }

    let cancelled = false;
    void optimizeRothConversions(requestPayload.baseInput, requestPayload.options)
      .then((optimization) => {
        if (!cancelled) {
          setResult(optimization);
        }
      })
      .catch((requestFailure) => {
        if (!cancelled) {
          const message =
            requestFailure instanceof Error
              ? requestFailure.message
              : "Unable to load this Roth report.";
          setError(message);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [requestError, requestPayload]);

  const reportLink = useMemo(() => {
    if (!requestPayload || typeof window === "undefined") {
      return null;
    }
    return buildRothReportHref(requestPayload, window.location.origin);
  }, [requestPayload]);

  const isLoading = !requestError && !error && !result;

  return (
    <div className="min-h-screen">
      <header className="header-glass sticky top-0 z-50 border-b border-[var(--color-border-light)]">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3 md:px-6">
          <Link href="/" className="flex items-center gap-2.5 transition-opacity hover:opacity-80">
            <Image
              src="/logo.svg"
              alt="EggNest"
              width={140}
              height={28}
              className="block"
              priority
            />
          </Link>
          <span className="hidden text-xs font-semibold uppercase tracking-widest text-[var(--color-text-muted)] sm:block">
            Roth report
          </span>
          <Link
            href="/simulator"
            className="rounded-full border border-[var(--color-primary-200)] bg-[var(--color-primary-50)] px-4 py-1.5 text-xs font-semibold text-[var(--color-primary)] transition-all hover:bg-[var(--color-primary)] hover:text-white hover:border-[var(--color-primary)]"
          >
            Back to simulator
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-10 md:px-6 md:py-12">
        <div className="mx-auto max-w-4xl space-y-6">
          <section className="rounded-[var(--radius-lg)] border border-[var(--color-border-light)] bg-white p-6 shadow-[var(--shadow-sm)]">
            <div className="text-[0.65rem] font-semibold uppercase tracking-wider text-[var(--color-text-light)]">
              Roth optimization report
            </div>
            <h1 className="mt-2 text-3xl font-semibold text-[var(--color-text)]">
              Saved Roth conversion scenario comparison
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-relaxed text-[var(--color-text-muted)]">
              This page reruns the same Roth optimization search from the shared
              scenario payload and renders the calculator artifact directly. It
              reports modeled outcomes under the encoded assumptions; it does
              not provide advice.
            </p>
          </section>

          {isLoading && (
            <section className="section-card flex items-center gap-3 text-sm text-[var(--color-text-muted)]">
              <div className="h-5 w-5 animate-spin-slow rounded-full border-2 border-[var(--color-primary-200)] border-t-[var(--color-primary)]" />
              Rebuilding Roth report from the shared scenario...
            </section>
          )}

          {(requestError || error) && !isLoading && (
            <section className="section-card space-y-3">
              <h2 className="text-lg font-semibold text-[var(--color-text)]">Unable to load this report</h2>
              <p className="text-sm text-[var(--color-text-muted)]">{requestError ?? error}</p>
              <Link
                href="/simulator"
                className="inline-flex rounded-[var(--radius-md)] border border-[var(--color-border)] bg-white px-4 py-2.5 text-sm font-medium text-[var(--color-text-muted)] transition-all hover:bg-[var(--color-gray-50)] hover:text-[var(--color-text)]"
              >
                Open simulator
              </Link>
            </section>
          )}

          {result && !isLoading && (
            <section className="section-card">
              <RothOptimizationReportView
                rothOptimizationResult={result}
                reportLink={reportLink}
              />
            </section>
          )}
        </div>
      </main>
    </div>
  );
}
