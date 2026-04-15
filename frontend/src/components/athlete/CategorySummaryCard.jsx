export const CATEGORY_GROUP_LABELS = {
  muz: "Muži / Dorostenci družstva / Starší dorostenci",
  zena: "Ženy / Dorostenky",
  mladsi_dorostenci: "Mladší / Střední dorostenci",
};

export function formatCategoryGroup(group) {
  return CATEGORY_GROUP_LABELS[group] ?? group;
}

export function CategoryGroupSelect({ groups, value, onChange, helperText }) {
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
      {helperText ? <p className="window-select__helper">{helperText}</p> : null}
    </div>
  );
}
