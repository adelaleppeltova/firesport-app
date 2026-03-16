import { useAthleteProfile } from "../../hooks/useApi";
import CardState from "./CardState";

export default function MyProfile({ athleteId }) {
  const { data: profile, isLoading, error } = useAthleteProfile(athleteId);

  if (isLoading) return <div className="skeleton skeleton--md" />;
  if (error) return <CardState type="error" />;
  if (!profile)
    return (
      <CardState type="no-data" text="Profil závodníka není k dispozici." />
    );

  return (
    <div className="my-profile">
      <div className="my-profile__header">
        <h3 className="my-profile__name">
          {profile.first_name} {profile.last_name}
          {profile.birth_year ? (
            <span className="my-profile__birth-year">
              {" "}
              ({profile.birth_year})
            </span>
          ) : null}
        </h3>
        <p className="my-profile__team">{profile.team}</p>
      </div>

      <div className="my-profile__stats">
        <div className="my-profile__stat">
          <span className="my-profile__stat-label">Nejlepší čas</span>
          <span className="my-profile__stat-value">
            {profile.best_time != null
              ? `${profile.best_time.toFixed(2)} s`
              : "—"}
          </span>
        </div>
        <div className="my-profile__stat">
          <span className="my-profile__stat-label">Celkem závodů</span>
          <span className="my-profile__stat-value">
            {profile.total_competitions ?? "—"}
          </span>
        </div>
      </div>
    </div>
  );
}
