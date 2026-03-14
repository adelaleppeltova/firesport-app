import Card from "../Card";

function formatTime(seconds) {
  if (seconds == null) return "—";
  const mins = Math.floor(seconds / 60);
  const secs = (seconds % 60).toFixed(2).padStart(5, "0");
  return mins > 0 ? `${mins}:${secs}` : `${secs} s`;
}

/**
 * Select pro výběr konkrétní kategorie z DB (např. "Střední dorostenci").
 */
export function CategorySelect({ categories, value, onChange }) {
  if (!categories || categories.length === 0) return null;
  const isDisabled = categories.length === 1;
  return (
    <div className="window-select">
      <label className="window-select__label" htmlFor="category-select">
        Kategorie:
      </label>
      <select
        id="category-select"
        className="window-select__input"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
        disabled={isDisabled}
      >
        {categories.map((cat) => (
          <option key={cat.category_id} value={cat.category_id}>
            {cat.category_name}
          </option>
        ))}
      </select>
    </div>
  );
}

/**
 * Karta přehledu v konkrétní kategorii (ne groupby).
 */
export default function AthleteDetailCategoryCard({
  totalRaces,
  bestTime,
  categoryName,
}) {
  return (
    <Card title={`Přehled v kategorii ${categoryName ?? "—"}`}>
      <div className="anomaly-summary">
        <div className="anomaly-summary__item">
          <span className="anomaly-summary__label">Celkový počet závodů</span>
          <span className="anomaly-summary__value">
            {totalRaces != null ? totalRaces : "—"}
          </span>
        </div>
        <div className="anomaly-summary__item">
          <span className="anomaly-summary__label">Nejlepší čas</span>
          <span className="anomaly-summary__value">
            {bestTime != null ? formatTime(bestTime) : "—"}
          </span>
        </div>
      </div>
    </Card>
  );
}
