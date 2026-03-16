import { useNavigate, useSearchParams } from "react-router-dom";
import { useCompetitions } from "../hooks/useApi";
import PrimaryButton from "../components/PrimaryButton";
import { useState, useEffect, useRef, useCallback } from "react";
import { scrollPageToTop } from "../components/ScrollToTop";

const PAGE_SIZE = 25;

export default function CompetitionsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const debounceRef = useRef(null);

  // Inicializace stavu z URL
  const initialSearch = searchParams.get("q") || "";
  const initialPage = Number(searchParams.get("page")) || 1;
  const initialSortKey = searchParams.get("sort") || "date";
  const initialSortDir = searchParams.get("dir") || "desc";

  const [search, setSearch] = useState(initialSearch);
  const [debouncedSearch, setDebouncedSearch] = useState(initialSearch);
  const [page, setPage] = useState(initialPage);
  const [sortKey, setSortKey] = useState(initialSortKey);
  const [sortDir, setSortDir] = useState(initialSortDir);

  // Sync stavu do URL (přes ref, aby nezpůsoboval refire efektů)
  const updateUrl = useCallback(
    (q, p, sk, sd) => {
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (p > 1) params.set("page", String(p));
      if (sk !== "date") params.set("sort", sk);
      if (sd !== "desc") params.set("dir", sd);
      setSearchParams(params, { replace: true });
    },
    [setSearchParams],
  );
  const updateUrlRef = useRef(updateUrl);
  useEffect(() => {
    updateUrlRef.current = updateUrl;
  }, [updateUrl]);

  // Debounce vyhledávání – 300 ms
  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
      updateUrlRef.current(search, 1, sortKey, sortDir);
    }, 300);
    return () => clearTimeout(debounceRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  // Sync page/sort do URL při změně + scroll nahoru
  useEffect(() => {
    updateUrlRef.current(debouncedSearch, page, sortKey, sortDir);
    scrollPageToTop();
  }, [page, sortKey, sortDir, debouncedSearch]);

  const { data, isLoading, error, isFetching } = useCompetitions({
    search: debouncedSearch,
    page,
    pageSize: PAGE_SIZE,
    sortKey,
    sortDir,
  });

  const competitions = data?.items || [];
  const total = data?.total || 0;
  const pageCount = Math.ceil(total / PAGE_SIZE);

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
    setPage(1);
  };

  const sortIcon = (key) => {
    if (sortKey !== key) return "fa-solid fa-sort";
    return sortDir === "asc" ? "fa-solid fa-sort-up" : "fa-solid fa-sort-down";
  };

  return (
    <div className="competitions-page page">
      <h1>Závody</h1>
      <div className="competitions-searchbar-wrapper">
        <div className="competitions-searchbar-iconwrap">
          <input
            className="competitions-searchbar"
            type="text"
            placeholder="Hledat název, místo nebo datum..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <i className="fa-solid fa-magnifying-glass competitions-searchbar-icon" />
        </div>
      </div>
      {debouncedSearch && (
        <p className="competitions-search-count">
          {isFetching ? "Hledám..." : `Nalezeno: ${total} závodů`}
        </p>
      )}
      {error ? (
        <p className="competitions-error">Chyba při načítání dat.</p>
      ) : isLoading ? (
        <p className="competitions-loading">Načítání...</p>
      ) : (
        <>
          <div className="competitions-table-wrapper">
            <table className="competitions-table">
              <thead>
                <tr>
                  <th
                    className="sortable-th"
                    onClick={() => handleSort("name")}
                  >
                    Název <i className={sortIcon("name")} />
                  </th>
                  <th
                    className="sortable-th"
                    onClick={() => handleSort("date")}
                  >
                    Datum <i className={sortIcon("date")} />
                  </th>
                  <th
                    className="sortable-th"
                    onClick={() => handleSort("place")}
                  >
                    Místo <i className={sortIcon("place")} />
                  </th>
                </tr>
              </thead>
              <tbody>
                {competitions.length > 0 ? (
                  competitions.map((comp) => (
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
