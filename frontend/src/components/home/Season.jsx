import { useMe, useAthletePerformanceInYear } from "../../hooks/useApi";

export default function Season() {
  const { data: me, isLoading: meLoading, error: meError } = useMe();

  const {
    data: performanceInYear,
    isLoading: overviewLoading,
    error: overviewError,
  } = useAthletePerformanceInYear(me?.athlete_id);

  if (meLoading || overviewLoading) return <div className="skeleton" />;
  if (meError || overviewError)
    return <p className="empty-state">Chyba načítání</p>;
  if (!performanceInYear)
    return <p className="empty-state">Žádná data o sezóně</p>;

  return (
    <div className="season">
      <div className="season__info">
        <p className="season__best-time">
          Nejlepší čas v sezóně: {performanceInYear.best_time?.toFixed(2)} s
        </p>
        <p className="season__average-time">
          Průměrný čas v sezóně: {performanceInYear.average_time?.toFixed(2)} s
        </p>
        <p className="season__competition-count">
          Počet závodů v sezóně: {performanceInYear.competitions}
        </p>
      </div>
    </div>
  );
}
