export const SPLIT_COLORS = {
  kept: "#d97706",
  tax: "#2563eb",
  lost: "#be185d",
} as const;

/** Widths below this share leave no room to print the amount. */
const SMALLEST_LABELLED_SHARE = 0.11;

export interface SplitPart {
  key: keyof typeof SPLIT_COLORS;
  /** Hundredths of the currency unit, such as pence or cents; never below 0. */
  amount: number;
  name: string;
  ink: string;
}

/** One unit of draw, split between what you keep, tax and lost benefits. */
export function SplitBar({
  parts,
  unit,
}: {
  parts: readonly SplitPart[];
  unit: (amount: number) => string;
}) {
  const whole = parts.reduce((sum, part) => sum + part.amount, 0) || 1;
  const shown = parts.filter((part) => part.amount > 0);

  return (
    <div
      role="img"
      aria-label={shown.map((part) => `${unit(part.amount)} ${part.name}`).join(", ")}
      className="flex h-7 w-full gap-0.5"
    >
      {shown.map((part) => (
        <div
          key={part.key}
          title={`${unit(part.amount)} ${part.name}`}
          className="flex items-center rounded px-2 text-xs font-semibold tabular-nums"
          style={{
            width: `${(part.amount * 100) / whole}%`,
            backgroundColor: SPLIT_COLORS[part.key],
            color: part.ink,
          }}
        >
          {part.amount / whole >= SMALLEST_LABELLED_SHARE ? unit(part.amount) : ""}
        </div>
      ))}
    </div>
  );
}

export function SplitLegend({ items }: { items: readonly { label: string; color: string }[] }) {
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
