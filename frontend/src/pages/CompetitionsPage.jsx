import { useNavigate } from "react-router-dom";
import { useCompetitions } from "../hooks/useApi";
import PrimaryButton from "../components/PrimaryButton";
import { useState, useEffect } from "react";

export default function CompetitionsPage() {
  const { data: competitions, isLoading, error } = useCompetitions();
  const navigate = useNavigate();

  const PAGE_SIZE = 25;
  const [page, setPage] = useState(1);
  const comps = competitions || [];
  const pageCount = Math.ceil(comps.length / PAGE_SIZE);
  const paginated = comps.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  useEffect(() => {
    setPage(1);
  }, [competitions]);

  if (isLoading) return <div className="competitions-page">Načítání...</div>;
  if (error)
    return <div className="competitions-page">Chyba při načítání dat.</div>;

  return (
    <div className="competitions-page page">
      <h1>Závody</h1>
      <div className="competitions-searchbar-wrapper">
        <div className="competitions-searchbar-iconwrap">
          <input
            className="competitions-searchbar"
            type="text"
            placeholder="Hledat název, místo nebo datum..."
            disabled
          />
          <i className="fa-solid fa-magnifying-glass competitions-searchbar-icon" />
        </div>
      </div>
      <div className="competitions-table-wrapper">
        <table className="competitions-table">
          <thead>
            <tr>
              <th>Název</th>
              <th>Datum</th>
              <th>Místo</th>
            </tr>
          </thead>
          <tbody>
            {paginated && paginated.length > 0 ? (
              paginated.map((comp) => (
                <tr
                  key={comp._id}
                  className="competition-row"
                  onClick={() => navigate(`/zavody/${comp._id}`)}
                  style={{ cursor: "pointer" }}
                >
                  <td>{comp.name}</td>
                  <td>
                    {comp.date
                      ? new Date(comp.date).toLocaleDateString("cs-CZ")
                      : "-"}
                  </td>
                  <td>{comp.place}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={3}>Žádné závody</td>
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
