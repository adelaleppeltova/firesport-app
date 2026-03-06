import { useEffect, useState, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAthletes } from "../hooks/useApi";
import PrimaryButton from "../components/PrimaryButton";

const PAGE_SIZE = 25;

export default function AthletesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
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
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  // Debounce: po 300 ms zapíše hodnotu z inputu do URL (a resetuje stránku)
  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      const params = new URLSearchParams();
      if (inputValue) params.set("q", inputValue);
      // při nové query vždy reset na str. 1
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
          />
          <i className="fa-solid fa-magnifying-glass athletes-searchbar-icon" />
        </div>
      </div>
      {committedSearch && (
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
                onClick={() => setPage(Math.max(1, page - 1))}
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
                onClick={() => setPage(Math.min(pageCount, page + 1))}
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
