export default function RecentActivity({ data }) {
  if (!data) return <p className="empty-state">Žádná aktivita</p>;

  return (
    <div className="recent-activity">
      <div className="recent-activity__athlete">
        <span className="recent-activity__icon">🏃</span>
        <div>
          <h3 className="recent-activity__name">{data.name}</h3>
          <p className="recent-activity__team">{data.team}</p>
        </div>
        <span className="recent-activity__time">{data.time}</span>
      </div>
    </div>
  );
}
