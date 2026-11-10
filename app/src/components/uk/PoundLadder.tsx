import type { DrawdownSlice } from "../../lib/api-uk-drawdown";
import { bandRange, describePound, splitPence } from "../../lib/uk-drawdown";
import { Ladder } from "../drawdown/Ladder";
import { PoundSplitBar, PoundSplitLegend } from "./PoundSplitBar";

/** The draw amounts where each extra pound changes hands, lowest first. */
export function PoundLadder({
  bands,
  draw,
  balance,
}: {
  bands: DrawdownSlice[];
  draw: number;
  balance: number;
}) {
  const showLost = bands.some((band) => splitPence(band).lost > 0);
  return (
    <Ladder
      heading="Where each extra pound goes"
      legend={<PoundSplitLegend showLost={showLost} />}
      bands={bands}
      draw={draw}
      range={(index) => bandRange(bands, index, balance)}
      row={(band) => (
        <>
          <PoundSplitBar split={splitPence(band)} />
          <p className="mt-1.5 text-[0.95rem]">{describePound(band)}</p>
        </>
      )}
    />
  );
}
