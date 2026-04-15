import Card from "../Card";
import formatCategoryName from "../../utils/formatCategoryName";

function formatTime(seconds) {
  if (seconds == null) return "—";
  const mins = Math.floor(seconds / 60);
  const secs = (seconds % 60).toFixed(2).padStart(5, "0");
  return mins > 0 ? `${mins}:${secs}` : `${secs} s`;
}

export function CategorySelect({ categories, value, onChange }) {
  if (!categories || categories.length === 0) return null;
  return (
    <div className="window-select">
      <label className="window-select__label" htmlFor="category-select">
        Kategorie:
      </label>
      <select
        id="category-select"
        className="window-select__input"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">Všechny kategorie</option>
        {categories.map((cat) => (
          <option key={cat.category_id} value={cat.category_id}>
            {formatCategoryName(cat.category_name)}
          </option>
        ))}
      </select>
    </div>
  );
}

export default function AthleteDetailCategoryCard({
  totalResults,
  bestTime,
  titleLabel,
  averageValidTime,
  invalidResultsCount,
  lastCompetition,
}) {
  const stats = [
    {
      label: "Počet výsledků",
      value: totalResults != null ? totalResults : "—",
    },
    {
      label: "Nejlepší čas",
      value: bestTime != null ? formatTime(bestTime) : "—",
    },
    {
      label: "Průměr validních časů",
      value: averageValidTime != null ? formatTime(averageValidTime) : "—",
    },
    {
      label: "Neplatné výsledky",
      value: invalidResultsCount != null ? invalidResultsCount : "—",
    },
  ];

  return (
    <Card
      title={`Přehled pro kategorii: ${formatCategoryName(titleLabel) ?? "—"}`}
      className="athlete-category-overview-card"
    >
      <div className="athlete-category-overview-card__stats">
        {stats.map((stat) => (
          <div className="athlete-category-overview-card__stat" key={stat.label}>
            <span className="athlete-category-overview-card__label">
              {stat.label}
            </span>
            <strong className="athlete-category-overview-card__value">
              {stat.value}
            </strong>
          </div>
        ))}
      </div>

      <div className="athlete-category-overview-card__footer">
        <span className="athlete-category-overview-card__footer-label">
          Poslední závod
        </span>
        <strong className="athlete-category-overview-card__footer-value">
          {lastCompetition || "—"}
        </strong>
      </div>
    </Card>
  );
}
