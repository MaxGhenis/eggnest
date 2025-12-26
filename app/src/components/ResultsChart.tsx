import {
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Area,
  ComposedChart,
} from "recharts";
import type { SimulationResult } from "../lib/api";

interface ResultsChartProps {
  result: SimulationResult;
  startAge?: number;
  onYearClick?: (yearIndex: number) => void;
}

interface ChartDataPoint {
  year: number;
  age: number;
  p5: number;
  p25: number;
  p50: number;
  p75: number;
  p95: number;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ payload: ChartDataPoint }>;
  label?: number;
}

function formatCurrency(value: number): string {
  if (Math.abs(value) >= 1000000) {
    return `$${(value / 1000000).toFixed(1)}M`;
  }
  if (Math.abs(value) >= 1000) {
    return `$${(value / 1000).toFixed(0)}K`;
  }
  return `$${value.toFixed(0)}`;
}

// Custom tooltip component
function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;

  // Extract all percentile values from payload
  const data = payload[0]?.payload as ChartDataPoint | undefined;
  if (!data) return null;

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
        Age {data.age} (Year {data.year + 1})
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "13px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: "16px" }}>
          <span style={{ color: "#9a3412" }}>95th:</span>
          <span style={{ fontWeight: 500 }}>{formatCurrency(data.p95)}</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", gap: "16px" }}>
          <span style={{ color: "#c2410c" }}>75th:</span>
          <span style={{ fontWeight: 500 }}>{formatCurrency(data.p75)}</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", gap: "16px", fontWeight: 600 }}>
          <span style={{ color: "#d97706" }}>Median:</span>
          <span>{formatCurrency(data.p50)}</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", gap: "16px" }}>
          <span style={{ color: "#c2410c" }}>25th:</span>
          <span style={{ fontWeight: 500 }}>{formatCurrency(data.p25)}</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", gap: "16px" }}>
          <span style={{ color: "#9a3412" }}>5th:</span>
          <span style={{ fontWeight: 500 }}>{formatCurrency(data.p5)}</span>
        </div>
      </div>
    </div>
  );
}

export function ResultsChart({ result, startAge = 65, onYearClick }: ResultsChartProps) {
  // Transform percentile paths into chart data with age
  const chartData: ChartDataPoint[] = result.percentile_paths.p50.map((_, index) => ({
    year: index,
    age: startAge + index,
    p5: result.percentile_paths.p5[index],
    p25: result.percentile_paths.p25[index],
    p50: result.percentile_paths.p50[index],
    p75: result.percentile_paths.p75[index],
    p95: result.percentile_paths.p95[index],
  }));

  return (
    <div className="results-chart">
      <h3>Portfolio Value Over Time</h3>
      <p style={{ fontSize: "0.8rem", color: "#78716c", margin: "0 0 0.5rem 0" }}>
        {onYearClick ? "Click on the chart to see year details. " : ""}
        Click legend items to toggle visibility.
      </p>
      <ResponsiveContainer width="100%" height={420}>
        <ComposedChart
          data={chartData}
          margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
          onClick={(e) => {
            if (onYearClick && e && e.activeTooltipIndex != null) {
              onYearClick(e.activeTooltipIndex as number);
            }
          }}
          style={{ cursor: onYearClick ? "pointer" : "default" }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e7e5e4" />
          <XAxis
            dataKey="age"
            label={{ value: "Age", position: "insideBottom", offset: -5, style: { fontFamily: "Inter, system-ui, sans-serif" } }}
            tick={{ fontFamily: "Inter, system-ui, sans-serif", fontSize: 12 }}
          />
          <YAxis
            tickFormatter={formatCurrency}
            label={{ value: "Portfolio Value", angle: -90, position: "insideLeft", style: { fontFamily: "Inter, system-ui, sans-serif" } }}
            tick={{ fontFamily: "Inter, system-ui, sans-serif", fontSize: 12 }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ fontFamily: "Inter, system-ui, sans-serif", fontSize: "11px" }}
            onClick={(e) => {
              // Legend click toggles visibility - handled by Recharts automatically
              console.log("Legend clicked:", e.dataKey);
            }}
          />

          {/* Confidence band: 5th to 95th percentile */}
          <Area
            type="monotone"
            dataKey="p95"
            stroke="rgba(217, 119, 6, 0.4)"
            strokeWidth={1}
            strokeDasharray="4 4"
            fill="rgba(217, 119, 6, 0.08)"
            name="95th Percentile"
            legendType="line"
          />
          <Area
            type="monotone"
            dataKey="p5"
            stroke="rgba(217, 119, 6, 0.4)"
            strokeWidth={1}
            strokeDasharray="4 4"
            fill="white"
            name="5th Percentile"
            legendType="line"
          />

          {/* Interquartile range */}
          <Line
            type="monotone"
            dataKey="p75"
            stroke="rgba(217, 119, 6, 0.6)"
            strokeWidth={1.5}
            dot={false}
            name="75th Percentile"
            activeDot={{ r: 4, fill: "#c2410c" }}
          />
          <Line
            type="monotone"
            dataKey="p25"
            stroke="rgba(217, 119, 6, 0.6)"
            strokeWidth={1.5}
            dot={false}
            name="25th Percentile"
            activeDot={{ r: 4, fill: "#c2410c" }}
          />

          {/* Median */}
          <Line
            type="monotone"
            dataKey="p50"
            stroke="#d97706"
            strokeWidth={3}
            dot={false}
            name="Median (50th)"
            activeDot={{ r: 6, fill: "#d97706", stroke: "white", strokeWidth: 2 }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
