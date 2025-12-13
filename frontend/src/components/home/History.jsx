import { useMe, useAthleteOverview } from "../../hooks/useApi";

export default function History() {
  const { data: me, isLoading: meLoading } = useMe();
  const { data: overview, isLoading: overviewLoading } = useAthleteOverview(
    me?.athlete_id
  );

  if (meLoading || overviewLoading) return <div className="skeleton" />;
  if (!overview) return <p className="empty-state">Žádná data</p>;

  const { performance_trend, recent_results } = overview;

  // Mapování trendu na ikonu a barvu
  const getTrendIcon = (trend) => {
    switch (trend) {
      case "improving":
        return { icon: "fa-arrow-up", label: "Zlepšení", color: "#4caf50" };
      case "declining":
        return { icon: "fa-arrow-down", label: "Zhoršení", color: "#f44336" };
      case "stable":
        return { icon: "fa-minus", label: "Stabilní", color: "#ff9800" };
      default:
        return { icon: "fa-minus", label: "Bez dat", color: "#999" };
    }
  };

  const trend = getTrendIcon(performance_trend);

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
              <strong>{trend.label}</strong> - Trend výkonu v posledních
              závodech
            </p>
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
                      title={`Čas: ${result.final_time?.toFixed(2)} s${
                        result.rank ? `, Pořadí: ${result.rank}` : ""
                      }`}
                    >
                      {result.final_time?.toFixed(2) || "-"}s
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
