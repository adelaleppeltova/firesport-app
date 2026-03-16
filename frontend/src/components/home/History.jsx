import { useEffect } from "react";
import { useAthletePerformanceHistory } from "../../hooks/useApi";
import CardState from "./CardState";
import {
  getHistoryTrendConfig,
  getHistoryTrendModifier,
} from "./cardModifiers";

export default function History({ athleteId, onTrendChange }) {
  const { data, isLoading, error } = useAthletePerformanceHistory(athleteId);

  const trendKey = data?.performance_indicator?.trend;
  const trend = getHistoryTrendConfig(trendKey);

  useEffect(() => {
    onTrendChange?.(getHistoryTrendModifier(trendKey));
  }, [onTrendChange, trendKey]);

  if (isLoading) return <div className="skeleton skeleton--lg" />;
  if (error) return <CardState type="error" />;
  if (!data) return <CardState type="no-data" text="Zatím žádné výsledky." />;

  const { performance_indicator } = data;
  const { recent_results } = performance_indicator;

  const formatSeconds = (value) => {
    if (value == null) return "-";
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue)) return "-";
    return numericValue.toFixed(2);
  };

  const indicator = performance_indicator ?? {};
  const {
    delta_seconds: deltaSeconds,
    new_value: newValue,
    old_value: oldValue,
  } = indicator;

  const hasDetails =
    trendKey && trendKey !== "insufficient" && deltaSeconds != null;

  const getDeltaLabel = () => {
    if (!hasDetails) return null;
    const abs = Math.abs(Number(deltaSeconds)).toFixed(2);
    if (trendKey === "up") return `o ${abs}\u202fs rychleji`;
    if (trendKey === "down") return `o ${abs}\u202fs pomaleji`;
    return `rozdíl ${formatSeconds(deltaSeconds)}\u202fs`;
  };

  return (
    <div className={`history history--state-${trend.state}`}>
      <div className="history__status">
        <i className={`fa-solid ${trend.icon} history__icon`} />
        <span className="history__label">{trend.label}</span>
      </div>

      {hasDetails && (
        <div className="history__delta">
          <span className="history__delta-value">{getDeltaLabel()}</span>
          <span className="history__delta-detail">
            průměr: {formatSeconds(oldValue)}
            {" "}s → {formatSeconds(newValue)}
            {" "}s
          </span>
        </div>
      )}

      {recent_results && recent_results.length > 0 && (
        <div className="history__recent">
          <span className="history__recent-label">Poslední časy</span>
          <div className="history__results">
            {recent_results.map((result, idx) => (
              <span
                key={idx}
                className="history__result-badge"
                title={result.rank ? `Pořadí: ${result.rank}` : undefined}
              >
                {formatSeconds(result.final_time)}
                {" "}s
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
