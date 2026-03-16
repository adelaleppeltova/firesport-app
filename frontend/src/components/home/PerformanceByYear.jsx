import { useMemo, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { useAthletePerformanceByYear } from "../../hooks/useApi";
import CardState from "./CardState";

const YEAR_STYLES = [
  { color: "#0f4d92", tone: "accent" },
  { color: "#cf362e", tone: "danger" },
  { color: "#2e7d32", tone: "positive" },
  { color: "#b26a1f", tone: "warning" },
];

export default function PerformanceByYear({ athleteId }) {
  const {
    data: performanceData,
    isLoading,
    error,
  } = useAthletePerformanceByYear(athleteId);
  const [view, setView] = useState("current"); // "current" | "recent"

  const currentYear = new Date().getFullYear();

  const chartData = useMemo(() => {
    if (!performanceData?.years?.length) return null;

    const { years, data } = performanceData;

    // Výběr zobrazených let podle přepínače
    let selectedYears;
    if (view === "current") {
      selectedYears = years.includes(currentYear)
        ? [currentYear]
        : [years[years.length - 1]];
    } else {
      const sorted = [...years].sort((a, b) => b - a);
      selectedYears = sorted.slice(0, 4).reverse();
    }

    const dateToDayOfYear = (dateStr) => {
      const d = new Date(dateStr);
      const start = new Date(d.getFullYear(), 0, 0);
      return Math.floor((d - start) / (1000 * 60 * 60 * 24));
    };

    const yearLines = {};
    const allTimes = [];
    const allX = [];

    selectedYears.forEach((year) => {
      yearLines[year] = (data[year] || []).map((d) => {
        const time = parseFloat(d.time.toFixed(2));
        const x = dateToDayOfYear(d.date);
        allTimes.push(time);
        allX.push(x);
        return { x, time, date: d.date, place: d.place ?? null };
      });
    });

    if (!allTimes.length) return null;

    const minTime = Math.min(...allTimes);
    const maxTime = Math.max(...allTimes);
    const timePadding = (maxTime - minTime) * 0.08 || 0.5;
    const minX = Math.min(...allX);
    const maxX = Math.max(...allX);
    const xPadding = Math.max(3, Math.round((maxX - minX) * 0.05));

    const yearColors = {};
    selectedYears.forEach((year, idx) => {
      yearColors[year] = YEAR_STYLES[idx % YEAR_STYLES.length];
      yearLines[year] = yearLines[year].map((point) => ({
        ...point,
        tone: yearColors[year].tone,
      }));
    });

    return {
      yearLines,
      years: selectedYears,
      colors: yearColors,
      minTime: parseFloat((minTime - timePadding).toFixed(1)),
      maxTime: parseFloat((maxTime + timePadding).toFixed(1)),
      xDomain: [minX - xPadding, maxX + xPadding],
    };
  }, [performanceData, view, currentYear]);

  if (isLoading) return <div className="skeleton skeleton--chart" />;
  if (error) return <CardState type="error" />;
  if (!performanceData?.years?.length) {
    return (
      <CardState
        type="insufficient"
        text="Nedostatek dat pro zobrazení grafu."
      />
    );
  }
  if (!chartData) {
    return (
      <CardState
        type="no-data"
        text="Pro vybranou sezónu nejsou žádné záznamy."
      />
    );
  }

  const { yearLines, years, colors, minTime, maxTime, xDomain } = chartData;

  const dayOfYearToLabel = (day) => {
    const d = new Date(2000, 0, day);
    return `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}.`;
  };

  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    const point = payload[0].payload;
    return (
      <div
        className={`performance-by-year__tooltip performance-by-year__tooltip--${point.tone ?? "accent"}`}
      >
        <p className="performance-by-year__tooltip-time">
          {point.time.toFixed(2)}s
        </p>
        {point.place && (
          <p className="performance-by-year__tooltip-detail">{point.place}</p>
        )}
        <p className="performance-by-year__tooltip-detail">
          {new Date(point.date).toLocaleDateString("cs-CZ")}
        </p>
      </div>
    );
  };

  return (
    <div className="performance-by-year">
      {/* Přepínač sezóna / poslední roky */}
      <div className="performance-by-year__toggle">
        <button
          className={`performance-by-year__toggle-btn${view === "current" ? " performance-by-year__toggle-btn--active" : ""}`}
          onClick={() => setView("current")}
        >
          Aktuální sezóna
        </button>
        <button
          className={`performance-by-year__toggle-btn${view === "recent" ? " performance-by-year__toggle-btn--active" : ""}`}
          onClick={() => setView("recent")}
        >
          Poslední roky
        </button>
      </div>

      {/* Graf */}
      <ResponsiveContainer width="100%" height={280}>
        <LineChart margin={{ top: 8, right: 20, left: 8, bottom: 32 }}>
          <CartesianGrid strokeDasharray="4,4" stroke="#e0e0e0" />
          <XAxis
            type="number"
            dataKey="x"
            domain={xDomain}
            tickFormatter={dayOfYearToLabel}
            stroke="#636363"
            tick={{ fontSize: 10, angle: 0, textAnchor: "middle" }}
            height={42}
            label={{
              value: "Datum",
              position: "bottom",
              offset: 8,
              fontSize: 12,
            }}
          />
          <YAxis
            reversed={false}
            domain={[minTime, maxTime]}
            tickFormatter={(v) => `${v.toFixed(1)}s`}
            stroke="#636363"
            tick={{ fontSize: 10 }}
            width={54}
            label={{
              value: "Čas (s)",
              angle: -90,
              position: "left",
              offset: 0,
              fontSize: 12,
            }}
          />
          <Tooltip content={<CustomTooltip />} isAnimationActive={false} />
          {years.map((year) => (
            <Line
              key={year}
              data={yearLines[year]}
              type="linear"
              dataKey="time"
              name={String(year)}
              stroke={colors[year].color}
              strokeWidth={2}
              dot={{ r: 3, fill: colors[year].color }}
              activeDot={{ r: 5 }}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
      {/* Legenda – jen pokud je víc let */}
      {years.length > 1 && (
        <div className="performance-by-year__legend">
          {years.map((year) => (
            <span key={year} className="performance-by-year__legend-item">
              <span
                className={`performance-by-year__legend-dot performance-by-year__legend-dot--${colors[year].tone}`}
              />
              {year}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
