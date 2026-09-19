import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  runSimulationWithProgress,
  TimeoutError,
  type SimulationEvent,
  type SimulationInput,
  type SimulationJobStatus,
  type SimulationResult,
} from './api';

const input: SimulationInput = {
  initial_capital: 500000,
  annual_spending: 40000,
  home_value: 0,
  current_age: 55,
  max_age: 95,
  gender: 'male',
  state: 'CA',
  filing_status: 'single',
  has_spouse: false,
  has_annuity: false,
  n_simulations: 2000,
  include_mortality: true,
  expected_return: 0.07,
  return_volatility: 0.16,
  dividend_yield: 0.02,
  stock_allocation: 0.8,
  social_security_monthly: 0,
  social_security_start_age: 67,
  pension_annual: 0,
  employment_income: 0,
  employment_growth_rate: 0.03,
  retirement_age: 65,
};

const result: SimulationResult = {
  success_rate: 0.95,
  median_final_value: 750000,
  mean_final_value: 800000,
  percentiles: { p50: 750000 },
  median_depletion_age: null,
  median_depletion_year: null,
  total_withdrawn_median: 900000,
  total_taxes_median: 120000,
  percentile_paths: { p50: [500000, 750000] },
  year_breakdown: [],
  initial_withdrawal_rate: 8,
  prob_10_year_failure: 0.02,
};

