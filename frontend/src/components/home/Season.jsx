import { useAthletePerformanceInYear } from "../../hooks/useApi";
import CardState from "./CardState";

export default function Season({ athleteId }) {
  const {
    data: performanceInYear,
    isLoading,
    error,
  } = useAthletePerformanceInYear(athleteId);

  if (isLoading) return <div className="skeleton skeleton--sm" />;
  if (error) return <CardState type="error" />;
  if (!performanceInYear)
    return (
      <CardState type="no-data" text="V letošní sezóně zatím žádné závody." />
    );

  return (
    <div className="season">
      <div className="season__stats">
        <div className="season__stat">
          <span className="season__stat-label">Nejlepší čas</span>
          <span className="season__stat-value">
            {performanceInYear.best_time != null
              ? `${performanceInYear.best_time.toFixed(2)} s`
              : "—"}
          </span>
        </div>
        <div className="season__stat">
          <span className="season__stat-label">Průměrný čas</span>
          <span className="season__stat-value">
            {performanceInYear.average_time != null
              ? `${performanceInYear.average_time.toFixed(2)} s`
              : "—"}
          </span>
        </div>
        <div className="season__stat">
          <span className="season__stat-label">Počet závodů</span>
          <span className="season__stat-value">
            {performanceInYear.competitions ?? "—"}
          </span>
        </div>
      </div>
    </div>
  );
}
