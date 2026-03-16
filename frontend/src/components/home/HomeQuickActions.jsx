import { Link } from "react-router-dom";

const ACTIONS = [
  { label: "Můj detail", icon: "👤", to: null, athleteOnly: true },
  { label: "Závodníci", icon: "🏃", to: "/zavodnici" },
  { label: "Závody", icon: "🏆", to: "/zavody" },
  { label: "Statistiky", icon: "📊", to: "/statistiky" },
];

export default function HomeQuickActions({ athleteId }) {
  return (
    <nav className="quick-actions">
      {ACTIONS.map((action) => {
        if (action.athleteOnly && !athleteId) return null;
        const to = action.athleteOnly ? `/zavodnici/${athleteId}` : action.to;
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
