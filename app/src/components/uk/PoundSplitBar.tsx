import type { PoundSplit } from "../../lib/uk-drawdown";

export const SPLIT_COLORS = {
  kept: "#d97706",
  tax: "#2563eb",
  lost: "#be185d",
} as const;

/** Widths below this share leave no room to print the pence. */
const SMALLEST_LABELLED_SHARE = 0.11;

/** One pound, split between what you keep, tax and lost Pension Credit. */
export function PoundSplitBar({ split }: { split: PoundSplit }) {
  const parts = [
    { key: "kept", pence: Math.max(split.kept, 0), name: "you keep", ink: "#1c1917" },
    { key: "tax", pence: Math.max(split.tax, 0), name: "income tax", ink: "#ffffff" },
    { key: "lost", pence: Math.max(split.lost, 0), name: "Pension Credit lost", ink: "#ffffff" },
  ] as const;
  const whole = parts.reduce((sum, part) => sum + part.pence, 0) || 1;
  const shown = parts.filter((part) => part.pence > 0);

  return (
    <div
      role="img"
      aria-label={shown.map((part) => `${part.pence}p ${part.name}`).join(", ")}
      className="flex h-7 w-full gap-0.5"
    >
      {shown.map((part) => (
        <div
          key={part.key}
          title={`${part.pence}p ${part.name}`}
          className="flex items-center rounded px-2 text-xs font-semibold tabular-nums"
          style={{
            width: `${(part.pence / whole) * 100}%`,
            backgroundColor: SPLIT_COLORS[part.key],
            color: part.ink,
          }}
        >
          {part.pence / whole >= SMALLEST_LABELLED_SHARE ? `${part.pence}p` : ""}
        </div>
      ))}
    </div>
  );
}

export function PoundSplitLegend({ showLost }: { showLost: boolean }) {
  const items = [
    { label: "You keep", color: SPLIT_COLORS.kept },
    { label: "Income tax", color: SPLIT_COLORS.tax },
    ...(showLost ? [{ label: "Pension Credit lost", color: SPLIT_COLORS.lost }] : []),
  ];
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-[var(--color-text-muted)]">
      {items.map((item) => (
        <li key={item.label} className="flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className="inline-block h-3 w-3 rounded-sm"
            style={{ backgroundColor: item.color }}
          />
          {item.label}
        </li>
      ))}
    </ul>
  );
}
