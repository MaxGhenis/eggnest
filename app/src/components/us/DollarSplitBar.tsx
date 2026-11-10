import type { CentSplit } from "../../lib/us-drawdown";
import { SPLIT_COLORS, SplitBar, SplitLegend } from "../drawdown/SplitBar";

const cents = (amount: number) => `${amount}¢`;

/** One dollar, split between what you keep, tax and lost benefits. */
export function DollarSplitBar({ split }: { split: CentSplit }) {
  return (
    <SplitBar
      unit={cents}
      parts={[
        { key: "kept", amount: Math.max(split.kept, 0), name: "you keep", ink: "#1c1917" },
        { key: "tax", amount: Math.max(split.tax, 0), name: "you pay in tax", ink: "#ffffff" },
        {
          key: "lost",
          amount: Math.max(split.lost, 0),
          name: "you lose in benefits",
          ink: "#ffffff",
        },
      ]}
    />
  );
}

export function DollarSplitLegend({ showLost }: { showLost: boolean }) {
  return (
    <SplitLegend
      items={[
        { label: "You keep", color: SPLIT_COLORS.kept },
        { label: "Tax", color: SPLIT_COLORS.tax },
        ...(showLost ? [{ label: "Benefits you lose", color: SPLIT_COLORS.lost }] : []),
      ]}
    />
  );
}
