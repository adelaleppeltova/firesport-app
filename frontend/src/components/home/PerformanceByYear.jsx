import { useMemo, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { useMe, useAthletePerformanceByYear } from "../../hooks/useApi";

export default function PerformanceByYear() {
  const { data: me, isLoading: meLoading } = useMe();
  const { data: performanceData, isLoading: dataLoading } =
    useAthletePerformanceByYear(me?.athlete_id);
  const [selectedYear, setSelectedYear] = useState(null);

  // Dynamické generování barev pro každý rok
  const generateColors = (count) => {
    const baseColors = [
      "#2196F3", // modrá
      "#FF6B6B", // červená
      "#4CAF50", // zelená
      "#FF9800", // oranžová
      "#9C27B0", // fialová
      "#00BCD4", // cyan
      "#FF5722", // deep orange
      "#3F51B5", // indigo
      "#009688", // teal
      "#FFEB3B", // amber
    ];

    if (count <= baseColors.length) {
      return baseColors.slice(0, count);
    }

    const colors = [...baseColors];
    for (let i = baseColors.length; i < count; i++) {
      const hue = ((i * 360) / count) % 360;
      colors.push(`hsl(${hue}, 70%, 60%)`);
    }
    return colors;
  };

  // Transformuj data do formátu pro Recharts
  const chartData = useMemo(() => {
    if (!performanceData || !performanceData.years.length) return null;

    const { years, data } = performanceData;
    const colors = generateColors(years.length);
    const yearToColor = {};
    years.forEach((year, idx) => {
      yearToColor[year] = colors[idx];
    });

    // Převod data na den roku (1–365), aby každá tečka seděla na správné X pozici
    const dateToDayOfYear = (dateStr) => {
      const d = new Date(dateStr);
      const start = new Date(d.getFullYear(), 0, 0);
      return Math.floor((d - start) / (1000 * 60 * 60 * 24));
    };

    // Každý rok má vlastní pole bodů { x, time, date, place }
    const yearLines = {};
    let allTimes = [];
    let allX = [];

    years.forEach((year) => {
      yearLines[year] = (data[year] || []).map((d) => {
        const time = parseFloat(d.time.toFixed(2));
        const x = dateToDayOfYear(d.date);
        allTimes.push(time);
        allX.push(x);
        return {
          x,
          time,
          date: d.date,
          place: d.place ?? null,
        };
      });
    });

    // Omezení osy Y na rozmezí dat závodníka + malý padding
    const minTime = Math.min(...allTimes);
    const maxTime = Math.max(...allTimes);
    const timePadding = (maxTime - minTime) * 0.05;

    // Omezení osy X na rozmezí dat závodníka + malý padding
    const minX = Math.min(...allX);
    const maxX = Math.max(...allX);
    const xPadding = Math.max(3, Math.round((maxX - minX) * 0.05));

    return {
      yearLines,
      years,
      colors: yearToColor,
      minTime: parseFloat((minTime - timePadding).toFixed(1)),
      maxTime: parseFloat((maxTime + timePadding).toFixed(1)),
      xDomain: [minX - xPadding, maxX + xPadding],
    };
  }, [performanceData]);

  if (meLoading || dataLoading) return <div className="skeleton" />;
  if (!chartData || !chartData.years.length) {
    return <p className="empty-state">Nedostatek dat pro graf</p>;
  }

  const { yearLines, years, colors, minTime, maxTime, xDomain } = chartData;

  // Převod dne roku zpět na DD.MM. pro popisky osy X
  const dayOfYearToLabel = (day) => {
    const d = new Date(2000, 0, day); // rok 2000 (přestupný) pro správný výpočet
    const dd = String(d.getDate()).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    return `${dd}.${mm}.`;
  };

  const CustomTooltip = ({ active, payload }) => {
    if (
      active &&
      payload &&
      payload.length &&
      (selectedYear === null || selectedYear === payload[0].name)
    ) {
      const point = payload[0].payload;
      return (
        <div
          className="performance-by-year__custom-tooltip"
          style={{
            backgroundColor: payload[0].color,
            color: "white",
            padding: "8px 12px",
            borderRadius: "6px",
            boxShadow: "0 2px 6px rgba(0,0,0,0.25)",
          }}
        >
          <p
            style={{
              margin: "0 0 2px 0",
              fontWeight: "bold",
              fontSize: "15px",
            }}
          >
            {point.time.toFixed(2)}s
          </p>
          {point.place && (
            <p style={{ margin: "0 0 2px 0", fontSize: "13px" }}>
              {point.place}
            </p>
          )}
          <p style={{ margin: 0, fontSize: "13px" }}>
            {new Date(point.date).toLocaleDateString("cs-CZ")}
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="performance-by-year">
      <div className="performance-by-year__container">
        <ResponsiveContainer width="100%" height={360}>
          <LineChart margin={{ top: 10, right: 16, left: 0, bottom: 50 }}>
            <CartesianGrid
              strokeDasharray="4,4"
              stroke="#797979"
              strokeWidth={1.5}
            />
            <XAxis
              type="number"
              dataKey="x"
              domain={xDomain}
              tickFormatter={dayOfYearToLabel}
              stroke="#666"
              tick={{ fontSize: 11, angle: -30, textAnchor: "end" }}
              height={50}
              label={{
                value: "Datum",
                position: "insideBottom",
                offset: -5,
                fontSize: 13,
              }}
            />
            <YAxis
              reversed={true}
              domain={[minTime, maxTime]}
              tickFormatter={(v) => `${v.toFixed(1)}s`}
              stroke="#333"
              tick={{ fontSize: 11 }}
              width={48}
              label={{
                value: "Čas (s)",
                angle: -90,
                position: "insideLeft",
                offset: 4,
                fontSize: 13,
              }}
            />
            <Tooltip content={<CustomTooltip />} isAnimationActive={false} />
            <Legend
              wrapperStyle={{ bottom: -5 }}
              content={({ payload }) => (
                <div
                  style={{
                    display: "flex",
                    justifyContent: "center",
                    flexWrap: "wrap",
                    gap: "6px 14px",
                    paddingTop: "12px",
                    fontSize: "13px",
                    cursor: "pointer",
                  }}
                >
                  {payload.map((entry) => {
                    const inactive =
                      selectedYear !== null && selectedYear !== entry.value;
                    return (
                      <div
                        key={entry.value}
                        onClick={() =>
                          setSelectedYear((prev) =>
                            prev === entry.value ? null : entry.value,
                          )
                        }
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "6px",
                          color: inactive ? "#aaa" : "inherit",
                        }}
                      >
                        <span
                          style={{
                            display: "inline-block",
                            width: "10px",
                            height: "10px",
                            borderRadius: "50%",
                            backgroundColor: inactive ? "#aaa" : entry.color,
                            flexShrink: 0,
                          }}
                        />
                        {entry.value}
                      </div>
                    );
                  })}
                </div>
              )}
            />

            {years.map((year) => {
              const isActive =
                selectedYear === null || selectedYear === String(year);
              return (
                <Line
                  key={`line-${year}`}
                  data={yearLines[year]}
                  type="linear"
                  dataKey="time"
                  name={String(year)}
                  stroke={colors[year]}
                  strokeWidth={isActive ? 2 : 1}
                  strokeOpacity={isActive ? 1 : 0.2}
                  dot={{
                    r: 2,
                    fill: colors[year],
                    fillOpacity: isActive ? 1 : 0.2,
                  }}
                  activeDot={isActive ? { r: 4 } : false}
                  isAnimationActive={false}
                />
              );
            })}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
