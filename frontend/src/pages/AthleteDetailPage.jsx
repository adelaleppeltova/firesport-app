import { useParams } from "react-router-dom";
import { useAthleteDetail } from "../hooks/useApi";

export default function AthleteDetailPage() {
  const { id } = useParams();
  const { data, isLoading, error } = useAthleteDetail(id);

  if (isLoading) return <div className="athlete-detail-page">Načítání...</div>;
  if (error || !data)
    return <div className="athlete-detail-page">Chyba při načítání dat.</div>;

  const { athlete, best_time, results } = data;

  return (
    <div className="athlete-detail-page">
      <h1>Závodník</h1>
      <div className="athletes-table-wrapper">
        <table className="athlete-detail-info-table">
          <tbody>
            <tr>
              <th>Jméno</th>
              <td>
                {athlete.first_name} {athlete.last_name}
              </td>
            </tr>
            <tr>
              <th>Rok narození</th>
              <td>{athlete.birth_year}</td>
            </tr>
            <tr>
              <th>Sbor</th>
              <td>{athlete.team}</td>
            </tr>
            <tr>
              <th>FSCode</th>
              <td>{athlete.fscode}</td>
            </tr>
            <tr>
              <th>Kategorie</th>
              <td>{athlete.category || "-"}</td>
            </tr>
            <tr>
              <th>Nejrychlejší čas</th>
              <td>{best_time ? best_time.toFixed(2) + " s" : "-"}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <hr className="athlete-detail-divider" />
      <h2>Výsledky</h2>
      <div className="athletes-table-wrapper">
        <table className="athlete-detail-table">
          <thead>
            <tr>
              <th>Datum</th>
              <th>Místo</th>
              <th>Výsledný čas</th>
            </tr>
          </thead>
          <tbody>
            {results && results.length > 0 ? (
              results.map((r, idx) => (
                <tr key={r._id || `${r.date}-${r.place}-${idx}`}>
                  <td>{r.date}</td>
                  <td>{r.place}</td>
                  <td>{r.final_time ? r.final_time.toFixed(2) + " s" : "-"}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={3}>Žádné výsledky</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
