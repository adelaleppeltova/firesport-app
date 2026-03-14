import { useAthleteProfile } from "../../hooks/useApi";

export default function MyProfile({ athleteId }) {
  const { data: profile, isLoading, error } = useAthleteProfile(athleteId);

  if (isLoading) return <div className="skeleton" />;
  if (error) return <p className="empty-state">Chyba načítání</p>;
  if (!profile) return <p className="empty-state">Žádná data o profilu</p>;

  return (
    <div className="my-profile">
      <div className="my-profile__athlete">
        <div>
          <h3 className="my-profile__name">
            {profile.first_name} {profile.last_name} ({profile.birth_year})
          </h3>
          <p className="my-profile__team">{profile.team}</p>
        </div>
        <p className="my-profile__time">
          Nejlepší čas: {profile.best_time?.toFixed(2)} s
        </p>
        <p className="my-profile__competitions">
          Celkový počet závodů: {profile.total_competitions}
        </p>
      </div>
    </div>
  );
}
