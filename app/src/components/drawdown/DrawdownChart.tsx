"use client";

import {
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent,
} from "react";
import {
  estimatedLabelWidth,
  jumpAround,
  keyedDraw,
  labelPlacement,
  niceTicks,
  rowAt,
  stepPlaceIn,
  type MarkedSpan,
} from "../../lib/drawdown";
import { SPLIT_COLORS } from "./SplitBar";

const REFERENCE_LINE = "#78716c";
const PLOT_BOTTOM = 318;
const TOTAL_HEIGHT = 374;
const MARGIN = { top: 56, right: 18, left: 58 };
const THUMB_SIZE = 26;
/** Marker labels stack above the plot, one line each. */
const LABEL_LINE = 18;
const LABEL_SPACE = 20;
/**
 * A touch must travel this far before it counts as a drag or a pan; across
 * the plot it moves the draw, up or down it scrolls the page.
 */
const TOUCH_SLOP = 8;

const NO_BANDS: readonly MarkedSpan[] = [];

/** A pointer pressed on the plot, until it lifts or the browser takes it. */
interface Press {
  pointerId: number;
  touch: boolean;
  x: number;
  y: number;
  dragging: boolean;
}

export interface ChartMarker {
  key: string;
  draw: number;
  label: string;
}

export interface ChartLabels {
  /** The line through what the reader would keep if no pound or dollar went anywhere. */
  reference: string;
  tax: string;
  lost: string;
  axis: string;
  slider: string;
}

export interface ChartRow {
  draw: number;
  money_to_spend: number;
}

function pathThrough(points: [number, number][]): string {
  return points.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join("");
}

/**
 * Money to spend at every draw. The horizontal axis doubles as the slider that
 * sets the draw, and dragging across the plot moves it too. A mouse sets the
 * draw where it presses; a touch sets it on a tap or a drag across the plot,
 * and leaves a vertical swipe to scroll the page. Under the pointer, inside a
 * jump the API holds no row for, the tooltip says what changes there and
 * between which draws, in the ladder's words, rather than a figure the engine
 * may not give.
 */
