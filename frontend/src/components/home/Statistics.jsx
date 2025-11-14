export default function Statistics({ data }) {
  if (!data) return <p>Načítání...</p>;

  return (
    <div className="statistics">
      <div className="statistics__header">
        <span className="statistics__icon">📊</span>
        <span className="statistics__category">Kategorie {data.category}</span>
      </div>
      <div className="statistics__row">
        <span>Průměrný čas</span>
        <strong>{data.avgTime}</strong>
      </div>
      <div className="statistics__row">
        <span>Nejlepší čas</span>
        <strong>{data.bestTime}</strong>
      </div>
    </div>
  );
}