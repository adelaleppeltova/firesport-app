import { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAthletes } from "../hooks/useApi";
import PrimaryButton from "../components/PrimaryButton";

const PAGE_SIZE = 25;

export default function AthletesPage() {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [page, setPage] = useState(1);
  const navigate = useNavigate();
  const debounceRef = useRef(null);

  // Debounce vyhledávání – 300 ms po posledním stisku klávesy
  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [search]);

  const { data, isLoading, error, isFetching } = useAthletes({
    search: debouncedSearch,
    page,
    pageSize: PAGE_SIZE,
  });

  const athletes = data?.items || [];
  const total = data?.total || 0;
  const pageCount = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="athletes-page page">
      <h1>Závodníci</h1>
      <div className="athletes-searchbar-wrapper">
        <div className="athletes-searchbar-iconwrap">
          <input
            className="athletes-searchbar"
            type="text"
            placeholder="Hledat jméno, rok nebo sbor..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <i className="fa-solid fa-magnifying-glass athletes-searchbar-icon" />
        </div>
      </div>
      {debouncedSearch && (
        <p className="athletes-search-count">
          {isFetching ? "Hledám..." : `Nalezeno: ${total} závodníků`}
        </p>
      )}
      {error ? (
        <p className="athletes-error">Chyba při načítání dat.</p>
      ) : isLoading ? (
        <p className="athletes-loading">Načítání...</p>
      ) : (
        <>
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
                {athletes.length > 0 ? (
                  athletes.map((athlete) => (
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
                disabled={page === 1 || isFetching}
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
                disabled={page === pageCount || isFetching}
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
        </>
      )}
    </div>
  );
}
