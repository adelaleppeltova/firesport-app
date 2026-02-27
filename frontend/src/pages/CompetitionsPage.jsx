import { useNavigate } from "react-router-dom";
import { useCompetitions } from "../hooks/useApi";
import PrimaryButton from "../components/PrimaryButton";
import { useState, useEffect } from "react";

export default function CompetitionsPage() {
  const { data: competitions, isLoading, error } = useCompetitions();
  const navigate = useNavigate();

  const PAGE_SIZE = 25;
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState("date");
  const [sortDir, setSortDir] = useState("desc");

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const sortIcon = (key) => {
    if (sortKey !== key) return "fa-solid fa-sort";
    return sortDir === "asc" ? "fa-solid fa-sort-up" : "fa-solid fa-sort-down";
  };

  const comps = competitions || [];
  const filtered = comps.filter((comp) => {
    if (!query.trim()) return true;
    const q = query.toLowerCase();
    const name = (comp.name || "").toLowerCase();
    const place = (comp.place || "").toLowerCase();
    const date = comp.date
      ? new Date(comp.date).toLocaleDateString("cs-CZ")
      : "";
    return name.includes(q) || place.includes(q) || date.includes(q);
  });

  const sorted = [...filtered].sort((a, b) => {
    if (!sortKey) return 0;
    const dir = sortDir === "asc" ? 1 : -1;
    if (sortKey === "name" || sortKey === "place") {
      const valA = (a[sortKey] || "").toLowerCase();
      const valB = (b[sortKey] || "").toLowerCase();
      return dir * valA.localeCompare(valB, "cs");
    }
    if (sortKey === "date") {
      const dateA = a.date ? new Date(a.date).getTime() : 0;
      const dateB = b.date ? new Date(b.date).getTime() : 0;
      return dir * (dateA - dateB);
    }
    return 0;
  });

  const pageCount = Math.ceil(sorted.length / PAGE_SIZE);
  const paginated = sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  useEffect(() => {
    setPage(1);
  }, [competitions, query, sortKey, sortDir]);

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
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <i className="fa-solid fa-magnifying-glass competitions-searchbar-icon" />
        </div>
      </div>
      <div className="competitions-table-wrapper">
        <table className="competitions-table">
          <thead>
            <tr>
              <th className="sortable-th" onClick={() => handleSort("name")}>
                Název <i className={sortIcon("name")} />
              </th>
              <th className="sortable-th" onClick={() => handleSort("date")}>
                Datum <i className={sortIcon("date")} />
              </th>
              <th className="sortable-th" onClick={() => handleSort("place")}>
                Místo <i className={sortIcon("place")} />
              </th>
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
