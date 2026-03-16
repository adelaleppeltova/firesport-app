import { useEffect } from "react";
import { useAthletePerformanceStability as useStabilityData } from "../../hooks/useApi";
import CardState from "./CardState";
import { getStabilityModifier } from "./cardModifiers";

const STABILITY_CONFIG = {
  stable: {
    match: (r) => r.includes("stabilní"),
    icon: "fa-check-circle",
    modifier: "stable",
    description: "Výsledky jsou stabilní a pravidelné.",
  },
  variable: {
    match: (r) => r.includes("kolísavé"),
    icon: "fa-circle-half-stroke",
    modifier: "variable",
    description: "Výkony se mezi závody výrazněji liší.",
  },
  unknown: {
    match: () => true,
    icon: "fa-circle-question",
    modifier: "unknown",
    description: "Pro hodnocení zatím není dost výsledků.",
  },
};

function getStabilityConfig(rating = "") {
  const normalized = rating.toLowerCase();
  return (
    Object.values(STABILITY_CONFIG).find((c) => c.match(normalized)) ??
    STABILITY_CONFIG.unknown
  );
}

export default function PerformanceStability({ athleteId, onStabilityChange }) {
  const { data, isLoading, error } = useStabilityData(athleteId);
  const ratingText = data?.stability_rating || "Nedostatek dat";
  const config = data ? getStabilityConfig(ratingText) : STABILITY_CONFIG.unknown;

  useEffect(() => {
    onStabilityChange?.("unknown");
  }, [athleteId, onStabilityChange]);

  useEffect(() => {
    onStabilityChange?.(getStabilityModifier(ratingText));
  }, [onStabilityChange, ratingText]);

  if (isLoading) return <div className="skeleton skeleton--lg" />;
  if (error) return <CardState type="error" />;
  if (!data)
    return (
      <CardState
        type="insufficient"
        text="Pro hodnocení je potřeba více výsledků."
      />
    );

  const { performance_variability, average_time_in_year } = data;

  const variabilityDisplay =
    performance_variability == null ? "-" : performance_variability.toFixed(2);

  return (
    <div className="performance-stability">
      <div className="performance-stability__info">
        <div className="performance-stability__header">
          <i
            className={`fa-solid ${config.icon} performance-stability__icon performance-stability__icon--${config.modifier}`}
          />
          <div>
            <p className="performance-stability__rating">
              <strong>{ratingText}</strong>
            </p>
            <p className="performance-stability__description">
              {config.description}
            </p>
          </div>
        </div>

        <div className="performance-stability__stats">
          <div className="performance-stability__stat">
            <span className="performance-stability__stat-label">Rozptyl:</span>
            <span className="performance-stability__stat-value">
              {variabilityDisplay} s
            </span>
          </div>

          <div className="performance-stability__stat">
            <span className="performance-stability__stat-label">
              Průměr v sezóně:
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
