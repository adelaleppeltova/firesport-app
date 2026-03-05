import { useState, useEffect, useRef } from "react";
import { useAthletes, usePairAthlete } from "../../hooks/useApi";
import PrimaryButton from "../PrimaryButton";

export default function PairAthleteDialog({ onClose }) {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const debounceRef = useRef(null);
  const pairMutation = usePairAthlete();

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
    try {
      console.log("Pairing with athlete ID:", athleteId);
      await pairMutation.mutateAsync(athleteId);
      onClose();
    } catch (err) {
      console.error("Failed to pair athlete:", err);
      console.error("Error response:", err.response?.data);
    }
  };

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog-content" onClick={(e) => e.stopPropagation()}>
        <h2>Najít atleta</h2>
        <div className="athletes-searchbar-wrapper">
          <div className="athletes-searchbar-iconwrap">
            <input
              className="athletes-searchbar"
              type="text"
              placeholder="Jméno, příjmení nebo FS kód..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              autoFocus
            />
            <i className="fa-solid fa-magnifying-glass athletes-searchbar-icon" />
          </div>
        </div>

        {debouncedQuery && (
          <p className="athletes-search-count">
            {isFetching ? "Hledám..." : ""}
          </p>
        )}

        {!isFetching &&
          searchResults?.items &&
          searchResults.items.length > 0 && (
            <ul className="athlete-list">
              {searchResults.items.map((athlete) => (
                <li key={athlete._id} onClick={() => handleSelect(athlete._id)}>
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
                </li>
              ))}
            </ul>
          )}

        {!isFetching &&
          debouncedQuery.length >= 2 &&
          searchResults?.items?.length === 0 && (
            <p className="empty-state">Žádný atlet nenalezen</p>
          )}

        <div className="button-center">
          <PrimaryButton
            className="btn-secondary"
            onClick={onClose}
            style={{ width: "min(200px,100%)", fontSize: "1.2rem" }}
          >
            Zavřít
          </PrimaryButton>
        </div>
      </div>
    </div>
  );
}
