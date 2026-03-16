import Card from "../components/Card";
import MyProfile from "../components/home/MyProfile";
import Season from "../components/home/Season";
import History from "../components/home/History";
import PerformanceStability from "../components/home/PerformanceStability";
import PerformanceByYear from "../components/home/PerformanceByYear";
import PairAthleteCard from "../components/home/PairAthleteCard";
import HomeQuickActions from "../components/home/HomeQuickActions";
import UnpairAthleteCard from "../components/home/UnpairAthleteCard";
import {
  useAthletePerformanceHistory,
  useAthletePerformanceStability,
  useMe,
} from "../hooks/useApi";
import {
  getHistoryTrendModifier,
  getStabilityModifier,
} from "../components/home/cardModifiers";

export default function HomePage() {
  const { data: user, isLoading } = useMe();
  const athleteId = user?.athlete_id ?? null;
  const { data: historyData } = useAthletePerformanceHistory(athleteId);
  const { data: stabilityData } = useAthletePerformanceStability(athleteId);
  const historyTrend = getHistoryTrendModifier(
    historyData?.performance_indicator?.trend,
  );
  const stabilityTrend = getStabilityModifier(stabilityData?.stability_rating);

  if (isLoading) {
    return (
      <div className="home-page page">
        <div className="dashboard">
          <div className="dashboard__col">
            <div className="skeleton skeleton--md" />
            <div className="skeleton skeleton--sm" />
            <div className="skeleton skeleton--lg" />
          </div>
          <div className="dashboard__col">
            <div className="skeleton skeleton--lg" />
            <div className="skeleton skeleton--chart" />
          </div>
        </div>
      </div>
    );
  }

  const isPaired = user?.athlete_id;

  if (!isPaired) {
    return (
      <div className="home-page page">
        <PairAthleteCard />
      </div>
    );
  }

  return (
    <div className="home-page page">
      <HomeQuickActions athleteId={athleteId} />
      <div className="dashboard">
        {/* Levý sloupec: profil, sezóna, stabilita */}
        <div className="dashboard__col">
          <Card title="Můj profil">
            <MyProfile athleteId={athleteId} />
          </Card>
          <Card title="Aktuální sezóna">
            <Season athleteId={athleteId} />
          </Card>
          <Card
            title="Stabilita výkonu"
            className={`card--stability-${stabilityTrend}`}
          >
            <PerformanceStability athleteId={athleteId} />
          </Card>
        </div>

        {/* Pravý sloupec: historie, vývoj za sezóny */}
        <div className="dashboard__col">
          <Card title="Trend výkonu" className={`card--trend-${historyTrend}`}>
            <History athleteId={athleteId} />
          </Card>
          <Card title="Výkon po sezónách">
            <PerformanceByYear athleteId={athleteId} />
          </Card>
        </div>
      </div>
      <UnpairAthleteCard />
    </div>
  );
}
