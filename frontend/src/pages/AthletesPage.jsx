import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAthletes } from "../hooks/useApi";
import PrimaryButton from "../components/PrimaryButton";

export default function AthletesPage() {
  const { data: athletes, isLoading, error } = useAthletes();
  const [query, setQuery] = useState("");
  const navigate = useNavigate();

  const filtered = (
    athletes?.filter((athlete) => {
      const q = query.toLowerCase();
      return (
        athlete.first_name?.toLowerCase().includes(q) ||
        athlete.last_name?.toLowerCase().includes(q) ||
        String(athlete.birth_year).includes(q) ||
        athlete.teams?.some((team) => team.toLowerCase().includes(q))
      );
    }) || []
  ).sort((a, b) =>
    (a.last_name || "").localeCompare(b.last_name || "", "cs", {
      sensitivity: "base",
    }),
  );

  const PAGE_SIZE = 25;
  const [page, setPage] = useState(1);
  const pageCount = Math.ceil(filtered.length / PAGE_SIZE);
  const paginated = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  useEffect(() => {
    setPage(1);
  }, [query, athletes]);

  if (isLoading) return <div className="athletes-page page">Načítání...</div>;
  if (error)
    return <div className="athletes-page page">Chyba při načítání dat.</div>;

  return (
    <div className="athletes-page page">
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
            {paginated && paginated.length > 0 ? (
              paginated.map((athlete) => (
                <tr
                  key={athlete._id}
                  className="athlete-row"
                  onClick={() => navigate(`/zavodnici/${athlete._id}`)}
                >
                  <td>
                    {athlete.first_name} {athlete.last_name}
                  </td>
                  <td>{athlete.birth_year}</td>
                  <td>{athlete.teams.join(", ")}</td>
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
      {/* PAGINACE */}
      {pageCount > 1 && (
        <div className="pagination">
          <PrimaryButton
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            style={{
              marginRight: 8,
              width: "min(180px, 100%)",
              fontSize: "1.2rem",
            }}
          >
            Předchozí
          </PrimaryButton>
          <span>
            Strana {page} / {pageCount}
          </span>
          <PrimaryButton
            onClick={() => setPage((p) => Math.min(pageCount, p + 1))}
            disabled={page === pageCount}
            style={{
              marginLeft: 8,
              width: "min(180px, 100%)",
              fontSize: "1.2rem",
            }}
          >
            Další
          </PrimaryButton>
        </div>
      )}
    </div>
  );
}
