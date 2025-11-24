import Card from "../components/Card";
import MyProfile from "../components/home/MyProfile";

export default function HomePage() {
  return (
    <div className="home-page">
      <Card title="Můj profil">
        <MyProfile />
      </Card>
    </div>
  );
}
