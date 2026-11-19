import { useCategoryCatalog } from "../hooks/useApi";

export default function DisciplineSelect({ value, onChange, all = false }) {
  const { data } = useCategoryCatalog();
  const disciplines = Object.entries(data?.disciplines ?? {});
  if (!disciplines.length) return null;

  return (
    <label>
      Disciplína{" "}
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {all && <option value="">Všechny disciplíny</option>}
        {disciplines.map(([id, name]) => (
          <option key={id} value={id}>{name}</option>
        ))}
      </select>
    </label>
  );
}
