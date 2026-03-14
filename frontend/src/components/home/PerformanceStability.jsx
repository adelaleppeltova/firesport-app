import { useAthletePerformanceStability as useStabilityData } from "../../hooks/useApi";

export default function PerformanceStability({ athleteId }) {
  const { data, isLoading, error } = useStabilityData(athleteId);

  if (isLoading) return <div className="skeleton" />;
  if (error) return <p className="empty-state">Chyba načítání</p>;
  if (!data)
    return <p className="empty-state">Žádná data o stabilitě výkonu</p>;

  const { stability_rating, performance_variability, average_time_in_year } =
    data;

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
              Rozsah časů:
            </span>
            <span className="performance-stability__stat-value">
              {variabilityDisplay} s
            </span>
          </div>

          <div className="performance-stability__stat">
            <span className="performance-stability__stat-label">
              Průměrný čas v sezóně:
            </span>
            <span className="performance-stability__stat-value">
              {average_time_in_year?.toFixed(2) || "-"} s
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
