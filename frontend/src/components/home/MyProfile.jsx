import { useMe, useAthleteOverview } from "../../hooks/useApi";

export default function MyProfile() {
  const { data: me, isLoading: meLoading, error: meError } = useMe();
  const {
    data: overview,
    isLoading: overviewLoading,
    error: overviewError,
  } = useAthleteOverview(me?.athlete_id);

  if (meLoading || overviewLoading) return <div className="skeleton" />;
  if (meError || overviewError)
    return <p className="empty-state">Chyba načítání</p>;
  if (!overview) return <p className="empty-state">Žádná data o profilu</p>;

  return (
    <div className="my-profile">
      <div className="my-profile__athlete">
        <div>
          <h3 className="my-profile__name">
            {overview.first_name} {overview.last_name} ({overview.birth_year})
          </h3>
          <p className="my-profile__team">{overview.team}</p>
        </div>
        <p className="my-profile__time">
          Nejlepší čas: {overview.best_time?.toFixed(2)} s
        </p>
        {/* <p className=" my-profile__team">
          {overview.best_performance.competition_place || "—"},{" "}
          {overview.best_performance.competition_date || "—"}
        </p> */}

        <p className="my-profile__competitions">
          Celkový počet závodů: {overview.total_competitions}
        </p>
      </div>
    </div>
  );
}
