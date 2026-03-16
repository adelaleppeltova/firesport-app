import { useEffect, useState, useRef } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAthletes } from "../hooks/useApi";
import PrimaryButton from "../components/PrimaryButton";
import { scrollPageToTop } from "../components/ScrollToTop";

const PAGE_SIZE = 25;
const MAX_VISIBLE_TEAMS = 2;

function formatTeams(teams = []) {
  const visibleTeams = teams.slice(0, MAX_VISIBLE_TEAMS);
  const remainingCount = teams.length - visibleTeams.length;

  if (remainingCount <= 0) {
    return visibleTeams.join(", ");
  }

  return `${visibleTeams.join(", ")} +${remainingCount}`;
}

export default function AthletesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const debounceRef = useRef(null);

  // URL je jediný zdroj pravdy pro q a page.
  // inputValue je lokální stav pouze pro ovládací prvek inputu (debounce).
  const committedSearch = searchParams.get("q") || "";
  const page = Number(searchParams.get("page")) || 1;

  const [inputValue, setInputValue] = useState(committedSearch);

  // Pokud se URL změní zvenčí (např. tlačítko Zpět), synchronizuj input
  const prevCommittedRef = useRef(committedSearch);
  useEffect(() => {
    if (committedSearch !== prevCommittedRef.current) {
      setInputValue(committedSearch);
      prevCommittedRef.current = committedSearch;
    }
  }, [committedSearch]);

  const setPage = (p) => {
    const params = new URLSearchParams(searchParams);
    if (p > 1) {
      params.set("page", String(p));
    } else {
      params.delete("page");
    }
    setSearchParams(params, { replace: true });
    scrollPageToTop();
  };

  // Debounce: po 300 ms zapíše hodnotu z inputu do URL (a resetuje stránku).
  // Pokud se inputValue rovná committedSearch (např. při prvním renderu),
  // URL se vůbec nedotkneme – zachováme ostatní params jako ?page=.
  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      if (inputValue === committedSearch) return;
      const params = new URLSearchParams(searchParams);
      if (inputValue) {
        params.set("q", inputValue);
      } else {
        params.delete("q");
      }
      // při nové query vždy reset na str. 1
      params.delete("page");
      setSearchParams(params, { replace: true });
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [inputValue]); // eslint-disable-line react-hooks/exhaustive-deps

  const { data, isLoading, error, isFetching } = useAthletes({
    search: committedSearch,
    page,
    pageSize: PAGE_SIZE,
  });

  const athletes = data?.items || [];
  const total = data?.total || 0;
  const pageCount = Math.ceil(total / PAGE_SIZE);
  const showInitialLoading = isLoading && !data;
  const hasActiveSearch = committedSearch.trim().length > 0;
  const resultsStatusMessage = isFetching
    ? "Aktualizuji výsledky..."
    : hasActiveSearch
      ? `Nalezeno ${total} závodníků.`
      : "";
  const showResultsStatus = Boolean(resultsStatusMessage) && !error && !showInitialLoading;

  const clearSearch = () => {
    setInputValue("");
    const params = new URLSearchParams(searchParams);
    params.delete("q");
    params.delete("page");
    setSearchParams(params, { replace: true });
  };

  return (
    <div className="athletes-page page">
      <h1>Závodníci</h1>
      <div className="athletes-searchbar-wrapper">
        <div className="athletes-searchbar-iconwrap">
          <input
            className="athletes-searchbar"
            type="text"
            placeholder="Hledat jméno, rok nebo sbor..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            aria-describedby={
              showResultsStatus ? "athletes-results-status" : undefined
            }
          />
          <i
            className={`fa-solid ${
              isFetching
                ? "fa-spinner athletes-searchbar-icon athletes-searchbar-icon--spinning"
                : "fa-magnifying-glass athletes-searchbar-icon"
            }`}
          />
        </div>
      </div>
      {error ? (
        <p className="athletes-feedback athletes-feedback--error">
          Nepodařilo se načíst seznam závodníků.
        </p>
      ) : showInitialLoading ? (
        <p className="athletes-feedback" aria-live="polite">
          Načítám seznam závodníků...
        </p>
      ) : (
        <>
          {showResultsStatus && (
            <div
              id="athletes-results-status"
              className={`athletes-results-status${
                isFetching ? " athletes-results-status--loading" : ""
              }`}
              aria-live="polite"
              aria-atomic="true"
            >
              {isFetching && (
                <span
                  className="athletes-results-status__dot"
                  aria-hidden="true"
                />
              )}
              <span>{resultsStatusMessage}</span>
            </div>
          )}
          <div
            className={`athletes-table-wrapper${
              isFetching ? " athletes-table-wrapper--fetching" : ""
            }`}
            aria-busy={isFetching}
          >
            {athletes.length > 0 ? (
              <table className="athletes-table">
                <colgroup>
                  <col className="athletes-table__col athletes-table__col--name" />
                  <col className="athletes-table__col athletes-table__col--year" />
                  <col className="athletes-table__col athletes-table__col--teams" />
                </colgroup>
                <thead>
                  <tr>
                    <th>Jméno</th>
                    <th className="athletes-table__year-heading">Rok</th>
                    <th>Sbor</th>
                  </tr>
                </thead>
                <tbody>
                  {athletes.map((athlete) => (
                    <tr key={athlete._id} className="athlete-row">
                      <td className="athlete-row__name">
                        <Link
                          className="athlete-row__link"
                          to={`/zavodnici/${athlete._id}`}
                          aria-label={`Otevřít profil závodníka ${athlete.first_name} ${athlete.last_name}`}
                        >
                          {athlete.first_name} {athlete.last_name}
                        </Link>
                      </td>
                      <td className="athlete-row__year">{athlete.birth_year}</td>
                      <td className="athlete-row__teams">
                        {formatTeams(athlete.teams)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="athletes-empty-state" role="status">
                {hasActiveSearch ? (
                  <>
                    <p className="athletes-empty-state__message">
                      Pro zadané vyhledávání nebyl nalezen žádný závodník.
                    </p>
                    <button
                      type="button"
                      className="athletes-empty-state__action"
                      onClick={clearSearch}
                    >
                      Vymazat filtr
                    </button>
                  </>
                ) : (
                  <p className="athletes-empty-state__message">
                    Aktuálně nejsou dostupní žádní závodníci.
                  </p>
                )}
              </div>
            )}
          </div>
          {/* PAGINACE */}
          {pageCount > 1 && (
            <div className="athletes-pagination" aria-label="Stránkování závodníků">
              <PrimaryButton
                className="athletes-pagination__button athletes-pagination__button--previous"
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page === 1 || isFetching}
              >
                Předchozí
              </PrimaryButton>
              <span className="athletes-pagination__status" aria-live="polite">
                Strana {page} / {pageCount}
              </span>
              <PrimaryButton
                className="athletes-pagination__button athletes-pagination__button--next"
                onClick={() => setPage(Math.min(pageCount, page + 1))}
                disabled={page === pageCount || isFetching}
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
