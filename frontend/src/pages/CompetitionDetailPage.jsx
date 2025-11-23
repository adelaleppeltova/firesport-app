import { useParams, useNavigate, Link } from "react-router-dom";
import { useCompetitionDetail } from "../hooks/useApi";
import Card from "../components/Card";

export default function CompetitionDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data, isLoading, error } = useCompetitionDetail(id);

  if (isLoading)
    return <div className="competition-detail-page">Načítání...</div>;
  if (error || !data)
    return (
      <div className="competition-detail-page">Chyba při načítání dat.</div>
    );

  const {
    competition_name,
    competition_date,
    competition_place,
    competition_type,
    athlete_count,
    categories,
    results_by_category,
  } = data;

  return (
    <div className="competition-detail-page">
      <h1>Závod</h1>
      <div className="competition-detail-table-wrapper">
        <table className="competition-detail-info-table">
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
              <th>Typ soutěže</th>
              <td>{competition_type || "-"}</td>
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
      <hr className="competition-detail-divider" />

      <h2>Výsledkové listiny</h2>
      <div className="competition-detail-list">
        {categories && categories.length > 0 ? (
          categories.map((cat) => (
            <Link
              key={cat._id}
              to={`/zavody/${id}/vysledky/${encodeURIComponent(cat._id)}`}
              style={{ textDecoration: "none", color: "inherit" }}
            >
              <Card className="competition-detail-results-card-row">
                {cat.name}
                <span style={{ float: "right" }}>&#8250;</span>
              </Card>
            </Link>
          ))
        ) : (
          <div>Výsledky nejsou k dispozici.</div>
        )}
      </div>
    </div>
  );
}
