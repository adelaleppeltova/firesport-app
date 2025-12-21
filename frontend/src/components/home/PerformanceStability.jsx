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
    if (
      rating.includes("Velmi vysoká") ||
      rating.includes("Vysoká")
    ) {
      return { icon: "fa-check-circle", color: "#4caf50" }; // Zelená
    } else if (rating.includes("Průměrná")) {
      return { icon: "fa-minus-circle", color: "#ff9800" }; // Oranžová
    } else if (rating.includes("Nízká")) {
      return { icon: "fa-exclamation-circle", color: "#f44336" }; // Červená
    }
    return { icon: "fa-question-circle", color: "#999" }; // Šedá
  };

  const ratingText = stability_rating || "Nedostatek dat";
  const stability = getStabilityIcon(ratingText);

  // Vypočítej relativní variabilitu
  const variabilityPercent =
    average_time_in_year && performance_variability
      ? ((performance_variability / average_time_in_year) * 100).toFixed(1)
      : null;

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
            {variabilityPercent && (
              <p className="performance-stability__text">
                Variabilita: {variabilityPercent}% (relativní)
              </p>
            )}
          </div>
        </div>

        <div className="performance-stability__stats">
          <div className="performance-stability__stat">
            <span className="performance-stability__stat-label">
              Rozptyl časů (s):
            </span>
            <span className="performance-stability__stat-value">
              {performance_variability?.toFixed(2) || "-"}
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
