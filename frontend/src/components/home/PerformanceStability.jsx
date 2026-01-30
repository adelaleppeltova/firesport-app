import { useMe, useAthleteOverview } from "../../hooks/useApi";

export default function PerformanceStability() {
  const { data: me, isLoading: meLoading, error: meError } = useMe();
  const {
    data: overview,
    isLoading: overviewLoading,
    error: overviewError,
  } = useAthleteOverview(me?.athlete_id);

  if (meLoading || overviewLoading) return <div className="skeleton" />;
  if (meError || overviewError)
    return <p className="empty-state">Chyba načítání</p>;
  if (!overview)
    return <p className="empty-state">Žádná data o stabilitě výkonu</p>;

  const { stability_rating, performance_variability, average_time_in_year } =
    overview;

  // Mapování stability na ikonu a barvu
  const getStabilityIcon = (rating = "") => {
    const normalized = rating.toLowerCase();
    if (normalized.includes("stabilní")) {
      return { icon: "fa-check-circle", color: "#4caf50" }; // Zelená
    }
    if (normalized.includes("kolísavé")) {
      return { icon: "fa-exclamation-circle", color: "#ff9800" }; // Oranžová
    }
    return { icon: "fa-question-circle", color: "#999" }; // Šedá
  };

  const ratingText = stability_rating || "Nedostatek dat";
  const stability = getStabilityIcon(ratingText);

  const variabilityDisplay =
    performance_variability == null ? "-" : performance_variability.toFixed(2);

  return (
    <div className="performance-stability">
      <div className="performance-stability__info">
        <div className="performance-stability__header">
          <i
            className={`fa-solid ${stability.icon}`}
            style={{
              color: stability.color,
              fontSize: "2rem",
              marginRight: "1rem",
            }}
          />
          <div>
            <p className="performance-stability__rating">
              <strong>{ratingText}</strong>
            </p>
          </div>
        </div>

        <div className="performance-stability__stats">
          <div className="performance-stability__stat">
            <span className="performance-stability__stat-label">
              Rozsah časů (s):
            </span>
            <span className="performance-stability__stat-value">
              {variabilityDisplay}
            </span>
          </div>

          <div className="performance-stability__stat">
            <span className="performance-stability__stat-label">
              Průměrný čas v sezóně (s):
            </span>
            <span className="performance-stability__stat-value">
              {average_time_in_year?.toFixed(2) || "-"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
