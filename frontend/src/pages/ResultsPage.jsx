import { useEffect } from "react";
import { Link, useParams, useLocation } from "react-router-dom";
import { useResultsByCategory, useCompetitionDetail } from "../hooks/useApi";
import PageContextNav from "../components/PageContextNav";
import groupResultLists from "../utils/groupResultLists";

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
    fscode: athlete?.fs_codes?.[0] ?? importedAthlete.fscode ?? null,
  };
}

function getResultRowId(result) {
  return result?._id;
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
      const row = document.getElementById(`row-${targetId}`) ??
        document.querySelector(`[data-athlete-id="${CSS.escape(targetId)}"]`);
      if (row) {
        row.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }
  }, [location.hash, results]);

  // compute highlight id to apply class in render
  const highlightedId = location.hash ? location.hash.replace("#", "") : null;
  const category = competition?.categories?.find((cat) => String(cat.id) === String(categoryId));
  const categoryName = category?.name ?? "Neznámá kategorie";
  const isTeam = category?.type === "team";
  const lists = groupResultLists(results ?? [], categoryName);

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
            {competition?.name || "Neznámá soutěž"}
          </p>
          <p className="results-page__date">
            {competition?.date
              ? new Date(competition.date).toLocaleDateString("cs-CZ")
              : "Datum neznámé"}
          </p>
        </div>
        <p className="results-page__category">{category?.discipline} · {categoryName}</p>
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
              <th>{isTeam ? "Družstvo" : "Závodník"}</th>
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
          {lists.map((list) => (
            <tbody key={list.id}>
              {(lists.length > 1 || list.name !== categoryName) && (
                <tr>
                  <th colSpan={9} scope="rowgroup">
                    {list.name}{list.block && ` · ${list.block}`}
                  </th>
                </tr>
              )}
              {list.results.map((r) => {
                const athlete = getAthleteDisplayData(r);
                const rowId = getResultRowId(r);
                const athleteName =
                  isTeam ? r.team || "—" : (
                    athlete.firstName && athlete.lastName
                      ? `${athlete.firstName} ${athlete.lastName}`
                      : r.source_full_name || "Jméno nezjištěno"
                  );

                return (
                  <tr
                    id={`row-${rowId}`}
                    key={rowId}
                    data-athlete-id={athlete.id ?? undefined}
                    className={
                      highlightedId === rowId || highlightedId === athlete.id ? "highlight" : ""
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
              })}
            </tbody>
          ))}
          {!lists.length && <tbody><tr><td colSpan={9}>Žádné výsledky</td></tr></tbody>}
        </table>
      </div>
    </div>
  );
}
