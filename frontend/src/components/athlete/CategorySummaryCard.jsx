export const CATEGORY_GROUP_LABELS = {
  muz: "Muži / Dorostenci družstva / Starší dorostenci",
  zena: "Ženy / Dorostenky",
  mladsi_dorostenci: "Mladší / Střední dorostenci",
};

const DISCIPLINE_LABELS = {
  "60m": "60 m",
  "100mPHP": "100 m s PHP",
  "4x100m": "Štafeta 4 × 100 m",
  PU: "Požární útok",
  vez: "Výstup na věž",
};

export function formatCategoryGroup(group, legacyCategoryNames = {}) {
  const separator = group.indexOf(":");
  if (separator < 0) return CATEGORY_GROUP_LABELS[group] ?? group;
  const discipline = group.slice(0, separator);
  const category = group.slice(separator + 1);
  if (discipline === "legacy") {
    return legacyCategoryNames[category] ?? "Historická kategorie";
  }
  return `${CATEGORY_GROUP_LABELS[category] ?? category} · ${DISCIPLINE_LABELS[discipline] ?? discipline}`;
}

export function CategoryGroupSelect({ groups, value, onChange, helperText, legacyCategoryNames }) {
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
            {formatCategoryGroup(g, legacyCategoryNames)}
          </option>
        ))}
      </select>
      {helperText ? <p className="window-select__helper">{helperText}</p> : null}
    </div>
  );
}
