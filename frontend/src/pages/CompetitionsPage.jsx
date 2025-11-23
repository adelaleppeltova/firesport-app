import { useNavigate } from "react-router-dom";
import { useCompetitions } from "../hooks/useApi";

export default function CompetitionsPage() {
  const { data: competitions, isLoading, error } = useCompetitions();
  const navigate = useNavigate();

  if (isLoading) return <div className="competitions-page">Načítání...</div>;
  if (error)
    return <div className="competitions-page">Chyba při načítání dat.</div>;

  return (
    <div className="competitions-page">
      <h1>Závody</h1>
      <div className="competitions-searchbar-wrapper">
        <div className="competitions-searchbar-iconwrap">
          <input
            className="competitions-searchbar"
            type="text"
            placeholder="Hledat název, místo nebo datum..."
            disabled
          />
          <i className="fa-solid fa-magnifying-glass competitions-searchbar-icon" />
        </div>
      </div>
      <div className="competitions-table-wrapper">
        <table className="competitions-table">
          <thead>
            <tr>
              <th>Název</th>
              <th>Datum</th>
              <th>Místo</th>
            </tr>
          </thead>
          <tbody>
            {competitions && competitions.length > 0 ? (
              competitions.map((comp) => (
                <tr
                  key={comp._id}
                  className="competition-row"
                  onClick={() => navigate(`/zavody/${comp._id}`)}
                  style={{ cursor: "pointer" }}
                >
                  <td>{comp.competition_name}</td>
                  <td>
                    {comp.competition_date
                      ? new Date(comp.competition_date).toLocaleDateString(
                          "cs-CZ"
                        )
                      : "-"}
                  </td>
                  <td>{comp.competition_place}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={3}>Žádné závody</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
