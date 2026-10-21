import {
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
  Legend,
} from "recharts";
const colors = ["#245de0", "#16a085", "#bf7724"];
export default function CalibrationChart({ curves }) {
  const entries = Object.entries(curves).filter(([, values]) => values.length);
  if (!entries.length)
    return (
      <p className="flex h-72 items-center justify-center text-sm text-muted">
        No answered trials to plot.
      </p>
    );
  return (
    <div
      className="h-80 w-full"
      role="img"
      aria-label="Calibration plot: confidence against accuracy, with a perfect-calibration diagonal"
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart margin={{ top: 20, right: 25, left: 8, bottom: 24 }}>
          <CartesianGrid stroke="#e8edf3" strokeDasharray="3 3" />
          <XAxis
            type="number"
            dataKey="x"
            domain={[0, 100]}
            ticks={[0, 20, 40, 60, 80, 100]}
            tick={{ fontSize: 11 }}
            label={{
              value: "Mean confidence (%)",
              position: "bottom",
              offset: 5,
            }}
          />
          <YAxis
            type="number"
            dataKey="y"
            domain={[0, 100]}
            ticks={[0, 20, 40, 60, 80, 100]}
            tick={{ fontSize: 11 }}
            label={{
              value: "Correct (%)",
              angle: -90,
              position: "insideLeft",
              offset: 0,
            }}
          />
          <Tooltip
            formatter={(v, name, info) => [
              `${Number(v).toFixed(1)}${name === "n" ? "" : "%"}`,
              name,
            ]}
            labelFormatter={() => "Calibration bin"}
          />
          <Legend verticalAlign="top" height={28} />
          <Line
            name="Perfect calibration"
            data={[
              { x: 0, y: 0 },
              { x: 100, y: 100 },
            ]}
            dataKey="y"
            stroke="#a8b4c4"
            strokeDasharray="5 5"
            dot={false}
            isAnimationActive={false}
          />
          {entries.map(([label, values], i) => (
            <Scatter
              isAnimationActive={false}
              key={label}
              name={label}
              data={values.map((v) => ({
                x: v.confidence,
                y: v.accuracy * 100,
                n: v.n,
              }))}
              fill={colors[i % colors.length]}
              line
              shape={(p) => (
                <g>
                  <circle
                    cx={p.cx}
                    cy={p.cy}
                    r={5 + Math.min(5, Math.sqrt(p.payload.n))}
                    fill={colors[i % colors.length]}
                    stroke="white"
                    strokeWidth={2}
                  />
                  <text
                    x={p.cx}
                    y={p.cy - 13}
                    textAnchor="middle"
                    fill={colors[i % colors.length]}
                    fontSize={10}
                  >
                    {p.payload.n}
                  </text>
                </g>
              )}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
