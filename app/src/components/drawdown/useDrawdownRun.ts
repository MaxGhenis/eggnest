"use client";

import { useEffect, useRef, useState } from "react";
import { useDebouncedValue } from "../../hooks/useDebouncedValue";
import { failureMessage } from "../../lib/drawdown";

export interface DrawdownRunResult<Run> {
  /** The inputs the API answered for, and those inputs with no draw. */
  key: string;
  baseKey: string;
  data: Run;
}

interface InFlight {
  key: string;
  baseKey: string;
  controller: AbortController;
}

interface Failed {
  key: string;
  attempt: number;
  message: string;
}

/**
 * Asks the API for the page's inputs once they stop changing.
 *
 * A run for the same figures about the household holds a sweep that serves
 * any draw, so a change to the draw alone leaves a run in flight to land and
 * then asks for the new draw; a change to anything else aborts it. A failure
 * shows only for the inputs that failed, until "Try again" sends them again,
 * and while that runs the page shows it is working, not the old failure.
 */
export function useDrawdownRun<Inputs extends { draw_amount: number }, Run>(
  inputs: Inputs,
  problem: string | null,
  fetchRun: (inputs: Inputs, signal: AbortSignal) => Promise<Run>,
  delay = 300,
) {
  const [run, setRun] = useState<DrawdownRunResult<Run> | null>(null);
  const [failed, setFailed] = useState<Failed | null>(null);
  const [attempt, setAttempt] = useState(0);
  const inflight = useRef<InFlight | null>(null);

  const key = JSON.stringify(inputs);
  const baseKey = JSON.stringify({ ...inputs, draw_amount: 0 });
  const debouncedKey = useDebouncedValue(key, delay);

  useEffect(() => {
    if (problem || debouncedKey !== key) return;
    const current = inflight.current;
    if (current && current.baseKey !== baseKey) {
      current.controller.abort();
      inflight.current = null;
    } else if (current) {
      // Asking for these inputs already, or for this household at another
      // draw: once that lands, this effect asks for the draw on the page.
      return;
    }
    if (run?.key === key) return;
    if (failed && failed.key === key && failed.attempt === attempt) return;

    const controller = new AbortController();
    const request: InFlight = { key, baseKey, controller };
    inflight.current = request;
    const tried = attempt;
    const finish = () => {
      if (inflight.current === request) inflight.current = null;
    };
    fetchRun(JSON.parse(key) as Inputs, controller.signal).then(
      (data) => {
        finish();
        if (controller.signal.aborted) return;
        setRun({ key, baseKey, data });
        setFailed(null);
      },
      (error: unknown) => {
        finish();
        if (controller.signal.aborted) return;
        setFailed({ key, attempt: tried, message: failureMessage(error) });
      },
    );
  }, [debouncedKey, key, baseKey, problem, attempt, run, failed, fetchRun]);

  useEffect(
    () => () => {
      inflight.current?.controller.abort();
      inflight.current = null;
    },
    [],
  );

  const failure =
    !problem && failed && failed.key === key && failed.attempt === attempt ? failed.message : null;
  return {
    run,
    failure,
    /** No answer yet for the inputs on the page, and none has failed. */
    working: !problem && failure === null && run?.key !== key,
    key,
    baseKey,
    retry: () => setAttempt((count) => count + 1),
  };
}
