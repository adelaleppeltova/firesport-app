import Card from "../components/Card";
import MyProfile from "../components/home/MyProfile";
import Season from "../components/home/Season";
import PairAthleteCard from "../components/home/PairAthleteCard";
import { useMe } from "../hooks/useApi";

export default function HomePage() {
  const { data: user, isLoading } = useMe();

  if (isLoading) {
    return <div className="home-page">Načítání...</div>;
  }

  const isPaired = user?.athlete_id;

  if (!isPaired) {
    return (
      <div className="home-page">
        <PairAthleteCard />
      </div>
    );
  }

  return (
    <div className="home-page">
      <Card title="Můj profil">
        <MyProfile />
      </Card>
      <Card title="Aktuální sezóna">
        <Season />
      </Card>
    </div>
  );
}
