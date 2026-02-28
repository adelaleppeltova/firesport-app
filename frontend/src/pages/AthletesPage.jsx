import { useEffect, useState, useRef, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAthletes } from "../hooks/useApi";
import PrimaryButton from "../components/PrimaryButton";

const PAGE_SIZE = 25;

export default function AthletesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const debounceRef = useRef(null);

  // Inicializace stavu z URL
  const initialSearch = searchParams.get("q") || "";
  const initialPage = Number(searchParams.get("page")) || 1;

  const [search, setSearch] = useState(initialSearch);
  const [debouncedSearch, setDebouncedSearch] = useState(initialSearch);
  const [page, setPage] = useState(initialPage);

  // sync state from URL params on mount and whenever they change
  useEffect(() => {
    // debugger;
    const p = Number(searchParams.get("page")) || 1;
    const q = searchParams.get("q") || "";
    if (p !== page) setPage(p);
    if (q !== search) {
      setSearch(q);
      setDebouncedSearch(q);
    }
  }, [searchParams]);

  // Sync stavu do URL (přes ref, aby nezpůsoboval refire efektů)
  const updateUrl = useCallback(
    (q, p) => {
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (p > 1) params.set("page", String(p));
      setSearchParams(params, { replace: true });
    },
    [setSearchParams],
  );

  const updateUrlRef = useRef(updateUrl);
  useEffect(() => {
    updateUrlRef.current = updateUrl;
  }, [updateUrl]);

  // Debounce vyhledávání – 300 ms po posledním stisku klávesy
  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(search);
      const pageParam = searchParams.get("page");
      if (!pageParam) {
        setPage(1);
      }
      const p = pageParam ? Number(pageParam) : page;
      updateUrlRef.current(search, p);
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [search, searchParams]);

  // Sync page do URL při změně stránky + scroll nahoru
  useEffect(() => {
    updateUrlRef.current(debouncedSearch, page);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [page, debouncedSearch]);

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
