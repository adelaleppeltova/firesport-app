import { useState } from "react";
import { useMe, useAthletePerformanceByYear } from "../../hooks/useApi";

export default function PerformanceByYear() {
  const { data: me, isLoading: meLoading } = useMe();
  const { data: performanceData, isLoading: dataLoading } =
    useAthletePerformanceByYear(me?.athlete_id);
  const [hoveredPoint, setHoveredPoint] = useState(null);

  if (meLoading || dataLoading) return <div className="skeleton" />;
  if (!performanceData || performanceData.years.length === 0) {
    return <p className="empty-state">Nedostatek dat pro graf</p>;
  }

  const { years, data } = performanceData;

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

    // Pokud je více let než barev, generuj dynamicky
    const colors = [...baseColors];
    for (let i = baseColors.length; i < count; i++) {
      const hue = ((i * 360) / count) % 360;
      colors.push(`hsl(${hue}, 70%, 60%)`);
    }
    return colors;
  };

  const colors = generateColors(years.length);

  // Najdi min a max čas pro Y osu
  let allTimes = [];
  years.forEach((year) => {
    if (data[year]) {
      allTimes = allTimes.concat(data[year].map((d) => d.time));
    }
  });

  const minTime = Math.min(...allTimes);
  const maxTime = Math.max(...allTimes);
  const padding = (maxTime - minTime) * 0.1;
  const yMin = minTime - padding;
  const yMax = maxTime + padding;

  // SVG rozměry
  const svgWidth = 800;
  const svgHeight = 400;
  const chartWidth = svgWidth - 80;
  const chartHeight = svgHeight - 60;
  const chartX = 50;
  const chartY = 20;

  // Převeď čas na Y souřadnici (invertovaná osa - lepší časy výše)
  const timeToY = (time) => {
    const ratio = (time - yMin) / (yMax - yMin);
    return chartY + chartHeight * ratio; // Invertovaná: ratio bez (1 - ratio)
  };

  // Převeď index bodu na X souřadnici
  const pointToX = (index, totalPoints) => {
    if (totalPoints === 1) {
      return chartX + chartWidth / 2;
    }
    return chartX + (index / (totalPoints - 1)) * chartWidth;
  };

  // Vytvořit SVG path pro linku
  const createPath = (points) => {
    if (points.length === 0) return "";
    return "M " + points.map(([x, y]) => `${x},${y}`).join(" L ");
  };

  return (
    <div className="performance-by-year">
      <div className="performance-by-year__container">
        <svg
          className="performance-by-year__chart"
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          width="100%"
          preserveAspectRatio="xMidYMid meet"
        >
          {/* Mřížka Y */}
          {[0, 0.25, 0.5, 0.75, 1].map((ratio, i) => {
            const y = chartY + chartHeight * (1 - ratio);
            const value = yMax - (yMax - yMin) * ratio;
            return (
              <g key={`grid-${i}`} className="performance-by-year__grid-line">
                <line
                  x1={chartX}
                  y1={y}
                  x2={chartX + chartWidth}
                  y2={y}
                  stroke="#797979"
                  strokeDasharray="4,4"
                  strokeWidth="1.5"
                />
                <text
                  x={chartX - 10}
                  y={y + 4}
                  textAnchor="end"
                  fontSize="17"
                  fill="#333"
                  fontWeight="500"
                >
                  {value.toFixed(1)}s
                </text>
              </g>
            );
          })}

          {/* Osy */}
          <line
            x1={chartX}
            y1={chartY}
            x2={chartX}
            y2={chartY + chartHeight}
            stroke="#333"
            strokeWidth="2"
          />
          <line
            x1={chartX}
            y1={chartY + chartHeight}
            x2={chartX + chartWidth}
            y2={chartY + chartHeight}
            stroke="#333"
            strokeWidth="2"
          />

          {/* Linky pro každý rok */}
          {years.map((year, yearIndex) => {
            const yearData = data[year] || [];
            const color = colors[yearIndex];

            const points = yearData.map((d, i) => [
              pointToX(i, yearData.length),
              timeToY(d.time),
            ]);

            return (
              <g key={`year-${year}`}>
                {/* Linka */}
                <path
                  d={createPath(points)}
                  stroke={color}
                  strokeWidth="2"
                  fill="none"
                  className="performance-by-year__line"
                />

                {/* Body */}
                {yearData.map((d, i) => {
                  const [x, y] = points[i];
                  const pointId = `${year}-${i}`;
                  const isHovered = hoveredPoint === pointId;

                  // Vypočítej optimální pozici tooltipů s ohledem na okraje
                  let tooltipX = x - 65;

                  // Pokud by tooltip vyjel z levého okraje
                  if (tooltipX < chartX + 5) {
                    tooltipX = chartX + 5;
                  }
                  // Pokud by vyjel z pravého okraje
                  else if (tooltipX + 130 > chartX + chartWidth - 5) {
                    tooltipX = chartX + chartWidth - 135;
                  }

                  return (
                    <g
                      key={pointId}
                      onMouseEnter={() => setHoveredPoint(pointId)}
                      onMouseLeave={() => setHoveredPoint(null)}
                      className="performance-by-year__point-group"
                    >
                      <circle
                        cx={x}
                        cy={y}
                        r={isHovered ? 7 : 4}
                        fill={color}
                        className="performance-by-year__point"
                        style={{ cursor: "pointer" }}
                      />
                      {isHovered && (
                        <g className="performance-by-year__tooltip">
                          <rect
                            x={tooltipX}
                            y={y - 55}
                            width="130"
                            height="60"
                            rx="6"
                            fill={color}
                            opacity="0.95"
                            filter="drop-shadow(0 2px 6px rgba(0,0,0,0.25))"
                          />
                          <text
                            x={tooltipX + 65}
                            y={y - 28}
                            textAnchor="middle"
                            fill="white"
                            fontSize="17"
                            fontWeight="bold"
                          >
                            {d.time.toFixed(2)}s
                          </text>
                          <text
                            x={tooltipX + 65}
                            y={y - 10}
                            textAnchor="middle"
                            fill="white"
                            fontSize="15"
                          >
                            {new Date(d.date).toLocaleDateString("cs-CZ")}
                          </text>
                        </g>
                      )}
                    </g>
                  );
                })}
              </g>
            );
          })}

          {/* Popisky na X ose (datumy) */}
          {years.map((year) => {
            const yearData = data[year] || [];
            if (yearData.length === 0) return null;

            // Zobraz datumy: první, poslední a případně jeden uprostřed
            const indicesToShow = [];
            if (yearData.length > 0) {
              indicesToShow.push(0); // první
              if (yearData.length > 2) {
                indicesToShow.push(Math.floor((yearData.length - 1) / 2)); // uprostřed
              }
              if (yearData.length > 1) {
                indicesToShow.push(yearData.length - 1); // poslední
              }
            }

            return indicesToShow.map((idx) => {
              if (idx >= yearData.length) return null;
              const d = yearData[idx];
              const x = pointToX(idx, yearData.length);
              const dateObj = new Date(d.date);
              const day = String(dateObj.getDate()).padStart(2, "0");
              const month = String(dateObj.getMonth() + 1).padStart(2, "0");
              const dateStr = `${day}.${month}.`;

              return (
                <text
                  key={`x-label-${year}-${idx}`}
                  x={x}
                  y={chartY + chartHeight + 20}
                  textAnchor="middle"
                  fontSize="15"
                  fill="#666"
                >
                  {dateStr}
                </text>
              );
            });
          })}
        </svg>

        {/* Legenda */}
        <div className="performance-by-year__legend">
          {years.map((year, index) => (
            <div
              key={`legend-${year}`}
              className="performance-by-year__legend-item"
            >
              <span
                className="performance-by-year__legend-color"
                style={{ backgroundColor: colors[index % colors.length] }}
              />
              <span className="performance-by-year__legend-text">{year}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
