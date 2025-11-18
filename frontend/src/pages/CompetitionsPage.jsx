import { useNavigate } from "react-router-dom";
import { useCompetitions } from "../hooks/useApi";

export default function CompetitionsPage() {
  const { data: competitions, isLoading, error } = useCompetitions();
  const navigate = useNavigate();

  if (isLoading) return <div className="competitions-page">Načítání...</div>;
  if (error)
    return <div className="competitions-page">Chyba při načítání dat.</div>;

  return (
    <div className="competitions-page athletes-page">
      <h1>Závody</h1>
      <div className="athletes-searchbar-wrapper">
        <div className="athletes-searchbar-iconwrap">
          <input
            className="athletes-searchbar"
            type="text"
            placeholder="Hledat název, místo nebo datum..."
            disabled
          />
          <i className="fa-solid fa-magnifying-glass athletes-searchbar-icon" />
        </div>
      </div>
      <div className="athletes-table-wrapper">
        <table className="athletes-table">
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
                  className="athlete-row"
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
