import Card from "../components/Card";
import MyProfile from "../components/home/MyProfile";
import Season from "../components/home/Season";

export default function HomePage() {
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
