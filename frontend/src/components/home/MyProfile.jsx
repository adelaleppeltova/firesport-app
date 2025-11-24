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
  if (!overview?.last_activity)
    return <p className="empty-state">Žádná aktivita</p>;

  const activity = overview.last_activity;

  return (
    <div className="my-profile">
      <div className="my-profile__athlete">
        <div>
          <h3 className="my-profile__name">
            {overview.athlete_name} ({overview.athlete_birth_year})
          </h3>
          <p className="my-profile__team">{overview.athlete_team}</p>
        </div>
        <p className="my-profile__time">
          Nejlepší čas: {overview.best_time?.toFixed(2)} s
        </p>
        <p className="my-profile__competitions">
          Celkový počet závodů: {overview.competition_count}
        </p>
      </div>
    </div>
  );
}