function jsonResponse(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function job(status: SimulationJobStatus['status']): SimulationJobStatus {
  return {
    job_id: 'existing-job',
    status,
    current_year: status === 'succeeded' ? 40 : 1,
    total_years: 40,
    progress: status === 'succeeded' ? 1 : 0.025,
    result: status === 'succeeded' ? result : null,
    created_at: new Date(0).toISOString(),
    updated_at: new Date().toISOString(),
  };
}

async function collect(token?: string): Promise<{
  events: SimulationEvent[];
  error?: unknown;
}> {
  const events: SimulationEvent[] = [];
  try {
    for await (const event of runSimulationWithProgress(input, token)) {
      events.push(event);
    }
    return { events };
  } catch (error) {
    return { events, error };
  }
}

function waitForAbort(options?: RequestInit): Promise<Response> {
  return new Promise((_, reject) => {
    options?.signal?.addEventListener('abort', () => {
      reject(new DOMException('The operation was aborted.', 'AbortError'));
    }, { once: true });
  });
}

describe('simulation startup and polling reliability', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(0);
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('waits through a cold start longer than 30 seconds before creating one job', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((url, options) => {
      if (String(url).endsWith('/health')) {
        return new Promise((resolve, reject) => {
          const timer = setTimeout(() => resolve(jsonResponse({ status: 'healthy' })), 45_000);
          options?.signal?.addEventListener('abort', () => {
            clearTimeout(timer);
            reject(new DOMException('The operation was aborted.', 'AbortError'));
          }, { once: true });
        });
      }
      return Promise.resolve(jsonResponse(job('succeeded'), 202));
    });

    const outcome = collect('signed-in-token');
    await vi.advanceTimersByTimeAsync(31_000);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/health$/);
    const headers = new Headers(fetchMock.mock.calls[0][1]?.headers);
    expect(headers.has('Authorization')).toBe(false);
    expect(headers.has('Content-Type')).toBe(false);

    await vi.advanceTimersByTimeAsync(15_000);
    const completed = await outcome;
    expect(completed.error).toBeUndefined();
    expect(completed.events[0]).toMatchObject({ type: 'progress', year: 0 });
    expect(completed.events.at(-1)).toEqual({ type: 'complete', result });
    expect(fetchMock.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1);
  });

  it('reports a timed-out job POST without retrying or launching a stream', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((url, options) => {
      if (String(url).endsWith('/health')) {
        return Promise.resolve(jsonResponse({ status: 'healthy' }));
      }
      return waitForAbort(options);
    });

    const outcome = collect();
    await vi.advanceTimersByTimeAsync(121_000);
    const failed = await outcome;
    expect(failed.error).toBeInstanceOf(TimeoutError);
    expect((failed.error as Error).message).toMatch(/timed out|too long|timeout/i);
    expect((failed.error as Error).message).not.toMatch(/cancelled/i);
    expect(fetchMock.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1);
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/simulate/stream'))).toBe(false);
  });

  it.each(['Failed to fetch', 'Load failed'])('recovers from %s while retaining the original job', async (networkMessage) => {
    let polls = 0;
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((url, options) => {
      if (String(url).endsWith('/health')) return Promise.resolve(jsonResponse({ status: 'healthy' }));
      if (options?.method === 'POST') return Promise.resolve(jsonResponse(job('queued'), 202));
      polls += 1;
      if (polls === 1) return Promise.reject(new TypeError(networkMessage));
      if (polls === 2) return Promise.resolve(jsonResponse({ detail: 'Temporarily unavailable' }, 503));
      return Promise.resolve(jsonResponse(job(polls === 3 ? 'running' : 'succeeded')));
    });

    const outcome = collect();
    await vi.advanceTimersByTimeAsync(20_000);
    const completed = await outcome;
    expect(completed.error).toBeUndefined();
    expect(completed.events.at(-1)).toEqual({ type: 'complete', result });
    expect(polls).toBe(4);
    expect(fetchMock.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1);
    const pollUrls = fetchMock.mock.calls
      .map(([url]) => String(url))
      .filter((url) => url.includes('/simulate/jobs/'));
    expect(new Set(pollUrls)).toEqual(new Set(['http://localhost:8000/simulate/jobs/existing-job']));
  });

  it('stops after three unsuccessful health reads without creating a job', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      jsonResponse({ detail: 'Temporarily unavailable' }, 503),
    );
    const outcome = collect();
    await vi.advanceTimersByTimeAsync(5_000);
    const failed = await outcome;
    expect(failed.error).toMatchObject({ statusCode: 503 });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls.every(([url]) => String(url).endsWith('/health'))).toBe(true);
  });

  it('stops after three failed polling reads without submitting a replacement job', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((url, options) => {
      if (String(url).endsWith('/health')) return Promise.resolve(jsonResponse({ status: 'healthy' }));
      if (options?.method === 'POST') return Promise.resolve(jsonResponse(job('queued'), 202));
      return Promise.resolve(jsonResponse({ detail: 'Temporarily unavailable' }, 503));
    });
    const outcome = collect();
    await vi.advanceTimersByTimeAsync(10_000);
    const failed = await outcome;
    expect(failed.error).toMatchObject({ statusCode: 503 });
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('/simulate/jobs/'))).toHaveLength(3);
    expect(fetchMock.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1);
  });

  it('surfaces a missing job without retrying it or falling back to another simulation', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((url, options) => {
      if (String(url).endsWith('/health')) return Promise.resolve(jsonResponse({ status: 'healthy' }));
      if (options?.method === 'POST') return Promise.resolve(jsonResponse(job('queued'), 202));
      return Promise.resolve(jsonResponse({ detail: 'Simulation job not found' }, 404));
    });
    const outcome = collect();
    await vi.advanceTimersByTimeAsync(5_000);
    const failed = await outcome;
    expect(failed.error).toMatchObject({ statusCode: 404 });
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('/simulate/jobs/'))).toHaveLength(1);
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/simulate/stream'))).toBe(false);
  });

  it('uses the legacy stream only when the job creation endpoint is missing', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (String(url).endsWith('/health')) return Promise.resolve(jsonResponse({ status: 'healthy' }));
      if (String(url).endsWith('/simulate/jobs')) {
        return Promise.resolve(jsonResponse({ detail: 'Not Found' }, 404));
      }
      if (String(url).endsWith('/simulate/stream')) {
        return Promise.resolve(new Response(`data: ${JSON.stringify({ type: 'complete', result })}\n\n`, {
          headers: { 'Content-Type': 'text/event-stream' },
        }));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    const completed = await collect();
    expect(completed.error).toBeUndefined();
    expect(completed.events.at(-1)).toEqual({ type: 'complete', result });
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual([
      'http://localhost:8000/health',
      'http://localhost:8000/simulate/jobs',
      'http://localhost:8000/simulate/stream',
    ]);
  });

  it('keeps polling a healthy job that completes after eleven minutes', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url, options) => {
      if (String(url).endsWith('/health')) return Promise.resolve(jsonResponse({ status: 'healthy' }));
      if (options?.method === 'POST') return Promise.resolve(jsonResponse(job('queued'), 202));
      return Promise.resolve(jsonResponse(job(Date.now() >= 11 * 60_000 ? 'succeeded' : 'running')));
    });
    const outcome = collect();
    await vi.advanceTimersByTimeAsync(11 * 60_000 + 5_000);
    const completed = await outcome;
    expect(completed.error).toBeUndefined();
    expect(completed.events.at(-1)).toEqual({ type: 'complete', result });
  });

  it('stops a job that is still running after the eighteen-minute deadline', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((url, options) => {
      if (String(url).endsWith('/health')) return Promise.resolve(jsonResponse({ status: 'healthy' }));
      return Promise.resolve(jsonResponse(job(options?.method === 'POST' ? 'queued' : 'running')));
    });
    const outcome = collect();
    await vi.advanceTimersByTimeAsync(18 * 60_000 + 10_000);
    const failed = await outcome;
    expect(failed.error).toBeInstanceOf(TimeoutError);
    expect(failed.events.some((event) => event.type === 'complete')).toBe(false);
    const callCount = fetchMock.mock.calls.length;
    await vi.advanceTimersByTimeAsync(60_000);
    expect(fetchMock).toHaveBeenCalledTimes(callCount);
  });
});
