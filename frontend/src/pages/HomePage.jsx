import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useMe, useAthleteOverview } from "../hooks/useApi";
import Card from "../components/Card";
import PairAthleteDialog from "../components/home/PairAthleteDialog";
import RecentActivity from "../components/home/RecentActivity";
import Statistics from "../components/home/Statistics";
import CompareAthletes from "../components/home/CompareAthletes";
import MyData from "../components/home/MyData";
import WelcomePage from "./WelcomePage";
import PrimaryButton from "../components/PrimaryButton";

export default function HomePage() {
  const { isAuthenticated, loading } = useAuth();
  const { data: me, isLoading: meLoading, error: meError } = useMe();
  const {
    data: overview,
    isLoading: overviewLoading,
    error: overviewError,
  } = useAthleteOverview(me?.athlete_id);

  const [showPairDialog, setShowPairDialog] = useState(false);

  if (loading) {
    return null;
  }
  if (!isAuthenticated) {
    return <WelcomePage />;
  }

  if (meLoading) {
    return (
      <div className="home-page">
        <Card status="loading">
          <div className="skeleton" />
        </Card>
      </div>
    );
  }

  if (meError) {
    return (
      <div className="home-page">
        <Card status="error">
          <p>Nepodařilo se načíst data.</p>
          <button onClick={() => window.location.reload()}>Zkusit znovu</button>
        </Card>
      </div>
    );
  }

  // User není spárovaný s atletem
  if (!me.athlete_id) {
    return (
      <div className="home-page">
        <Card status="empty">
          <div className="pairathlete-card">
            <h1>Spoj účet s atletem</h1>
            <p>Pro zobrazení statistik najdi atleta v databázi.</p>
            <PrimaryButton onClick={() => setShowPairDialog(true)}>
              Najít atleta
            </PrimaryButton>
          </div>
        </Card>

        {showPairDialog && (
          <PairAthleteDialog onClose={() => setShowPairDialog(false)} />
        )}
      </div>
    );
  }

  // Loading overview
  if (overviewLoading) {
    return (
      <div className="home-page">
        <Card title="Poslední aktivita" status="loading">
          <div className="skeleton" />
        </Card>
        <Card title="Statistiky" status="loading">
          <div className="skeleton" />
        </Card>
      </div>
    );
  }

  // Error overview
  if (overviewError) {
    return (
      <div className="home-page">
        <Card status="error">
          <p>Nepodařilo se načíst přehled atleta.</p>
          <button onClick={() => window.location.reload()}>Zkusit znovu</button>
        </Card>
      </div>
    );
  }

  return (
    <div className="home-page">
      {/* 1) Poslední aktivita */}
      <Card title="Poslední aktivita" status="ready">
        <RecentActivity
          data={
            overview.last_activity
              ? {
                  name: overview.last_activity.competition_name,
                  team:
                    overview.last_activity.competition_place ||
                    overview.athlete_team,
                  time: `${overview.last_activity.final_time.toFixed(2)} s`,
                }
              : null
          }
        />
      </Card>

      {/* 2) Statistiky */}
      <Card title="Statistiky" status="ready">
        <Statistics
          data={{
            category: overview.category || "—",
            avgTime: overview.avg_time
              ? `${overview.avg_time.toFixed(2)} s`
              : "—",
            bestTime: overview.best_time
              ? `${overview.best_time.toFixed(2)} s`
              : "—",
          }}
        />
      </Card>

      {/* 3) Moje data */}
      <Card title="Moje data" status="ready">
        <MyData />
      </Card>

      {/* 4) Porovnat výkon */}
      <Card title="Porovnat výkon" status="ready">
        <CompareAthletes />
      </Card>
    </div>
  );
}
