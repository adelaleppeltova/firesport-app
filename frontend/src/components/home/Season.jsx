import { useMe, useAthleteOverview } from "../../hooks/useApi";

export default function Season() {
  const { data: me, isLoading: meLoading, error: meError } = useMe();

  const {
    data: overview,
    isLoading: overviewLoading,
    error: overviewError,
  } = useAthleteOverview(me?.athlete_id);

  if (meLoading || overviewLoading) return <div className="skeleton" />;
  if (meError || overviewError)
    return <p className="empty-state">Chyba načítání</p>;
  if (!overview) return <p className="empty-state">Žádná data o sezóně</p>;

  return (
    <div className="season">
      <div className="season__info">
        <p className="season__best-time">
          Nejlepší čas v sezóně: {overview.best_time_in_year?.toFixed(2)} s
        </p>
        <p className="season__average-time">
          Průměrný čas v sezóně: {overview.average_time_in_year?.toFixed(2)} s
        </p>
        <p className="season__competition-count">
          Počet závodů v sezóně: {overview.total_competitions}
        </p>
      </div>
    </div>
  );
}
