"use client";

import { useLayoutEffect, useMemo, useRef, useState, type PointerEvent } from "react";
import { niceTicks, rowAt } from "../../lib/drawdown";
import { SPLIT_COLORS } from "./SplitBar";

const REFERENCE_LINE = "#78716c";
const PLOT_BOTTOM = 318;
const TOTAL_HEIGHT = 374;
const MARGIN = { top: 56, right: 18, left: 58 };
const THUMB_SIZE = 26;
/** Marker labels stack above the plot, one line each. */
const LABEL_LINE = 18;
const LABEL_SPACE = 20;

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
 * sets the draw, and dragging across the plot moves it too.
 */
export function DrawdownChart<Row extends ChartRow>({
  sweep,
  draw,
  top,
  step,
  markers,
  onDraw,
  taxAbove,
  lostAt,
  details,
  money,
  compact,
  labels,
}: {
  sweep: Row[];
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
  money: (value: number) => string;
  compact: (value: number) => string;
  labels: ChartLabels;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  const [hover, setHover] = useState<number | null>(null);
  const dragging = useRef(false);

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
    return inside[inside.length - 1].draw < top ? [...inside, rowAt(sweep, top)] : inside;
  }, [sweep, top]);

  const visibleMarkers = markers.filter((marker) => marker.draw <= top);
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

  const chosen = rowAt(sweep, draw);
  const inspected = hover === null ? null : rowAt(sweep, hover);
  const xTicks = niceTicks(0, top, width < 480 ? 3 : 6);

  const drawAtPointer = (event: PointerEvent<SVGRectElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    const share = Math.min(Math.max((event.clientX - bounds.left) / bounds.width, 0), 1);
    return Math.min(Math.round((share * top) / step) * step, top);
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
            const nearEnd = x(marker.draw) > width * 0.62;
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
                  x={x(marker.draw) + (nearEnd ? -5 : 5)}
                  y={labelY + 4}
                  textAnchor={nearEnd ? "end" : "start"}
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

          {inspected && (
            <>
              <line
                x1={x(inspected.draw)}
                x2={x(inspected.draw)}
                y1={marginTop}
                y2={plotBottom}
                stroke="var(--color-gray-500)"
              />
              <circle
                cx={x(inspected.draw)}
                cy={y(inspected.money_to_spend)}
                r={4}
                fill={SPLIT_COLORS.kept}
                stroke="var(--color-bg-card)"
                strokeWidth={2}
              />
            </>
          )}

          <rect
            data-testid="curve-surface"
            x={MARGIN.left}
            y={marginTop}
            width={Math.max(plotWidth, 1)}
            height={plotBottom - marginTop - THUMB_SIZE / 2}
            fill="transparent"
            style={{ touchAction: "pan-y", cursor: "ew-resize" }}
            onPointerDown={(event) => {
              dragging.current = true;
              event.currentTarget.setPointerCapture?.(event.pointerId);
              onDraw(drawAtPointer(event));
            }}
            onPointerMove={(event) => {
              const value = drawAtPointer(event);
              setHover(value);
              if (dragging.current) onDraw(value);
            }}
            onPointerUp={() => {
              dragging.current = false;
            }}
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
          onChange={(event) => onDraw(Number(event.target.value))}
          style={{
            left: MARGIN.left - THUMB_SIZE / 2,
            width: plotWidth + THUMB_SIZE,
            top: plotBottom - 16,
            height: 32,
          }}
        />

        {inspected && (
          <div
            className="pointer-events-none absolute rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-bg-card)] px-3 py-2 text-sm shadow-[var(--shadow-md)]"
            style={{
              top: marginTop + 6,
              ...(x(inspected.draw) > width / 2
                ? { right: width - x(inspected.draw) + 10 }
                : { left: x(inspected.draw) + 10 }),
            }}
          >
            <div className="text-[var(--color-text-muted)]">Draw {money(inspected.draw)}</div>
            <div className="font-semibold tabular-nums">{money(inspected.money_to_spend)} to spend</div>
            {details(inspected).map((line) => (
              <div key={line} className="tabular-nums">
                {line}
              </div>
            ))}
          </div>
        )}
      </div>
    </figure>
  );
}
