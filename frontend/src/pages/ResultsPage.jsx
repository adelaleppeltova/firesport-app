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

function getAthleteDisplayData(result) {
  const athlete = result?.athlete;
  const importedAthlete = result?.imported_athlete ?? {};

  return {
    id: athlete?._id ?? null,
    firstName: athlete?.first_name ?? importedAthlete.first_name ?? "",
    lastName: athlete?.last_name ?? importedAthlete.last_name ?? "",
    birthYear: athlete?.birth_year ?? importedAthlete.birth_year ?? null,
    fscode: athlete?.fscode ?? importedAthlete.fscode ?? null,
  };
}

function getResultRowId(result) {
  return result?.athlete?._id ?? result?._id;
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
  const sortedResults = [...(results ?? [])].sort((a, b) => {
    const aRank = a?.rank;
    const bRank = b?.rank;

    if (aRank == null && bRank == null) return 0;
    if (aRank == null) return 1;
    if (bRank == null) return -1;

    return aRank - bRank;
  });
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
            {sortedResults.length > 0 ? (
              sortedResults.map((r) => {
                const athlete = getAthleteDisplayData(r);
                const rowId = getResultRowId(r);
                const athleteName =
                  `${athlete.firstName} ${athlete.lastName}`.trim() ||
                  "Neznámý závodník";

                return (
                  <tr
                    id={`row-${rowId}`}
                    key={rowId}
                    className={
                      highlightedId === String(athlete.id) ? "highlight" : ""
                    }
                  >
                    <td className="results-table__start-number">
                      {r.start_number ?? ""}
                    </td>
                    <td className="results-table__athlete">
                      {athlete.id ? (
                        <Link
                          className="results-row__link"
                          to={`/zavodnici/${athlete.id}`}
                          aria-label={`Otevřít profil závodníka ${athleteName}`}
                        >
                          {athleteName}
                        </Link>
                      ) : (
                        <span className="results-row__label">{athleteName}</span>
                      )}
                    </td>
                    <td className="results-table__birth-year">
                      {athlete.birthYear ?? "—"}
                    </td>
                    <td className="results-table__fscode">
                      {athlete.fscode ?? "—"}
                    </td>
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
                );
              })
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