export function DrawdownChart<Row extends ChartRow>({
  sweep,
  bands = NO_BANDS,
  draw,
  top,
  step,
  markers,
  onDraw,
  taxAbove,
  lostAt,
  details,
  describeStep,
  money,
  compact,
  labels,
}: {
  sweep: Row[];
  /** The API's bands; the chart reads a jump from them as the page does. */
  bands?: readonly MarkedSpan[];
  draw: number;
  top: number;
  step: number;
  markers: ChartMarker[];
  onDraw: (draw: number) => void;
  /** Tax at this row beyond the tax with no draw. */
  taxAbove: (row: Row, noDraw: Row) => number;
  /** Benefits lost at this row against no draw; below zero when they rise. */
  lostAt: (row: Row, noDraw: Row) => number;
  /** Lines under the amount to spend in the tooltip. */
  details: (row: Row) => string[];
  /** What changes all at once across a jump, from the API's rows at its band's ends, as the ladder says it. */
  describeStep: (from: Row, to: Row) => string;
  money: (value: number) => string;
  compact: (value: number) => string;
  labels: ChartLabels;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  const [hover, setHover] = useState<number | null>(null);
  const press = useRef<Press | null>(null);
  const labelNodes = useRef(new Map<string, SVGTextElement>());
  const [measured, setMeasured] = useState<Record<string, number>>({});

  // Measures before the first paint, so a phone never sees the default width.
  useLayoutEffect(() => {
    const element = box.current;
    if (!element || typeof ResizeObserver === "undefined") return;
    const measure = (measured: number) => setWidth(Math.max(280, measured));
    measure(element.getBoundingClientRect().width);
    const observer = new ResizeObserver(([entry]) => measure(entry.contentRect.width));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const noDraw = sweep[0];
  const rows = useMemo(() => {
    const inside = sweep.filter((row) => row.draw <= top);
    return inside[inside.length - 1].draw < top ? [...inside, rowAt(sweep, top, bands)] : inside;
  }, [sweep, top, bands]);

  const visibleMarkers = markers.filter((marker) => marker.draw <= top);
  const labelText = visibleMarkers.map((marker) => marker.label).join("\n");

  // Measures each marker label once the browser has laid it out (a resize
  // observer reports on its first look), so a label sits on the side of its
  // line with room for it. Until then, and where nothing lays text out, an
  // estimate stands in.
  useLayoutEffect(() => {
    const element = box.current;
    if (!element || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => {
      const lengths: Record<string, number> = {};
      for (const [label, node] of labelNodes.current) {
        const length = node.getComputedTextLength?.();
        if (typeof length === "number" && length > 0) lengths[label] = length;
      }
      setMeasured((current) =>
        Object.keys(lengths).length === Object.keys(current).length &&
        Object.entries(lengths).every(([label, length]) => current[label] === length)
          ? current
          : lengths,
      );
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [labelText]);

  // Room above the plot for every marker's label; two fit the default margin.
  const extra = Math.max(0, LABEL_SPACE + LABEL_LINE * visibleMarkers.length - MARGIN.top);
  const marginTop = MARGIN.top + extra;
  const plotBottom = PLOT_BOTTOM + extra;
  const totalHeight = TOTAL_HEIGHT + extra;

  const plotWidth = width - MARGIN.left - MARGIN.right;
  const x = (value: number) => MARGIN.left + (top > 0 ? (value / top) * plotWidth : 0);

  const referenceAt = (row: Row) => noDraw.money_to_spend + row.draw;
  const allValues = rows.flatMap((row) => [row.money_to_spend, referenceAt(row)]);
  const lowest = Math.min(...allValues);
  const highest = Math.max(...allValues);
  const yTicks = niceTicks(lowest, highest, 4);
  const yLow = Math.min(lowest, yTicks[0]);
  const yHigh = Math.max(highest, yTicks[yTicks.length - 1], yLow + 1);
  const y = (value: number) =>
    plotBottom - ((value - yLow) / (yHigh - yLow)) * (plotBottom - marginTop);

  const lossOf = (row: Row) => Math.max(lostAt(row, noDraw), 0);
  const lostTop = rows.map((row) => row.money_to_spend + lossOf(row));
  const taxTop = rows.map((row, i) => Math.max(lostTop[i], referenceAt(row)));
  const hasLoss = rows.some((row) => lossOf(row) >= 1);
  const hasTax = rows.some((row) => taxAbove(row, noDraw) >= 1);

  const band = (lower: number[], upper: number[]) =>
    `${pathThrough(rows.map((row, i) => [x(row.draw), y(upper[i])]))}L${pathThrough(
      rows.map((row, i) => [x(row.draw), y(lower[i])] as [number, number]).reverse(),
    ).slice(1)}Z`;

  const chosen = rowAt(sweep, draw, bands);
  // Inside a jump the API places only to within its band, the tooltip shows
  // the jump instead of a row.
  const jump = hover === null ? null : jumpAround(sweep, hover, bands);
  const inspected = hover === null || jump ? null : rowAt(sweep, hover, bands);
  const xTicks = niceTicks(0, top, width < 480 ? 3 : 6);

  const drawAtPointer = (event: PointerEvent<SVGRectElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    const share = Math.min(Math.max((event.clientX - bounds.left) / bounds.width, 0), 1);
    return Math.min(Math.round((share * top) / step) * step, top);
  };

  const onPointerDown = (event: PointerEvent<SVGRectElement>) => {
    const touch = event.pointerType === "touch" || event.pointerType === "pen";
    press.current = {
      pointerId: event.pointerId,
      touch,
      x: event.clientX,
      y: event.clientY,
      dragging: !touch,
    };
    if (touch) return;
    event.currentTarget.setPointerCapture?.(event.pointerId);
    onDraw(drawAtPointer(event));
  };

  const onPointerMove = (event: PointerEvent<SVGRectElement>) => {
    const value = drawAtPointer(event);
    const current = press.current;
    if (!current || current.pointerId !== event.pointerId) {
      if (event.pointerType !== "touch") setHover(value);
      return;
    }
    if (!current.dragging) {
      const across = Math.abs(event.clientX - current.x);
      const down = Math.abs(event.clientY - current.y);
      if (down >= TOUCH_SLOP && down >= across) {
        // A vertical swipe: the page scrolls and the draw stays put.
        press.current = null;
        return;
      }
      if (across < TOUCH_SLOP) return;
      current.dragging = true;
      event.currentTarget.setPointerCapture?.(event.pointerId);
    }
    if (event.pointerType === "mouse" && event.buttons === 0) {
      // The button came up somewhere this element never heard about.
      press.current = null;
      setHover(value);
      return;
    }
    setHover(value);
    onDraw(value);
  };

  const onPointerUp = (event: PointerEvent<SVGRectElement>) => {
    const current = press.current;
    press.current = null;
    if (current?.touch && !current.dragging && current.pointerId === event.pointerId) {
      onDraw(drawAtPointer(event));
    }
  };

  const endPress = () => {
    press.current = null;
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    const next = keyedDraw(event.key, draw, top, step);
    if (next === null) return;
    event.preventDefault();
    onDraw(next);
  };

  return (
    <figure className="m-0">
      <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-[var(--color-text-muted)]">
        <li className="flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className="inline-block h-0.5 w-4 rounded"
            style={{ backgroundColor: SPLIT_COLORS.kept }}
          />
          Money to spend
        </li>
        <li className="flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className="inline-block h-0.5 w-4 rounded"
            style={{ backgroundColor: REFERENCE_LINE }}
          />
          {labels.reference}
        </li>
        {hasTax && (
          <li className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="inline-block h-3 w-3 rounded-sm"
              style={{ backgroundColor: SPLIT_COLORS.tax, opacity: 0.22 }}
            />
            {labels.tax}
          </li>
        )}
        {hasLoss && (
          <li className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="inline-block h-3 w-3 rounded-sm"
              style={{ backgroundColor: SPLIT_COLORS.lost, opacity: 0.22 }}
            />
            {labels.lost}
          </li>
        )}
      </ul>

      <div ref={box} className="relative mt-2" style={{ height: totalHeight }}>
        <svg
          width={width}
          height={totalHeight}
          role="img"
          aria-label={`Money to spend at each amount you draw, from ${money(noDraw.money_to_spend)} with no draw to ${money(rows[rows.length - 1].money_to_spend)} with a draw of ${money(top)}.`}
        >
          {yTicks.map((tick) => (
            <g key={tick}>
              <line
                x1={MARGIN.left}
                x2={width - MARGIN.right}
                y1={y(tick)}
                y2={y(tick)}
                stroke="var(--color-gray-200)"
              />
              <text
                x={MARGIN.left - 10}
                y={y(tick) + 4}
                textAnchor="end"
                className="fill-[var(--color-text-muted)] text-[12px] tabular-nums"
              >
                {compact(tick)}
              </text>
            </g>
          ))}

          {hasLoss && <path d={band(rows.map((r) => r.money_to_spend), lostTop)} fill={SPLIT_COLORS.lost} opacity={0.18} />}
          {hasTax && <path d={band(lostTop, taxTop)} fill={SPLIT_COLORS.tax} opacity={0.18} />}

          <path
            d={pathThrough(rows.map((row) => [x(row.draw), y(referenceAt(row))]))}
            fill="none"
            stroke={REFERENCE_LINE}
            strokeWidth={1.5}
          />
          <path
            d={pathThrough(rows.map((row) => [x(row.draw), y(row.money_to_spend)]))}
            fill="none"
            stroke={SPLIT_COLORS.kept}
            strokeWidth={2.5}
            strokeLinejoin="round"
            strokeLinecap="round"
          />

          {visibleMarkers.map((marker, index) => {
            const placed = labelPlacement(
              x(marker.draw),
              measured[marker.label] ?? estimatedLabelWidth(marker.label),
              width,
            );
            const labelY = 14 + index * LABEL_LINE;
            return (
              <g key={marker.key}>
                <line
                  x1={x(marker.draw)}
                  x2={x(marker.draw)}
                  y1={labelY + 4}
                  y2={plotBottom}
                  stroke="var(--color-gray-400)"
                />
                <text
                  ref={(node) => {
                    if (node) labelNodes.current.set(marker.label, node);
                    else labelNodes.current.delete(marker.label);
                  }}
                  x={placed.x}
                  y={labelY + 4}
                  textAnchor={placed.anchor}
                  className="fill-[var(--color-text)] text-[12px]"
                >
                  {marker.label}
                </text>
              </g>
            );
          })}

          <line
            x1={x(draw)}
            x2={x(draw)}
            y1={y(chosen.money_to_spend)}
            y2={plotBottom}
            stroke="var(--color-text)"
          />
          <circle
            cx={x(draw)}
            cy={y(chosen.money_to_spend)}
            r={6}
            fill={SPLIT_COLORS.kept}
            stroke="var(--color-bg-card)"
            strokeWidth={2}
          />

          {hover !== null && (
            <line
              x1={x(hover)}
              x2={x(hover)}
              y1={marginTop}
              y2={plotBottom}
              stroke="var(--color-gray-500)"
            />
          )}
          {inspected && (
            <circle
              data-testid="hover-point"
              cx={x(inspected.draw)}
              cy={y(inspected.money_to_spend)}
              r={4}
              fill={SPLIT_COLORS.kept}
              stroke="var(--color-bg-card)"
              strokeWidth={2}
            />
          )}

          <rect
            data-testid="curve-surface"
            x={MARGIN.left}
            y={marginTop}
            width={Math.max(plotWidth, 1)}
            height={plotBottom - marginTop - THUMB_SIZE / 2}
            fill="transparent"
            style={{ touchAction: "pan-y", cursor: "ew-resize" }}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={endPress}
            onLostPointerCapture={endPress}
            onPointerLeave={() => setHover(null)}
          />

          {xTicks.map((tick) => (
            <text
              key={tick}
              x={Math.min(x(tick), width - MARGIN.right - 14)}
              y={plotBottom + 34}
              textAnchor="middle"
              className="fill-[var(--color-text-muted)] text-[12px] tabular-nums"
            >
              {compact(tick)}
            </text>
          ))}
          <text
            x={MARGIN.left + plotWidth / 2}
            y={plotBottom + 48}
            textAnchor="middle"
            className="fill-[var(--color-text-muted)] text-[12px]"
          >
            {labels.axis}
          </text>
        </svg>

        <input
          type="range"
          className="draw-slider absolute"
          aria-label={labels.slider}
          aria-valuetext={money(draw)}
          min={0}
          max={Math.max(top, step)}
          step={step}
          value={Math.min(draw, top)}
          onChange={(event) => onDraw(Math.min(Number(event.target.value), top))}
          onKeyDown={onKeyDown}
          style={{
            left: MARGIN.left - THUMB_SIZE / 2,
            width: plotWidth + THUMB_SIZE,
            top: plotBottom - 16,
            height: 32,
          }}
        />

        {hover !== null && (
          <div
            className="pointer-events-none absolute max-w-[16rem] rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-bg-card)] px-3 py-2 text-sm shadow-[var(--shadow-md)]"
            style={{
              top: marginTop + 6,
              ...(x(hover) > width / 2 ? { right: width - x(hover) + 10 } : { left: x(hover) + 10 }),
            }}
          >
            <div className="text-[var(--color-text-muted)]">Draw {money(hover)}</div>
            {jump ? (
              <>
                <div className="font-semibold tabular-nums">{stepPlaceIn(money, jump)}</div>
                <div>{describeStep(rowAt(sweep, jump.draw_from), rowAt(sweep, jump.draw_to))}</div>
              </>
            ) : (
              inspected && (
                <>
                  <div className="font-semibold tabular-nums">
                    {money(inspected.money_to_spend)} to spend
                  </div>
                  {details(inspected).map((line) => (
                    <div key={line} className="tabular-nums">
                      {line}
                    </div>
                  ))}
                </>
              )
            )}
          </div>
        )}
      </div>
    </figure>
  );
}
