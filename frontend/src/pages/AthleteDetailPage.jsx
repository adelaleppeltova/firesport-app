import { useState, useEffect, useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import { useAthleteDetail, useAthletePerCategoryStats } from "../hooks/useApi";
import AthleteDetailCategoryCard, {
  CategorySelect,
} from "../components/athlete/AthleteDetailCategoryCard";
import PageContextNav from "../components/PageContextNav";
import formatCategoryName from "../utils/formatCategoryName";

const formatDate = (dateString) => {
  if (!dateString) return "-";
  const date = new Date(dateString);
  return `${date.getDate()}. ${date.getMonth() + 1}. ${date.getFullYear()}`;
};

const formatResultTime = (result) =>
  (result.final_time ? `${result.final_time.toFixed(2)} s` : "") +
  (result.final_time_status === "valid" ? "" : " NP");

const getResultTimeParts = (result) => ({
  time: result.final_time ? `${result.final_time.toFixed(2)} s` : null,
  isInvalid: result.final_time_status !== "valid",
});

const formatSeason = (dateString) => {
  if (!dateString) return "-";
  const date = new Date(dateString);
  return Number.isNaN(date.getTime()) ? "-" : `${date.getFullYear()}`;
};

const getResultDateValue = (result) =>
  new Date(result?.competition?.date || 0).getTime();

const getResultKey = (result) =>
  result?._id ??
  [
    result?.competition?._id ?? "competition",
    result?.category?._id ?? "category",
    result?.team ?? "team",
    result?.competition?.date ?? "date",
    result?.final_time ?? "time",
    result?.final_time_status ?? "status",
  ].join(":");

const getResultLink = (result, athleteId) => {
  const competitionId = result?.competition?._id;
  const categoryId = result?.category?._id;

  if (!competitionId || !categoryId || !athleteId) {
    return null;
  }

  return `/zavody/${competitionId}/vysledky/${categoryId}#${athleteId}`;
};

export default function AthleteDetailPage() {
  const { id } = useParams();
  const { data, isLoading, error } = useAthleteDetail(id);
  const { data: perCategoryData } = useAthletePerCategoryStats(id);

  const [selectedCategoryId, setSelectedCategoryId] = useState("");

  const availableCategories = useMemo(() => {
    if (!perCategoryData?.categories) return [];
    return perCategoryData.categories;
  }, [perCategoryData]);

  useEffect(() => {
    if (
      selectedCategoryId &&
      availableCategories.length > 0 &&
      !availableCategories.find((c) => c.category_id === selectedCategoryId)
    ) {
      setSelectedCategoryId("");
    }
  }, [availableCategories, selectedCategoryId]);

  if (isLoading) return <div className="athlete-detail-page">Načítání...</div>;
  if (error || !data)
    return <div className="athlete-detail-page">Chyba při načítání dat.</div>;

  const { athlete, best_time, results } = data;
  const selectedCategory = selectedCategoryId
    ? (availableCategories.find((c) => c.category_id === selectedCategoryId) ??
      null)
    : null;
  const filteredResults = selectedCategoryId
    ? (results ?? []).filter(
        (result) => result.category?._id === selectedCategoryId,
      )
    : results ?? [];
  const summaryTitleLabel = selectedCategory?.category_name ?? "Všechny kategorie";
  const summaryTotalRaces = selectedCategory
    ? selectedCategory.total_races ?? null
    : filteredResults.length;
  const summaryBestTime = selectedCategory
    ? selectedCategory.best_time ?? null
    : best_time ?? null;
  const hasResults = filteredResults.length > 0;
  const athleteName = `${athlete.first_name} ${athlete.last_name}`;
  const athleteTeams = athlete.teams?.join(", ") || "-";
  const athleteMeta = [
    athlete.birth_year ? `Ročník ${athlete.birth_year}` : null,
    athleteTeams !== "-" ? athleteTeams : null,
    athlete.district ? `Okres ${athlete.district}` : null,
    athlete.fscode ? `FS Code: ${athlete.fscode}` : null,
  ].filter(Boolean);
  const lastResult = [...filteredResults].sort(
    (a, b) => getResultDateValue(b) - getResultDateValue(a),
  )[0];
  const validResults = filteredResults.filter(
    (result) =>
      result.final_time_status === "valid" && result.final_time != null,
  );
  const averageValidTime =
    validResults.length > 0
      ? validResults.reduce((sum, result) => sum + result.final_time, 0) /
        validResults.length
      : null;
  const invalidResultsCount = filteredResults.filter(
    (result) => result.final_time_status !== "valid",
  ).length;
  const lastCompetitionLabel = lastResult?.competition?.name
    ? `${lastResult.competition.name} • ${formatDate(lastResult.competition.date)}`
    : null;
  const profileStats = [
    {
      label: "Nejlepší čas",
      value: summaryBestTime != null ? `${summaryBestTime.toFixed(2)} s` : "—",
    },
    {
      label: "Počet výsledků",
      value: summaryTotalRaces != null ? `${summaryTotalRaces}` : "—",
    },
    {
      label: "Počet kategorií",
      value: `${availableCategories.length || 0}`,
    },
    {
      label: "Poslední sezóna",
      value: formatSeason(lastResult?.competition?.date),
    },
  ];

  return (
    <div className="athlete-detail-page page">
      <PageContextNav
        items={[
          { label: "Závodníci", to: "/zavodnici" },
          { label: athleteName },
        ]}
        action={{ label: "Zpět na seznam závodníků", to: "/zavodnici" }}
      />

      <section className="athlete-profile-hero">
        <div className="athlete-profile-hero__intro">
          <p className="athlete-profile-hero__eyebrow">Profil závodníka</p>
          <h1 className="athlete-profile-hero__name">{athleteName}</h1>

          {athleteMeta.length > 0 && (
            <div className="athlete-profile-hero__meta" aria-label="Základní údaje">
              {athleteMeta.map((item) => (
                <span className="athlete-profile-hero__badge" key={item}>
                  {item}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="athlete-profile-hero__stats" aria-label="Přehled statistik">
          {profileStats.map((stat) => (
            <div className="athlete-profile-hero__stat" key={stat.label}>
              <span className="athlete-profile-hero__stat-label">
                {stat.label}
              </span>
              <strong className="athlete-profile-hero__stat-value">
                {stat.value}
              </strong>
            </div>
          ))}
        </div>
      </section>

      <section className="athlete-category-section" aria-labelledby="athlete-category-section-title">
        <div className="athlete-category-section__header">
          <h2
            className="athlete-category-section__title"
            id="athlete-category-section-title"
          >
            Filtr a přehled kategorie
          </h2>
          <p className="athlete-category-section__description">
            Vybraná kategorie upravuje souhrn i seznam výsledků níže.
          </p>
        </div>

        {availableCategories.length > 0 && (
          <CategorySelect
            categories={availableCategories}
            value={selectedCategoryId}
            onChange={setSelectedCategoryId}
          />
        )}

        <AthleteDetailCategoryCard
          totalResults={summaryTotalRaces}
          bestTime={summaryBestTime}
          titleLabel={summaryTitleLabel}
          averageValidTime={averageValidTime}
          invalidResultsCount={invalidResultsCount}
          lastCompetition={lastCompetitionLabel}
        />
      </section>

      <hr className="athlete-detail-divider" />
      <h2>Výsledky</h2>
      <div className="athletes-table-wrapper athlete-detail-results-table-wrapper">
        <table className="athlete-detail-table">
          <colgroup>
            <col className="athlete-detail-table__col athlete-detail-table__col--date" />
            <col className="athlete-detail-table__col athlete-detail-table__col--competition" />
            <col className="athlete-detail-table__col athlete-detail-table__col--place" />
            <col className="athlete-detail-table__col athlete-detail-table__col--category" />
            <col className="athlete-detail-table__col athlete-detail-table__col--team" />
            <col className="athlete-detail-table__col athlete-detail-table__col--time" />
          </colgroup>
          <thead>
            <tr>
              <th className="athlete-detail-table__date-heading">Datum</th>
              <th>Závod</th>
              <th>Místo</th>
              <th>Kategorie</th>
              <th>Sbor</th>
              <th className="athlete-detail-table__time-heading">Výsledný čas</th>
            </tr>
          </thead>
          <tbody>
            {hasResults ? (
              filteredResults.map((r) => {
                const competitionName = r.competition?.name || "Neznámý závod";
                const competitionPlace = r.competition?.place || "-";
                const competitionDate = formatDate(r.competition?.date);
                const categoryName = formatCategoryName(r.category?.name) || "-";
                const resultLink = getResultLink(r, athlete?._id);
                const timeParts = getResultTimeParts(r);

                return (
                <tr
                  className="athlete-results-card-row"
                  key={getResultKey(r)}
                >
                  <td className="athlete-detail-table__date athlete-detail-table__date--muted">
                    {competitionDate}
                  </td>
                  <td className="athlete-detail-table__competition">
                    {resultLink ? (
                      <Link
                        className="athlete-results-card-row__link"
                        to={resultLink}
                        aria-label={`Otevřít výsledky závodu ${competitionName}`}
                      >
                        {competitionName}
                      </Link>
                    ) : (
                      <span className="athlete-results-card-row__link athlete-results-card-row__link--disabled">
                        {competitionName}
                      </span>
                    )}
                  </td>
                  <td className="athlete-detail-table__place">{competitionPlace}</td>
                  <td className="athlete-detail-table__category">
                    {categoryName}
                  </td>
                  <td className="athlete-detail-table__team">{r.team || "-"}</td>
                  <td className="athlete-detail-table__time">
                    <div className="athlete-detail-table__time-content">
                      <span className="athlete-detail-table__time-value">
                        {timeParts.time || "—"}
                      </span>
                      {timeParts.isInvalid && (
                        <span className="athlete-detail-table__status-badge">NP</span>
                      )}
                    </div>
                  </td>
                </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={6}>Žádné výsledky</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="athlete-results-mobile-list">
        {hasResults ? (
          filteredResults.map((r) => {
            const competitionName = r.competition?.name || "Neznámý závod";
            const competitionDate = formatDate(r.competition?.date);
            const competitionPlace = r.competition?.place || "-";
            const categoryName = formatCategoryName(r.category?.name) || "-";
            const resultLink = getResultLink(r, athlete?._id);

            return (
              <article className="athlete-results-mobile-card" key={getResultKey(r)}>
                {resultLink ? (
                  <Link
                    className="athlete-results-mobile-card__header"
                    to={resultLink}
                    aria-label={`Otevřít výsledky závodu ${competitionName}`}
                  >
                    <span className="athlete-results-mobile-card__date">
                      {competitionDate}
                    </span>
                    <h3 className="athlete-results-mobile-card__title">
                      {competitionName}
                    </h3>
                  </Link>
                ) : (
                  <div className="athlete-results-mobile-card__header athlete-results-mobile-card__header--static">
                    <span className="athlete-results-mobile-card__date">
                      {competitionDate}
                    </span>
                    <h3 className="athlete-results-mobile-card__title">
                      {competitionName}
                    </h3>
                  </div>
                )}

                <dl className="athlete-results-mobile-card__details">
                  <div className="athlete-results-mobile-card__detail">
                    <dt>Místo</dt>
                    <dd>{competitionPlace}</dd>
                  </div>
                  <div className="athlete-results-mobile-card__detail">
                    <dt>Kategorie</dt>
                    <dd>{categoryName}</dd>
                  </div>
                  <div className="athlete-results-mobile-card__detail">
                    <dt>Sbor</dt>
                    <dd>{r.team || "-"}</dd>
                  </div>
                  <div className="athlete-results-mobile-card__detail athlete-results-mobile-card__detail--time">
                    <dt>Čas</dt>
                    <dd>{formatResultTime(r) || "-"}</dd>
                  </div>
                </dl>
              </article>
            );
          })
        ) : (
          <div className="athlete-results-mobile-card athlete-results-mobile-card--empty">
            Žádné výsledky
          </div>
        )}
      </div>
    </div>
  );
}
