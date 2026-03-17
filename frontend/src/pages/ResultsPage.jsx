import React, { useEffect } from "react";
import { Link, useParams, useLocation } from "react-router-dom";
import { useResultsByCategory, useCompetitionDetail } from "../hooks/useApi";
import PageContextNav from "../components/PageContextNav";
import formatCategoryName from "../utils/formatCategoryName";

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
  const categoryName =
    formatCategoryName(
      competition?.categories?.find(
        (cat) => String(cat.id) === String(categoryId),
      )?.name,
    ) || "Název kategorie neznámý";

  if (isLoading || isCompLoading) return <div>Načítání...</div>;
  if (error) return <div>Chyba při načítání výsledků.</div>;

  return (
    <div className="results-page page">
      <PageContextNav
        items={[
          { label: "Závody", to: "/zavody" },
          {
            label: competition?.name || "Detail závodu",
            to: id ? `/zavody/${id}` : "/zavody",
          },
          { label: categoryName },
        ]}
        action={{
          label: "Zpět na detail závodu",
          to: id ? `/zavody/${id}` : "/zavody",
        }}
      />

      <header className="results-page__header">
        <h1>Výsledky</h1>
        <div className="results-page__meta">
          <p className="results-page__competition">
            {competition?.name || "Název soutěže neznámý"}
          </p>
          <p className="results-page__date">
            {competition?.date
              ? new Date(competition.date).toLocaleDateString("cs-CZ")
              : "Datum neznámé"}
          </p>
        </div>
        <p className="results-page__category">{categoryName}</p>
      </header>
      <div className="results-table-wrapper">
        <table className="results-table">
          <colgroup>
            <col className="results-table__col results-table__col--start-number" />
            <col className="results-table__col results-table__col--athlete" />
            <col className="results-table__col results-table__col--birth-year" />
            <col className="results-table__col results-table__col--fscode" />
            <col className="results-table__col results-table__col--team" />
            <col className="results-table__col results-table__col--attempt" />
            <col className="results-table__col results-table__col--attempt" />
            <col className="results-table__col results-table__col--final-time" />
            <col className="results-table__col results-table__col--rank" />
          </colgroup>
          <thead>
            <tr>
              <th className="results-table__start-number-heading">Číslo</th>
              <th>Závodník</th>
              <th className="results-table__birth-year-heading">
                Rok narození
              </th>
              <th className="results-table__fscode-heading">FSCode</th>
              <th>Sbor</th>
              <th className="results-table__attempt-heading">Čas 1</th>
              <th className="results-table__attempt-heading">Čas 2</th>
              <th className="results-table__final-time-heading">
                Výsledný čas
              </th>
              <th className="results-table__rank-heading">Pořadí</th>
            </tr>
          </thead>
          <tbody>
            {results && results.length > 0 ? (
              results.map((r) => (
                <tr
                  id={`row-${r.athlete._id}`}
                  key={r.athlete._id}
                  className={
                    highlightedId === String(r.athlete._id) ? "highlight" : ""
                  }
                >
                  <td className="results-table__start-number">
                    {r.start_number ?? ""}
                  </td>
                  <td className="results-table__athlete">
                    <Link
                      className="results-row__link"
                      to={`/zavodnici/${r.athlete._id}`}
                      aria-label={`Otevřít profil závodníka ${r.athlete.first_name} ${r.athlete.last_name}`}
                    >
                      {r.athlete.first_name} {r.athlete.last_name}
                    </Link>
                  </td>
                  <td className="results-table__birth-year">
                    {r.athlete.birth_year}
                  </td>
                  <td className="results-table__fscode">{r.athlete.fscode}</td>
                  <td className="results-table__team">{r.team}</td>
                  <td className="results-table__attempt">
                    {getAttempt(r.times, 1)}
                  </td>
                  <td className="results-table__attempt">
                    {getAttempt(r.times, 2)}
                  </td>
                  <td className="results-table__final-time">
                    {renderTime(r.final_time, r.final_time_status)}
                  </td>
                  <td className="results-table__rank">{r.rank}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={9}>Žádné výsledky</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
