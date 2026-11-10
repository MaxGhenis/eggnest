import { IconArrowDownRight } from "@tabler/icons-react";
import type { USDrawdownOutcome, USDrawdownSlice } from "../../lib/api-us-drawdown";
import {
  benefitsMoving,
  describeDollar,
  describeStep,
  ladderRange,
  ladderRows,
  outcomeAt,
  splitCents,
} from "../../lib/us-drawdown";
import { Ladder } from "../drawdown/Ladder";
import { SPLIT_COLORS } from "../drawdown/SplitBar";
import { DollarSplitBar, DollarSplitLegend } from "./DollarSplitBar";

/** The draw amounts where each extra dollar changes hands, lowest first. */
export function DollarLadder({
  bands,
  sweep,
  draw,
  balance,
}: {
  bands: USDrawdownSlice[];
  sweep: USDrawdownOutcome[];
  draw: number;
  balance: number;
}) {
  const rows = ladderRows(bands);
  const showLost = rows.some((row) => !row.step && splitCents(row).lost > 0);
  return (
    <Ladder
      heading="Where each extra dollar goes"
      legend={<DollarSplitLegend showLost={showLost} />}
      bands={rows}
      draw={draw}
      range={(index) => ladderRange(rows, index, balance)}
      row={(row) => {
        const from = outcomeAt(sweep, row.draw_from);
        const to = outcomeAt(sweep, row.draw_to);
        if (row.step) {
          return (
            <p className="flex items-start gap-2 text-[0.95rem]">
              <IconArrowDownRight
                aria-hidden="true"
                size={20}
                className="mt-0.5 shrink-0"
                style={{ color: SPLIT_COLORS.lost }}
              />
              {describeStep(from, to)}
            </p>
          );
        }
        return (
          <>
            <DollarSplitBar split={splitCents(row)} />
            <p className="mt-1.5 text-[0.95rem]">{describeDollar(row, benefitsMoving(from, to))}</p>
          </>
        );
      }}
    />
  );
}
