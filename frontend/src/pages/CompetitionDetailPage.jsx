import { useParams, Link } from "react-router-dom";
import { useQueries } from "@tanstack/react-query";
import { useCompetitionDetail } from "../hooks/useApi";
import Card from "../components/Card";
import PageContextNav from "../components/PageContextNav";
import api from "../api/axios";
import formatCategoryName from "../utils/formatCategoryName";

const formatDate = (dateString) => {
  if (!dateString) return "-";

  const parsedDate = new Date(dateString);
  if (Number.isNaN(parsedDate.getTime())) return "-";

  return `${parsedDate.getDate()}. ${parsedDate.getMonth() + 1}. ${parsedDate.getFullYear()}`;
};

const formatSeason = (dateString) => {
  if (!dateString) return "-";

  const parsedDate = new Date(dateString);
  if (Number.isNaN(parsedDate.getTime())) return "-";

  return `${parsedDate.getFullYear()}`;
};

const formatBestTime = (results) => {
  const validTimes = results
    .filter((result) => result?.final_time_status === "valid")
    .map((result) => result?.final_time)
    .filter((time) => time != null);

  if (validTimes.length === 0) return "—";

  return `${Math.min(...validTimes).toFixed(2)} s`;
};

export default function CompetitionDetailPage() {
  const { id } = useParams();
  const { data, isLoading, error } = useCompetitionDetail(id);
  const { name, date, place, league, athlete_count, categories } = data ?? {};
  const formattedCategories =
    categories?.map((category) => ({
      id: category.id,
      name: formatCategoryName(category.name),
    })) ?? [];
  const formattedDate = formatDate(date);
  const competitionSummary =
    formattedDate !== "-" && place && league
      ? `Závod ${name || "bez názvu"} se konal ${formattedDate} v lokalitě ${place} a je zařazen do soutěže ${league}.`
      : `${name || "Tento závod"} zatím nemá dostupné doplňující informace.`;
  const competitionMeta = [formattedDate, place || null, league || null].filter(
    Boolean,
  );
  const competitionStats = [
    {
      label: "Počet závodníků",
      value: athlete_count ?? "—",
    },
    {
      label: "Počet kategorií",
      value: categories?.length ?? 0,
    },
    {
      label: "Liga",
      value: league || "—",
    },
    {
      label: "Rok",
      value: formatSeason(date),
    },
  ];
  const categoryResultsQueries = useQueries({
    queries: formattedCategories.map((category) => ({
      queryKey: ["results", id, category.id],
      queryFn: async () => {
        const { data: results } = await api.get(
          `/v1/competitions/${id}/results/${category.id}`,
        );
        return results;
      },
      enabled: !!id && !!category.id,
      staleTime: 60_000,
    })),
  });
  const categoryStatsById = new Map(
    formattedCategories.map((category, index) => {
      const categoryResults = categoryResultsQueries[index]?.data ?? [];
      const validResults = categoryResults.filter(
        (result) => result?.final_time_status === "valid",
      );

      return [
        category.id,
        {
          athleteCount: categoryResults.length,
          validResultsCount: validResults.length,
          bestTime: formatBestTime(categoryResults),
          isLoading: categoryResultsQueries[index]?.isLoading,
        },
      ];
    }),
  );

  if (isLoading)
    return <div className="competition-detail-page">Načítání...</div>;
  if (error || !data)
    return (
      <div className="competition-detail-page">Chyba při načítání dat.</div>
    );

  return (
    <div className="competition-detail-page page">
      <PageContextNav
        items={[
          { label: "Závody", to: "/zavody" },
          { label: name || "Detail závodu" },
        ]}
        action={{ label: "Zpět na seznam závodů", to: "/zavody" }}
      />

      <section className="competition-profile-hero">
        <div className="competition-profile-hero__intro">
          <p className="competition-profile-hero__eyebrow">Detail závodu</p>
          <h1 className="competition-profile-hero__name">{name || "-"}</h1>

          {competitionMeta.length > 0 && (
            <div
              className="competition-profile-hero__meta"
              aria-label="Základní údaje o závodu"
            >
              {competitionMeta.map((item) => (
                <span className="competition-profile-hero__badge" key={item}>
                  {item}
                </span>
              ))}
            </div>
          )}
        </div>

        <div
          className="competition-profile-hero__stats"
          aria-label="Přehled statistik závodu"
        >
          {competitionStats.map((stat) => (
            <div className="competition-profile-hero__stat" key={stat.label}>
              <span className="competition-profile-hero__stat-label">
                {stat.label}
              </span>
              <strong className="competition-profile-hero__stat-value">
                {stat.value}
              </strong>
            </div>
          ))}
        </div>
      </section>

      <section
        className="competition-overview-section"
        aria-labelledby="competition-overview-title"
      >
        <div className="competition-overview-section__header">
          <h2
            className="competition-overview-section__title"
            id="competition-overview-title"
          >
            Přehled závodu
          </h2>
          <p className="competition-overview-section__description">
            Základní souhrn závodu a přehled vypsaných kategorií.
          </p>
        </div>

        <Card title="Souhrn a kategorie" className="competition-overview-card">
          <div className="competition-overview-card__content">
            <p className="competition-overview-card__summary">
              {competitionSummary}
            </p>

            <div className="competition-overview-card__categories">
              <span className="competition-overview-card__categories-label">
                Kategorie závodu
              </span>

              {formattedCategories.length > 0 ? (
                <div
                  className="competition-overview-card__categories-list"
                  aria-label="Kategorie závodu"
                >
                  {formattedCategories.map((category) => (
                    <span
                      className="competition-overview-card__category-badge"
                      key={category.id}
                    >
                      {category.name}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="competition-overview-card__categories-empty">
                  Kategorie zatím nejsou k dispozici.
                </p>
              )}
            </div>
          </div>
        </Card>
      </section>

      <hr className="competition-detail-divider" />

      <h2>Výsledkové listiny</h2>
      <div className="competition-detail-results-grid">
        {categories && categories.length > 0 ? (
          categories.map((cat) => (
            <Link
              key={cat.id}
              to={`/zavody/${id}/vysledky/${encodeURIComponent(cat.id)}`}
              className="competition-detail-results-card-link"
            >
              <Card className="competition-detail-results-card-row">
                <div className="competition-detail-results-card-row__content">
                  <div className="competition-detail-results-card-row__main">
                    <strong className="competition-detail-results-card-row__title">
                      {formatCategoryName(cat.name)}
                    </strong>
                    <span className="competition-detail-results-card-row__subtitle">
                      Zobrazit výsledky kategorie
                    </span>
                  </div>

                  {categoryStatsById.get(cat.id) && (
                    <div className="competition-detail-results-card-row__stats">
                      <span className="competition-detail-results-card-row__stat">
                        Závodníků:{" "}
                        <strong>
                          {categoryStatsById.get(cat.id)?.isLoading
                            ? "…"
                            : (categoryStatsById.get(cat.id)?.athleteCount ??
                              "—")}
                        </strong>
                      </span>
                      <span className="competition-detail-results-card-row__stat">
                        Nejlepší čas:{" "}
                        <strong>
                          {categoryStatsById.get(cat.id)?.isLoading
                            ? "…"
                            : (categoryStatsById.get(cat.id)?.bestTime ?? "—")}
                        </strong>
                      </span>
                      <span className="competition-detail-results-card-row__stat">
                        Platných výsledků:{" "}
                        <strong>
                          {categoryStatsById.get(cat.id)?.isLoading
                            ? "…"
                            : (categoryStatsById.get(cat.id)
                                ?.validResultsCount ?? "—")}
                        </strong>
                      </span>
                    </div>
                  )}
                </div>

                <span
                  className="competition-detail-results-card-row__arrow"
                  aria-hidden="true"
                >
                  &#8250;
                </span>
              </Card>
            </Link>
          ))
        ) : (
          <div>Výsledky nejsou k dispozici.</div>
        )}
      </div>
    </div>
  );
}
