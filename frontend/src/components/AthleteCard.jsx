function AthleteCard({ athlete }) {
  return (
    <div className="athlete-card">
      <h3>
        {athlete.first_name} {athlete.last_name}
      </h3>
      <p>Category: {athlete.category}</p>
      <p>Team: {athlete.team[0]?.name}</p>
    </div>
  );
}
export default AthleteCard;
