import { Link } from "react-router-dom";

export default function CompareAthletes() {
  return (
    <Link to="/compare" className="compare-athletes">
      <span className="compare-athletes__icon">📊</span>
      <span>Porovnat výkon</span>
      <span className="compare-athletes__arrow">›</span>
    </Link>
  );
}