import { useParams, useNavigate } from "react-router-dom";
import { useCompetitionDetail } from "../hooks/useApi";
import "../assets/styles/pages/_athlete-detail.scss";
import Card from "../components/Card";

export default function CompetitionDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data, isLoading, error } = useCompetitionDetail(id);

  if (isLoading) return <div className="athlete-detail-page">Načítání...</div>;
  if (error || !data)
    return <div className="athlete-detail-page">Chyba při načítání dat.</div>;

  const {
    competition_name,
    competition_date,
    competition_place,
    athlete_count,
    categories,
    results_by_category,
  } = data;

  return (
    <div className="athlete-detail-page">
      <h1>Závod</h1>
      <div className="athletes-table-wrapper">
        <table className="athlete-detail-info-table">
          <tbody>
            <tr>
              <th>Datum</th>
              <td>
                {competition_date
                  ? new Date(competition_date).toLocaleDateString("cs-CZ")
                  : "-"}
              </td>
            </tr>
            <tr>
              <th>Místo</th>
              <td>{competition_place || "-"}</td>
            </tr>
            <tr>
              <th>Název</th>
              <td>{competition_name || "-"}</td>
            </tr>
            <tr>
              <th>Počet závodníků</th>
              <td>{athlete_count ?? "-"}</td>
            </tr>
            <tr>
              <th>Kategorie</th>
              <td>
                {categories && categories.length > 0
                  ? categories.map((cat) => cat.name).join(", ")
                  : "-"}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <hr className="athlete-detail-divider" />

      <h2>Výsledkové listiny</h2>
      <div className="athlete-results">
        {categories && categories.length > 0 ? (
          categories.map((cat) => (
            <Card
              key={cat._id}
              className="athlete-results-card-row"
              onClick={() =>
                navigate(
                  `/zavody/${id}/vysledky/${encodeURIComponent(cat._id)}`
                )
              }
            >
              {cat.name}
              <span style={{ float: "right" }}>&#8250;</span>
            </Card>
          ))
        ) : (
          <div>Výsledky nejsou k dispozici.</div>
        )}
      </div>
    </div>
  );
}
