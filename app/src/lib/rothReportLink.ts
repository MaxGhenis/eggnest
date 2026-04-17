import type {
  RothConversionPolicy,
  RothOptimizationResult,
  SimulationInput,
} from "./api";

export interface RothReportRequestPayload {
  version: 1;
  baseInput: SimulationInput;
  options: {
    annualConversionAmounts?: number[];
    conversionPolicies?: RothConversionPolicy[];
    candidateStartAges?: number[];
    windowLengths?: number[];
  };
}

function encodeBase64Url(value: string): string {
  if (typeof Buffer !== "undefined") {
    return Buffer.from(value, "utf8")
      .toString("base64")
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/g, "");
  }

  const bytes = new TextEncoder().encode(value);
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function decodeBase64Url(value: string): string {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padding = normalized.length % 4 === 0 ? "" : "=".repeat(4 - (normalized.length % 4));

  if (typeof Buffer !== "undefined") {
    return Buffer.from(`${normalized}${padding}`, "base64").toString("utf8");
  }

  const binary = atob(`${normalized}${padding}`);
  const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

function uniqueSortedNumbers(values: Array<number | null | undefined>): number[] {
  return [...new Set(values.filter((value): value is number => typeof value === "number"))].sort((a, b) => a - b);
}

function uniquePolicies(values: Array<RothConversionPolicy | undefined>): RothConversionPolicy[] {
  return [...new Set(values.filter((value): value is RothConversionPolicy => Boolean(value)))];
}

function isFixedAmountScenario(
  item: Pick<RothOptimizationResult["results"][number], "conversion_policy" | "annual_conversion_amount">,
): boolean {
  return item.conversion_policy === "fixed_amount" || item.annual_conversion_amount !== null;
}

export function buildRothReportRequestPayload(
  baseInput: SimulationInput,
  result: RothOptimizationResult,
): RothReportRequestPayload {
  const fixedAmounts = uniqueSortedNumbers(
    result.results
      .filter((item) => isFixedAmountScenario(item))
      .map((item) => item.annual_conversion_amount),
  );
  const conversionPolicies = uniquePolicies(
    result.results
      .map((item) => item.conversion_policy)
      .filter((policy) => policy !== "fixed_amount"),
  );

  return {
    version: 1,
    baseInput: {
      ...baseInput,
      ...(result.metadata?.random_seed !== undefined
        ? { random_seed: result.metadata?.random_seed ?? null }
        : {}),
    },
    options: {
      ...(fixedAmounts.length > 0 ? { annualConversionAmounts: fixedAmounts } : {}),
      conversionPolicies,
      candidateStartAges: result.candidate_start_ages,
      windowLengths: result.window_lengths,
    },
  };
}

export function encodeRothReportRequestPayload(
  payload: RothReportRequestPayload,
): string {
  return encodeBase64Url(JSON.stringify(payload));
}

export function decodeRothReportRequestPayload(
  encodedPayload: string,
): RothReportRequestPayload | null {
  try {
    const parsed = JSON.parse(decodeBase64Url(encodedPayload)) as RothReportRequestPayload;
    if (parsed.version !== 1 || !parsed.baseInput) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function buildRothReportHref(
  payload: RothReportRequestPayload,
  origin?: string,
): string {
  const encodedPayload = encodeRothReportRequestPayload(payload);
  const path = `/simulator/roth-report?report=${encodedPayload}`;
  return origin ? `${origin}${path}` : path;
}
