import type { PoundSplit } from "../../lib/uk-drawdown";
import { SPLIT_COLORS, SplitBar, SplitLegend } from "../drawdown/SplitBar";

export { SPLIT_COLORS };

const pence = (amount: number) => `${amount}p`;

/** One pound, split between what you keep, tax and lost Pension Credit. */
export function PoundSplitBar({ split }: { split: PoundSplit }) {
  return (
    <SplitBar
      unit={pence}
      parts={[
        { key: "kept", amount: Math.max(split.kept, 0), name: "you keep", ink: "#1c1917" },
        { key: "tax", amount: Math.max(split.tax, 0), name: "income tax", ink: "#ffffff" },
        { key: "lost", amount: Math.max(split.lost, 0), name: "Pension Credit lost", ink: "#ffffff" },
      ]}
    />
  );
}

export function PoundSplitLegend({ showLost }: { showLost: boolean }) {
  return (
    <SplitLegend
      items={[
        { label: "You keep", color: SPLIT_COLORS.kept },
        { label: "Income tax", color: SPLIT_COLORS.tax },
        ...(showLost ? [{ label: "Pension Credit lost", color: SPLIT_COLORS.lost }] : []),
      ]}
    />
  );
}
