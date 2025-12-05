import { useParams } from "react-router-dom";
import { useResultsByCategory, useCompetitionDetail } from "../hooks/useApi";

// Pomocná funkce pro zobrazení času
function renderTime(time, status) {
  if (status === "invalid") return "NP";
  if (time == null) return "";
  return time;
}

export default function ResultsPage() {
  const { id, categoryId } = useParams();
  const {
    data: results,
    isLoading,
    error,
  } = useResultsByCategory(id, categoryId);
  const { data: competition, isLoading: isCompLoading } =
    useCompetitionDetail(id);

  if (isLoading || isCompLoading) return <div>Načítání...</div>;
  if (error) return <div>Chyba při načítání výsledků.</div>;

  return (
    <div className="results-page">
      <h1>Výsledky</h1>
      <h2>
        {competition?.name || "Název soutěže neznámý"},{" "}
        {competition?.date
          ? new Date(competition.date).toLocaleDateString("cs-CZ")
          : "Datum neznámé"}
      </h2>
      <p>
        {competition?.categories?.find(
          (cat) => String(cat.id) === String(categoryId)
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
                <tr key={idx}>
                  <td>{r.start_number ?? ""}</td>
                  <td>{r.athlete.first_name}</td>
                  <td>{r.athlete.last_name}</td>
                  <td>{r.athlete.birth_year}</td>
                  <td>{r.athlete.fscode}</td>
                  <td>{r.athlete.team}</td>
                  <td>{renderTime(r.time_1, r.time_1_status)}</td>
                  <td>{renderTime(r.time_2, r.time_2_status)}</td>
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
