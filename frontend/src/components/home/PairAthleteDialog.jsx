import { useState, useEffect, useRef } from "react";
import { useAthletes, usePairAthlete } from "../../hooks/useApi";
import PrimaryButton from "../PrimaryButton";

export default function PairAthleteDialog({ onClose }) {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const debounceRef = useRef(null);
  const inputRef = useRef(null);
  const pairMutation = usePairAthlete();

  // Zavření přes Escape
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  // Focus na input při otevření
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedQuery(query);
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [query]);

  const { data: searchResults, isFetching } = useAthletes({
    search: debouncedQuery,
    page: 1,
    pageSize: 25,
  });

  const handleSelect = async (athleteId) => {
    if (pairMutation.isPending) return;
    try {
      await pairMutation.mutateAsync(athleteId);
      onClose();
    } catch (err) {
      // chyba je ošetřena v mutaci
    }
  };

  const isPairing = pairMutation.isPending;

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div
        className="dialog-content"
        role="dialog"
        aria-modal="true"
        aria-labelledby="pair-athlete-dialog-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="pair-athlete-dialog-title">Vybrat závodníka</h2>
        <div className="athletes-searchbar-wrapper">
          <div className="athletes-searchbar-iconwrap">
            <input
              ref={inputRef}
              className="athletes-searchbar"
              type="text"
              placeholder="Jméno, příjmení nebo FS kód..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              disabled={isPairing}
              aria-label="Hledat atleta"
            />
            <i
              className="fa-solid fa-magnifying-glass athletes-searchbar-icon"
              aria-hidden="true"
            />
          </div>
        </div>

        {debouncedQuery && (
          <p className="athletes-search-count" aria-live="polite">
            {isFetching ? "Hledám..." : ""}
          </p>
        )}

        {isPairing && (
          <p className="athletes-search-count" aria-live="polite">
            Přiřazuji závodníka…
          </p>
        )}

        {!isFetching &&
          searchResults?.items &&
          searchResults.items.length > 0 && (
            <ul className="athlete-list" aria-label="Výsledky hledání">
              {searchResults.items.map((athlete) => (
                <li key={athlete._id}>
                  <button
                    type="button"
                    onClick={() => handleSelect(athlete._id)}
                    className={`athlete-list__button${
                      isPairing ? " athlete-list__item--disabled" : ""
                    }`}
                    disabled={isPairing}
                  >
                    <strong>
                      {athlete.first_name} {athlete.last_name}
                    </strong>
                    <span className="athlete-meta">
                      {[
                        athlete.birth_year,
                        athlete.teams?.length ? athlete.teams.join(", ") : null,
                        athlete.fscode,
                      ]
                        .filter(Boolean)
                        .join(" • ")}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}

        {!isFetching &&
          debouncedQuery.length >= 2 &&
          searchResults?.items?.length === 0 && (
            <p className="empty-state">Závodník nenalezen.</p>
          )}

        <div className="button-center">
          <PrimaryButton
            className="btn-secondary"
            onClick={onClose}
            disabled={isPairing}
            style={{ width: "min(200px,100%)", fontSize: "1.2rem" }}
          >
            Zavřít
          </PrimaryButton>
        </div>
      </div>
    </div>
  );
}
