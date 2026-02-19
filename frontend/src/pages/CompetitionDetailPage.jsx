import { useParams, useNavigate, Link } from "react-router-dom";
import { useCompetitionDetail } from "../hooks/useApi";
import Card from "../components/Card";

export default function CompetitionDetailPage() {
  const { id, categoryId } = useParams();
  const navigate = useNavigate();
  const { data, isLoading, error } = useCompetitionDetail(id, categoryId);

  if (isLoading)
    return <div className="competition-detail-page">Načítání...</div>;
  if (error || !data)
    return (
      <div className="competition-detail-page">Chyba při načítání dat.</div>
    );

  const {
    name,
    date,
    place,
    league,
    athlete_count,
    categories,
    results_by_category,
  } = data;

  return (
    <div className="competition-detail-page page">
      <h1>Závod</h1>
      <div className="competition-detail-table-wrapper">
        <table className="competition-detail-info-table">
          <tbody>
            <tr>
              <th>Datum</th>
              <td>{date ? new Date(date).toLocaleDateString("cs-CZ") : "-"}</td>
            </tr>
            <tr>
              <th>Místo</th>
              <td>{place || "-"}</td>
            </tr>
            <tr>
              <th>Název</th>
              <td>{name || "-"}</td>
            </tr>
            <tr>
              <th>Liga</th>
              <td>{league || "-"}</td>
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
              key={cat.id}
              to={`/zavody/${id}/vysledky/${encodeURIComponent(cat.id)}`}
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
