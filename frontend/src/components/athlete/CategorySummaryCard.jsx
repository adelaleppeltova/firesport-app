import Card from "../Card";

// --- constants ---

export const CATEGORY_GROUP_LABELS = {
  muz: "Muži / Dorostenci družstva / Starší dorostenci",
  zena: "Ženy / Dorostenky",
  mladsi_dorostenci: "Mladší / Střední dorostenci",
};

// --- helpers ---

export function formatCategoryGroup(group) {
  return CATEGORY_GROUP_LABELS[group] ?? group;
}

function formatTime(seconds) {
  if (seconds == null) return "—";
  const mins = Math.floor(seconds / 60);
  const secs = (seconds % 60).toFixed(2).padStart(5, "0");
  return mins > 0 ? `${mins}:${secs}` : `${secs} s`;
}

// --- CategoryGroupSelect ---

export function CategoryGroupSelect({ groups, value, onChange }) {
  if (!groups || groups.length === 0) return null;
  const isDisabled = groups.length === 1;
  return (
    <div className="window-select">
      <label className="window-select__label" htmlFor="category-group-select">
        Kategorie:
      </label>
      <select
        id="category-group-select"
        className="window-select__input"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
        disabled={isDisabled}
      >
        {groups.map((g) => (
          <option key={g} value={g}>
            {formatCategoryGroup(g)}
          </option>
        ))}
      </select>
    </div>
  );
}

// --- CategorySummaryCard ---

export default function CategorySummaryCard({
  totalRaces,
  bestTime,
  categoryGroup,
}) {
  const categoryLabel = categoryGroup
    ? formatCategoryGroup(categoryGroup)
    : "—";

  return (
    <Card title={`Přehled v kategorii ${categoryLabel}`}>
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
