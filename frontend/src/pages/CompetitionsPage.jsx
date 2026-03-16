import { Link, useSearchParams } from "react-router-dom";
import { useCompetitions } from "../hooks/useApi";
import PrimaryButton from "../components/PrimaryButton";
import { useState, useEffect, useRef, useCallback } from "react";
import { scrollPageToTop } from "../components/ScrollToTop";

const PAGE_SIZE = 25;

export default function CompetitionsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
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
  const showInitialLoading = isLoading && !data;
  const hasActiveSearch = debouncedSearch.trim().length > 0;
  const resultsStatusMessage = isFetching
    ? "Aktualizuji výsledky..."
    : hasActiveSearch
      ? `Nalezeno ${total} závodů.`
      : "";
  const showResultsStatus = Boolean(resultsStatusMessage) && !error && !showInitialLoading;

  const clearSearch = () => {
    setSearch("");
    setDebouncedSearch("");
    setPage(1);
    updateUrlRef.current("", 1, sortKey, sortDir);
  };

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

  const getAriaSort = (key) => {
    if (sortKey !== key) return "none";
    return sortDir === "asc" ? "ascending" : "descending";
  };

  const getSortButtonLabel = (label, key) => {
    if (sortKey !== key) {
      return `Seřadit podle sloupce ${label} vzestupně`;
    }

    return sortDir === "asc"
      ? `${label}, aktuálně vzestupně. Aktivací změníte řazení na sestupné`
      : `${label}, aktuálně sestupně. Aktivací změníte řazení na vzestupné`;
  };

  return (
    <div className="competitions-page page">
      <div className="competitions-page__header">
        <h1>Závody</h1>
        <div className="competitions-page__toolbar">
          <div className="competitions-searchbar-wrapper">
            <div className="competitions-searchbar-iconwrap">
              <input
                className="competitions-searchbar"
                type="text"
                placeholder="Hledat název, místo nebo datum..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                aria-describedby={
                  showResultsStatus ? "competitions-results-status" : undefined
                }
              />
              <i
                className={`fa-solid ${
                  isFetching
                    ? "fa-spinner competitions-searchbar-icon competitions-searchbar-icon--spinning"
                    : "fa-magnifying-glass competitions-searchbar-icon"
                }`}
              />
            </div>
          </div>
        </div>
      </div>
      {error ? (
        <p className="competitions-feedback competitions-feedback--error">
          Nepodařilo se načíst seznam závodů.
        </p>
      ) : showInitialLoading ? (
        <p className="competitions-feedback" aria-live="polite">
          Načítám seznam závodů...
        </p>
      ) : (
        <div className="competitions-page__content">
          {showResultsStatus && (
            <div
              id="competitions-results-status"
              className={`competitions-results-status${
                isFetching ? " competitions-results-status--loading" : ""
              }`}
              aria-live="polite"
              aria-atomic="true"
            >
              {isFetching && (
                <span
                  className="competitions-results-status__dot"
                  aria-hidden="true"
                />
              )}
              <span>{resultsStatusMessage}</span>
            </div>
          )}
          <div
            className={`competitions-table-wrapper${
              isFetching ? " competitions-table-wrapper--fetching" : ""
            }`}
            aria-busy={isFetching}
          >
            {competitions.length > 0 ? (
              <table className="competitions-table">
                <colgroup>
                  <col className="competitions-table__col competitions-table__col--name" />
                  <col className="competitions-table__col competitions-table__col--date" />
                  <col className="competitions-table__col competitions-table__col--place" />
                </colgroup>
                <thead>
                  <tr>
                    <th
                      className={`sortable-th competitions-table__name-heading${
                        sortKey === "name" ? " sortable-th--active" : ""
                      }`}
                      aria-sort={getAriaSort("name")}
                    >
                      <button
                        type="button"
                        className="sortable-th__button"
                        onClick={() => handleSort("name")}
                        aria-label={getSortButtonLabel("Název", "name")}
                      >
                        <span className="sortable-th__label">Název</span>
                        <i className={sortIcon("name")} aria-hidden="true" />
                      </button>
                    </th>
                    <th
                      className={`sortable-th competitions-table__date-heading${
                        sortKey === "date" ? " sortable-th--active" : ""
                      }`}
                      aria-sort={getAriaSort("date")}
                    >
                      <button
                        type="button"
                        className="sortable-th__button"
                        onClick={() => handleSort("date")}
                        aria-label={getSortButtonLabel("Datum", "date")}
                      >
                        <span className="sortable-th__label">Datum</span>
                        <i className={sortIcon("date")} aria-hidden="true" />
                      </button>
                    </th>
                    <th
                      className={`sortable-th competitions-table__place-heading${
                        sortKey === "place" ? " sortable-th--active" : ""
                      }`}
                      aria-sort={getAriaSort("place")}
                    >
                      <button
                        type="button"
                        className="sortable-th__button"
                        onClick={() => handleSort("place")}
                        aria-label={getSortButtonLabel("Místo", "place")}
                      >
                        <span className="sortable-th__label">Místo</span>
                        <i className={sortIcon("place")} aria-hidden="true" />
                      </button>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {competitions.map((comp) => {
                    const formattedDate = comp.date
                      ? new Date(comp.date).toLocaleDateString("cs-CZ")
                      : "-";

                    return (
                      <tr key={comp._id} className="competition-row">
                        <td className="competition-row__name" data-label="Název">
                          <Link
                            className="competition-row__link"
                            to={`/zavody/${comp._id}`}
                            aria-label={`Otevřít detail závodu ${comp.name}`}
                          >
                            {comp.name}
                          </Link>
                        </td>
                        <td className="competition-row__date" data-label="Datum">
                          {formattedDate}
                        </td>
                        <td className="competition-row__place" data-label="Místo">
                          {comp.place}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : (
              <div className="competitions-empty-state" role="status">
                {hasActiveSearch ? (
                  <>
                    <p className="competitions-empty-state__message">
                      Pro zadané vyhledávání nebyl nalezen žádný závod.
                    </p>
                    <button
                      type="button"
                      className="competitions-empty-state__action"
                      onClick={clearSearch}
                    >
                      Vymazat filtr
                    </button>
                  </>
                ) : (
                  <p className="competitions-empty-state__message">
                    Aktuálně nejsou dostupné žádné závody.
                  </p>
                )}
              </div>
            )}
          </div>
          {/* PAGINACE */}
          {pageCount > 1 && (
            <div
              className="competitions-pagination"
              aria-label="Stránkování závodů"
            >
              <PrimaryButton
                className="competitions-pagination__button competitions-pagination__button--previous"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1 || isFetching}
              >
                Předchozí
              </PrimaryButton>
              <span className="competitions-pagination__status" aria-live="polite">
                Strana {page} / {pageCount}
              </span>
              <PrimaryButton
                className="competitions-pagination__button competitions-pagination__button--next"
                onClick={() => setPage((p) => Math.min(pageCount, p + 1))}
                disabled={page === pageCount || isFetching}
              >
                Další
              </PrimaryButton>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
