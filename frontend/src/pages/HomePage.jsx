import Card from "../components/Card";
import MyProfile from "../components/home/MyProfile";
import Season from "../components/home/Season";
import History from "../components/home/History";
import PerformanceStability from "../components/home/PerformanceStability";
import PerformanceByYear from "../components/home/PerformanceByYear";
import PairAthleteCard from "../components/home/PairAthleteCard";
import { useMe } from "../hooks/useApi";

export default function HomePage() {
  const { data: user, isLoading } = useMe();

  if (isLoading) {
    return <div className="home-page page">Načítání...</div>;
  }

  const isPaired = user?.athlete_id;

  if (!isPaired) {
    return (
      <div className="home-page page">
        <PairAthleteCard />
      </div>
    );
  }

  const athleteId = user.athlete_id;

  return (
    <div className="home-page page">
      <Card title="Můj profil">
        <MyProfile athleteId={athleteId} />
      </Card>
      <Card title="Aktuální sezóna">
        <Season athleteId={athleteId} />
      </Card>
      <Card title="Historie výkonu">
        <History athleteId={athleteId} />
      </Card>
      <Card title="Stabilita výkonu">
        <PerformanceStability athleteId={athleteId} />
      </Card>
      <Card title="Vývoj výkonu za sezóny">
        <PerformanceByYear athleteId={athleteId} />
      </Card>
    </div>
  );
}
