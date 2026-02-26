import { useParams } from "react-router-dom";
import { useAthleteDetail } from "../hooks/useApi";

const formatDate = (dateString) => {
  if (!dateString) return "-";
  const date = new Date(dateString);
  return `${date.getDate()}. ${date.getMonth() + 1}. ${date.getFullYear()}`;
};

export default function AthleteDetailPage() {
  const { id } = useParams();
  const { data, isLoading, error } = useAthleteDetail(id);

  if (isLoading) return <div className="athlete-detail-page">Načítání...</div>;
  if (error || !data)
    return <div className="athlete-detail-page">Chyba při načítání dat.</div>;

  const { athlete, best_time, results } = data;

  return (
    <div className="athlete-detail-page page">
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
              <td>{athlete.birth_year || "-"}</td>
            </tr>
            <tr>
              <th>Sbor</th>
              <td>{athlete.teams.map((team) => team).join(", ") || "-"}</td>
            </tr>
            <tr>
              <th>Okres</th>
              <td>{athlete.district || "-"}</td>
            </tr>
            <tr>
              <th>FSCode</th>
              <td>{athlete.fscode || "-"}</td>
            </tr>
            {/* <tr>
              <th>Kategorie</th>
              <td>{athlete.category || "-"}</td>
            </tr> */}
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
              <th>Závod</th>
              <th>Místo</th>
              <th>Kategorie</th>
              <th>Výsledný čas</th>
            </tr>
          </thead>
          <tbody>
            {results && results.length > 0 ? (
              results.map((r, idx) => (
                <tr
                  onClick={() => window.location.href = `/zavody/${r.competition._id}/vysledky/${r.category._id}#${athlete._id}`}
                  className="athlete-results-card-row"
                  key={idx}
                >
                  <td>{formatDate(r.competition?.date)}</td>
                  <td>{r.competition?.name}</td>
                  <td>{r.competition?.place}</td>
                  <td>{r.category.name}</td>
                  <td>
                    {(r.final_time ? r.final_time.toFixed(2) + " s" : "") +
                      (r.final_time_status === "valid" ? "" : " NP")}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5}>Žádné výsledky</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
