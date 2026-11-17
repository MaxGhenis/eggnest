import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NetworkError, SimulationError } from "../../lib/api";
import { useDrawdownRun } from "./useDrawdownRun";

// Invariants these tests hold:
// - A run in flight for the same figures about the household serves any
//   draw, so a draw-only change keeps it, and asks for the new draw once it
//   lands (us-page-3). A change to the household aborts it.
// - The page shows a failure only for the figures that failed, and a retry
//   shows the page working rather than the old failure (us-page-8).
// - Every failure is worded by kind (us-page-8, uk-page-04's page half).

interface Inputs {
  pension: number;
  draw_amount: number;
}

const DELAY = 20;

/** A request the test answers by hand. */
function controlledRuns() {
  const calls: { inputs: Inputs; signal: AbortSignal; resolve: (run: string) => void; reject: (error: unknown) => void }[] = [];
  const fetchRun = vi.fn(
    (inputs: Inputs, signal: AbortSignal) =>
      new Promise<string>((resolve, reject) => {
        calls.push({ inputs, signal, resolve, reject });
        signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
      }),
  );
  return { calls, fetchRun };
}

function settle() {
  return act(async () => {
    await new Promise((resolve) => setTimeout(resolve, DELAY * 4));
  });
}

function mount(
  fetchRun: (inputs: Inputs, signal: AbortSignal) => Promise<string>,
  first: Inputs,
  problem: string | null = null,
) {
  return renderHook(
    ({ inputs, problem }: { inputs: Inputs; problem: string | null }) =>
      useDrawdownRun(inputs, problem, fetchRun, DELAY),
    { initialProps: { inputs: first, problem } },
  );
}

describe("useDrawdownRun", () => {
  it("keeps a run in flight through draw-only changes, then asks for the draw", async () => {
    // us-page-3: each draw change aborted the run for a changed household, so
    // a reader who nudged the slider kept restarting the wait.
    const { calls, fetchRun } = controlledRuns();
    const view = mount(fetchRun, { pension: 0, draw_amount: 1_000 });
    await settle();
    expect(calls).toHaveLength(1);

    view.rerender({ inputs: { pension: 0, draw_amount: 2_000 }, problem: null });
    await settle();
    view.rerender({ inputs: { pension: 0, draw_amount: 3_000 }, problem: null });
    await settle();
    expect(calls).toHaveLength(1);
    expect(calls[0].signal.aborted).toBe(false);

    await act(async () => calls[0].resolve("run at 1,000"));
    expect(view.result.current.run?.data).toBe("run at 1,000");
    await waitFor(() => expect(calls).toHaveLength(2));
    expect(calls[1].inputs).toEqual({ pension: 0, draw_amount: 3_000 });

    await act(async () => calls[1].resolve("run at 3,000"));
    await settle();
    expect(view.result.current.run?.data).toBe("run at 3,000");
    expect(calls).toHaveLength(2);
  });

  it("aborts a run for other figures about the household", async () => {
    const { calls, fetchRun } = controlledRuns();
    const view = mount(fetchRun, { pension: 0, draw_amount: 1_000 });
    await settle();
    view.rerender({ inputs: { pension: 5_000, draw_amount: 1_000 }, problem: null });
    await settle();
    expect(calls).toHaveLength(2);
    expect(calls[0].signal.aborted).toBe(true);
    expect(view.result.current.failure).toBeNull();
  });

  it("words a failure by kind and shows the page working while it tries again", async () => {
    // us-page-8: "Try again" gave no sign it was working, and every failure
    // said to check the connection.
    const { calls, fetchRun } = controlledRuns();
    const view = mount(fetchRun, { pension: 0, draw_amount: 1_000 });
    await settle();
    await act(async () => calls[0].reject(new SimulationError("engine failed", 500)));
    expect(view.result.current.failure).toBe(
      "The calculator couldn’t work out this year. Try again, or change a figure.",
    );
    await settle();
    expect(calls).toHaveLength(1);

    act(() => view.result.current.retry());
    await waitFor(() => expect(calls).toHaveLength(2));
    expect(view.result.current.failure).toBeNull();
    expect(view.result.current.working).toBe(true);

    await act(async () => calls[1].reject(new NetworkError("down")));
    expect(view.result.current.failure).toBe(
      "We couldn’t reach the calculator. Check your connection and try again.",
    );
    expect(view.result.current.working).toBe(false);
  });

  it("shows a failure only for the figures that failed", async () => {
    const { calls, fetchRun } = controlledRuns();
    const view = mount(fetchRun, { pension: 0, draw_amount: 1_000 });
    await settle();
    await act(async () => calls[0].resolve("run at 1,000"));

    view.rerender({ inputs: { pension: 0, draw_amount: 2_000 }, problem: null });
    await waitFor(() => expect(calls).toHaveLength(2));
    await act(async () => calls[1].reject(new NetworkError("down")));
    expect(view.result.current.failure).not.toBeNull();

    view.rerender({ inputs: { pension: 0, draw_amount: 1_000 }, problem: null });
    expect(view.result.current.failure).toBeNull();
    expect(view.result.current.run?.data).toBe("run at 1,000");
    await settle();
    expect(calls).toHaveLength(2);
  });

  it("sends nothing while the inputs have a problem", async () => {
    const { calls, fetchRun } = controlledRuns();
    const view = mount(fetchRun, { pension: 0, draw_amount: 1_000 }, "Enter your date of birth.");
    view.rerender({ inputs: { pension: 0, draw_amount: 2_000 }, problem: "Enter your date of birth." });
    await settle();
    expect(calls).toHaveLength(0);
    expect(view.result.current.working).toBe(false);
    view.rerender({ inputs: { pension: 0, draw_amount: 2_000 }, problem: null });
    await settle();
    expect(calls.map((call) => call.inputs.draw_amount)).toEqual([2_000]);
  });

  it("aborts the run in flight when the page goes", async () => {
    const { calls, fetchRun } = controlledRuns();
    const view = mount(fetchRun, { pension: 0, draw_amount: 1_000 });
    await settle();
    view.unmount();
    expect(calls[0].signal.aborted).toBe(true);
  });
});
