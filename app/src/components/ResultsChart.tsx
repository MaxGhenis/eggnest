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
}

function formatCurrency(value: number): string {
  if (value >= 1000000) {
    return `$${(value / 1000000).toFixed(1)}M`;
  }
  if (value >= 1000) {
    return `$${(value / 1000).toFixed(0)}K`;
  }
  return `$${value.toFixed(0)}`;
}

export function ResultsChart({ result }: ResultsChartProps) {
  // Transform percentile paths into chart data
  const chartData = result.percentile_paths.p50.map((_, index) => ({
    year: index,
    p5: result.percentile_paths.p5[index],
    p25: result.percentile_paths.p25[index],
    p50: result.percentile_paths.p50[index],
    p75: result.percentile_paths.p75[index],
    p95: result.percentile_paths.p95[index],
  }));

  return (
    <div className="results-chart">
      <h3>Portfolio Value Over Time</h3>
      <ResponsiveContainer width="100%" height={400}>
        <ComposedChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="year"
            label={{ value: "Years", position: "insideBottom", offset: -5 }}
          />
          <YAxis
            tickFormatter={formatCurrency}
            label={{ value: "Portfolio Value", angle: -90, position: "insideLeft" }}
          />
          <Tooltip
            formatter={(value: number) => formatCurrency(value)}
            labelFormatter={(label) => `Year ${label}`}
          />
          <Legend />

          {/* Confidence band: 5th to 95th percentile */}
          <Area
            type="monotone"
            dataKey="p95"
            stroke="none"
            fill="#fef3c7"
            name="95th percentile"
          />
          <Area
            type="monotone"
            dataKey="p5"
            stroke="none"
            fill="#ffffff"
            name="5th percentile"
          />

          {/* Interquartile range */}
          <Line
            type="monotone"
            dataKey="p75"
            stroke="#f59e0b"
            strokeWidth={1}
            dot={false}
            name="75th percentile"
          />
          <Line
            type="monotone"
            dataKey="p25"
            stroke="#f59e0b"
            strokeWidth={1}
            dot={false}
            name="25th percentile"
          />

          {/* Median */}
          <Line
            type="monotone"
            dataKey="p50"
            stroke="#d97706"
            strokeWidth={3}
            dot={false}
            name="Median"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
