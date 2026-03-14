import { useAthletePerformanceHistory } from "../../hooks/useApi";

export default function History({ athleteId }) {
  const { data, isLoading, error } = useAthletePerformanceHistory(athleteId);

  if (isLoading) return <div className="skeleton" />;
  if (error || !data) return <p className="empty-state">Žádná data</p>;
  const { performance_indicator } = data;
  const { recent_results } = performance_indicator;

  const formatSeconds = (value) => {
    if (value == null) return "-";
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue)) return "-";
    return numericValue.toFixed(2);
  };

  // Trend is based on last 6 valid results (newer 3 vs older 3, median).
  const getTrendIcon = (trend) => {
    switch (trend) {
      case "up":
        return { icon: "fa-arrow-up", label: "Zlepšení", color: "#4caf50" };
      case "down":
        return { icon: "fa-arrow-down", label: "Zhoršení", color: "#f44336" };
      case "stable":
        return { icon: "fa-minus", label: "Stabilní", color: "#ff9800" };
      case "insufficient":
        return { icon: "fa-minus", label: "Nedostatek dat", color: "#999" };
      default:
        return { icon: "fa-minus", label: "Bez dat", color: "#999" };
    }
  };

  const indicator = performance_indicator ?? {};
  const {
    trend: trendKey,
    delta_seconds: deltaSeconds,
    new_value: newValue,
    old_value: oldValue,
  } = indicator;

  const trend = getTrendIcon(trendKey);
  const deltaText =
    deltaSeconds == null
      ? "-"
      : `${deltaSeconds > 0 ? "+" : ""}${formatSeconds(deltaSeconds)} s`;
  const hasDetails =
    trendKey && trendKey !== "insufficient" && deltaSeconds != null;

  return (
    <div className="history">
      <div className="history__info">
        <div className="history__trend">
          <i
            className={`fa-solid ${trend.icon}`}
            style={{
              color: trend.color,
              fontSize: "2rem",
              marginRight: "1rem",
            }}
          />
          <div>
            <p className="history__text">
              <strong>{trend.label}</strong> - Výkonnost podle posledních závodů
            </p>
            {hasDetails && (
              <p className="history__subtext">
                Změna: {deltaText} (starší 3: {formatSeconds(oldValue)} s,
                novější 3: {formatSeconds(newValue)} s)
              </p>
            )}
            {recent_results && recent_results.length > 0 && (
              <div className="history__recent">
                <p className="history__subtext">
                  Posledních {recent_results.length} výsledků:
                </p>
                <div className="history__results">
                  {recent_results.map((result, idx) => (
                    <span
                      key={idx}
                      className="history__result-badge"
                      title={`Čas: ${formatSeconds(result.final_time)} s${
                        result.rank ? `, Pořadí: ${result.rank}` : ""
                      }`}
                    >
                      {formatSeconds(result.final_time)} s
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
