import React, { useEffect } from "react";
import { useParams, useLocation, useNavigate } from "react-router-dom";
import { useResultsByCategory, useCompetitionDetail } from "../hooks/useApi";

// Pomocná funkce pro zobrazení času
function renderTime(time, status) {
  if (status === "invalid") return "NP";
  if (time == null) return "";
  return time;
}

// Pomocná funkce pro získání pokusu z pole times
function getAttempt(times, attemptNum) {
  const t = times?.find((t) => t.attempt === attemptNum);
  return t ? renderTime(t.time, t.status) : "";
}

export default function ResultsPage() {
  const { id, categoryId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const {
    data: results,
    isLoading,
    error,
  } = useResultsByCategory(id, categoryId);
  const { data: competition, isLoading: isCompLoading } =
    useCompetitionDetail(id);

  // scroll to highlighted athlete when hash present
  useEffect(() => {
    if (!results || results.length === 0) return;
    const hash = location.hash;
    if (hash) {
      const targetId = hash.replace("#", "");
      const row = document.getElementById(`row-${targetId}`);
      if (row) {
        row.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }
  }, [location.hash, results]);

  // compute highlight id to apply class in render
  const highlightedId = location.hash ? location.hash.replace("#", "") : null;

  if (isLoading || isCompLoading) return <div>Načítání...</div>;
  if (error) return <div>Chyba při načítání výsledků.</div>;

  return (
    <div className="results-page page">
      <h1>Výsledky</h1>
      <h2>
        {competition?.name || "Název soutěže neznámý"},{" "}
        {competition?.date
          ? new Date(competition.date).toLocaleDateString("cs-CZ")
          : "Datum neznámé"}
      </h2>
      <p>
        {competition?.categories?.find(
          (cat) => String(cat.id) === String(categoryId),
        )?.name || "Název kategorie neznámý"}
      </p>
      <div className="results-table-wrapper">
        <table className="results-table">
          <thead>
            <tr>
              <th>Startovní číslo</th>
              <th>Jméno</th>
              <th>Příjmení</th>
              <th>Rok narození</th>
              <th>FSCode</th>
              <th>Sbor</th>
              <th>Čas 1</th>
              <th>Čas 2</th>
              <th>Výsledný čas</th>
              <th>Pořadí</th>
            </tr>
          </thead>
          <tbody>
            {results && results.length > 0 ? (
              results.map((r, idx) => (
                <tr
                  id={`row-${r.athlete._id}`}
                  key={r.athlete._id}
                  className={
                    highlightedId === String(r.athlete._id) ? "highlight" : ""
                  }
                  onClick={() => navigate(`/zavodnici/${r.athlete._id}`)}
                >
                  <td>{r.start_number ?? ""}</td>
                  <td>{r.athlete.first_name}</td>
                  <td>{r.athlete.last_name}</td>
                  <td>{r.athlete.birth_year}</td>
                  <td>{r.athlete.fscode}</td>
                  <td>{r.team}</td>
                  <td>{getAttempt(r.times, 1)}</td>
                  <td>{getAttempt(r.times, 2)}</td>
                  <td>{renderTime(r.final_time, r.final_time_status)}</td>
                  <td>{r.rank}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={10}>Žádné výsledky</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
