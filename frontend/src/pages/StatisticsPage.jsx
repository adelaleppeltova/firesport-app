import React from "react";

const stats = [
  {
    icon: "fa-solid fa-triangle-exclamation",
    title: "Detekce neobvyklých výkonů",
    desc: "Isolation Forest, Local Outlier Factor",
  },
  {
    icon: "fa-solid fa-chart-line",
    title: "Predikce výsledného času (podle ročníku, sboru, soutěže)",
    desc: "Lineární regrese, Random Forest, XGBoost",
  },
  {
    icon: "fa-regular fa-folder",
    title: "Klasifikace",
    desc: "Logistická regrese, SVM",
  },
  {
    icon: "fa-solid fa-diagram-project",
    title: "Hledání podobných typů závodníků",
    desc: "Clustering (shlukování) — K-Means, DBSCAN, PCA pro vizualizaci",
  },
  {
    icon: "fa-regular fa-clock",
    title: "Výkon v čase",
    desc: "Time series — ARIMA, Prophet, LSTM",
  },
];

export default function StatisticsPage() {
  return (
    <div className="statistics-page">
      <h1>Statistiky</h1>
      <div className="statistics-list">
        {stats.map((stat, idx) => (
          <div className="statistics-card" key={idx}>
            <div className="statistics-card-icon">
              <i className={stat.icon} />
            </div>
            <div className="statistics-card-content">
              <div className="statistics-card-title">{stat.title}</div>
              <div className="statistics-card-desc">{stat.desc}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
