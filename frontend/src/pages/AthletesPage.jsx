import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAthletes } from "../hooks/useApi";

export default function AthletesPage() {
  const { data: athletes, isLoading, error } = useAthletes();
  const [query, setQuery] = useState("");
  const navigate = useNavigate();

  const filtered = athletes?.filter((athlete) => {
    const q = query.toLowerCase();
    return (
      athlete.first_name?.toLowerCase().includes(q) ||
      athlete.last_name?.toLowerCase().includes(q) ||
      String(athlete.birth_year).includes(q) ||
      athlete.team?.toLowerCase().includes(q)
    );
  });

  if (isLoading) return <div className="athletes-page">Načítání...</div>;
  if (error)
    return <div className="athletes-page">Chyba při načítání dat.</div>;

  return (
    <div className="athletes-page">
      <h1>Závodníci</h1>
      <div className="athletes-searchbar-wrapper">
        <div className="athletes-searchbar-iconwrap">
          <input
            className="athletes-searchbar"
            type="text"
            placeholder="Hledat jméno, rok nebo sbor..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <i className="fa-solid fa-magnifying-glass athletes-searchbar-icon" />
        </div>
      </div>
      <div className="athletes-table-wrapper">
        <table className="athletes-table">
          <thead>
            <tr>
              <th>Jméno</th>
              <th>Rok</th>
              <th>Sbor</th>
            </tr>
          </thead>
          <tbody>
            {filtered && filtered.length > 0 ? (
              filtered.map((athlete) => (
                <tr
                  key={athlete._id}
                  className="athlete-row"
                  onClick={() => navigate(`/athletes/${athlete._id}`)}
                >
                  <td>
                    {athlete.first_name} {athlete.last_name}
                  </td>
                  <td>{athlete.birth_year}</td>
                  <td>{athlete.team}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={3}>Žádní závodníci</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
