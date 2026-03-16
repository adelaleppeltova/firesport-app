import { Link } from "react-router-dom";
import { useMlWindows } from "../../hooks/useApi";

const ACTIONS = [
  { label: "Můj detail", icon: "👤", to: null, athleteOnly: true },
  { label: "Závodníci", icon: "🏃", to: "/zavodnici" },
  { label: "Závody", icon: "🏆", to: "/zavody" },
  { label: "Statistiky", icon: "📊", to: "/statistiky" },
];

export default function HomeQuickActions({ athleteId }) {
  const { data: athleteWindows, isError: hasWindowsError } = useMlWindows(
    "yearly_3y",
    athleteId,
  );

  return (
    <nav className="quick-actions">
      {ACTIONS.map((action) => {
        if (action.athleteOnly && !athleteId) return null;
        const hasProcessedAnomalies =
          !hasWindowsError && Array.isArray(athleteWindows) && athleteWindows.length > 0;

        const to = action.athleteOnly
          ? `/zavodnici/${athleteId}`
          : action.label === "Statistiky" && athleteId && hasProcessedAnomalies
            ? `/statistiky?athlete_id=${encodeURIComponent(athleteId)}`
            : action.to;

        return (
          <Link key={action.label} className="quick-actions__item" to={to}>
            <span className="quick-actions__icon">{action.icon}</span>
            <span className="quick-actions__label">{action.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
