import { IconArrowDownRight } from "@tabler/icons-react";
import type { DrawdownBand, DrawdownOutcome } from "../../lib/api-uk-drawdown";
import {
  describePound,
  describeStep,
  ladderRange,
  ladderRows,
  outcomeAt,
  splitPence,
} from "../../lib/uk-drawdown";
import { Ladder } from "../drawdown/Ladder";
import { SPLIT_COLORS } from "../drawdown/SplitBar";
import { PoundSplitBar, PoundSplitLegend } from "./PoundSplitBar";

/**
 * The draw amounts where each extra pound changes hands, lowest first. A band
 * the API marks as a jump shows what changes all at once there.
 */
export function PoundLadder({
  bands,
  sweep,
  draw,
  balance,
}: {
  bands: DrawdownBand[];
  sweep: DrawdownOutcome[];
  draw: number;
  balance: number;
}) {
  const rows = ladderRows(bands);
  const showLost = rows.some((row) => !row.step && splitPence(row).lost > 0);
  return (
    <Ladder
      heading="Where each extra pound goes"
      legend={<PoundSplitLegend showLost={showLost} />}
      bands={rows}
      draw={draw}
      range={(index) => ladderRange(rows, index, balance)}
      row={(row) =>
        row.step ? (
          <p className="flex items-start gap-2 text-[0.95rem]">
            <IconArrowDownRight
              aria-hidden="true"
              size={20}
              className="mt-0.5 shrink-0"
              style={{ color: SPLIT_COLORS.tax }}
            />
            {describeStep(outcomeAt(sweep, row.draw_from), outcomeAt(sweep, row.draw_to))}
          </p>
        ) : (
          <>
            <PoundSplitBar split={splitPence(row)} />
            <p className="mt-1.5 text-[0.95rem]">{describePound(row)}</p>
          </>
        )
      }
    />
  );
}
