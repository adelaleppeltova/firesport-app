import { useParams } from "react-router-dom";
import { useResultsByCategory, useCompetitionDetail } from "../hooks/useApi";

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
        {competition?.competition_name || "Název soutěže neznámý"},{" "}
        {competition?.competition_date
          ? new Date(competition.competition_date).toLocaleDateString("cs-CZ")
          : "Datum neznámé"}
      </h2>
      <p>
        {competition?.categories?.find(
          (cat) => String(cat._id) === String(categoryId)
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
                  <td>{r.first_name}</td>
                  <td>{r.last_name}</td>
                  <td>{r.birth_year}</td>
                  <td>{r.fscode}</td>
                  <td>{r.team}</td>
                  <td>{r.time_1}</td>
                  <td>{r.time_2}</td>
                  <td>{r.final_time}</td>
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
