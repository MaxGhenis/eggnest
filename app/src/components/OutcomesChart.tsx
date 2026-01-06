import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Area,
  AreaChart,
} from "recharts";
import type { OutcomePaths } from "../lib/api";

interface OutcomesChartProps {
  outcomePaths: OutcomePaths;
  startAge?: number;
}

interface ChartDataPoint {
  age: number;
  died_with_money: number;
  died_broke: number;
  alive_with_money: number;
  alive_broke: number;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    dataKey: string;
    value: number;
    color: string;
    name: string;
  }>;
  label?: number;
}

// Custom tooltip component
function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;

  // Sort by display order (bottom to top of stack)
  const orderedPayload = [...payload].reverse();

  return (
    <div
      style={{
        backgroundColor: "white",
        border: "1px solid #d6d3d1",
        borderRadius: "8px",
        padding: "12px 16px",
        boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1)",
        fontFamily: "Inter, system-ui, sans-serif",
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: "8px", fontSize: "14px" }}>
        Age {label}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "13px" }}>
        {orderedPayload.map((entry) => (
          <div
            key={entry.dataKey}
            style={{
              display: "flex",
              justifyContent: "space-between",
              gap: "16px",
              alignItems: "center"
            }}
          >
            <span style={{
              display: "flex",
              alignItems: "center",
              gap: "6px"
            }}>
              <span
                style={{
                  width: "10px",
                  height: "10px",
                  backgroundColor: entry.color,
                  borderRadius: "2px",
                  display: "inline-block"
                }}
              />
              {entry.name}:
            </span>
            <span style={{ fontWeight: 500 }}>
              {entry.value.toFixed(1)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function OutcomesChart({ outcomePaths, startAge = 65 }: OutcomesChartProps) {
  // Transform outcome paths into chart data
  const chartData: ChartDataPoint[] = outcomePaths.died_with_money.map((_, index) => ({
    age: startAge + index,
    died_with_money: outcomePaths.died_with_money[index],
    died_broke: outcomePaths.died_broke[index],
    alive_with_money: outcomePaths.alive_with_money[index],
    alive_broke: outcomePaths.alive_broke[index],
  }));

  // Colors for the chart areas
  // Stack order (bottom to top): died_with_money, died_broke, alive_broke, alive_with_money
  const colors = {
    died_with_money: "#22c55e",  // Green - success outcome
    died_broke: "#ef4444",        // Red - failure outcome
    alive_with_money: "#86efac",  // Light green - still going strong
    alive_broke: "#fca5a5",       // Light red - alive but depleted
  };

  return (
    <div className="outcomes-chart">
      <h3>Outcome Distribution Over Time</h3>
      <p style={{ fontSize: "0.8rem", color: "#78716c", margin: "0 0 0.5rem 0" }}>
        Shows cumulative outcomes at each age accounting for mortality.
      </p>
      <ResponsiveContainer width="100%" height={380}>
        <AreaChart
          data={chartData}
          margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
          stackOffset="none"
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e7e5e4" />
          <XAxis
            dataKey="age"
            label={{
              value: "Age",
              position: "insideBottom",
              offset: -5,
              style: { fontFamily: "Inter, system-ui, sans-serif" }
            }}
            tick={{ fontFamily: "Inter, system-ui, sans-serif", fontSize: 12 }}
          />
          <YAxis
            domain={[0, 100]}
            tickFormatter={(value) => `${value}%`}
            label={{
              value: "Percentage of Simulations",
              angle: -90,
              position: "insideLeft",
              style: { fontFamily: "Inter, system-ui, sans-serif" }
            }}
            tick={{ fontFamily: "Inter, system-ui, sans-serif", fontSize: 12 }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ fontFamily: "Inter, system-ui, sans-serif", fontSize: "11px" }}
            formatter={(value) => {
              const labels: Record<string, string> = {
                died_with_money: "Died with Money",
                died_broke: "Ran Out Before Death",
                alive_with_money: "Alive with Money",
                alive_broke: "Alive but Depleted",
              };
              return labels[value] || value;
            }}
          />

          {/* Stack order matters - bottom to top */}
          <Area
            type="monotone"
            dataKey="died_with_money"
            stackId="1"
            stroke={colors.died_with_money}
            fill={colors.died_with_money}
            fillOpacity={0.8}
            name="died_with_money"
          />
          <Area
            type="monotone"
            dataKey="died_broke"
            stackId="1"
            stroke={colors.died_broke}
            fill={colors.died_broke}
            fillOpacity={0.8}
            name="died_broke"
          />
          <Area
            type="monotone"
            dataKey="alive_broke"
            stackId="1"
            stroke={colors.alive_broke}
            fill={colors.alive_broke}
            fillOpacity={0.8}
            name="alive_broke"
          />
          <Area
            type="monotone"
            dataKey="alive_with_money"
            stackId="1"
            stroke={colors.alive_with_money}
            fill={colors.alive_with_money}
            fillOpacity={0.8}
            name="alive_with_money"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
