import { useState, useEffect, useMemo } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  useAdminAthleteMergeCandidates,
  useAdminMergeAthletes,
  useAthleteDetail,
  useAthletePerCategoryStats,
} from "../hooks/useApi";
import AthleteDetailCategoryCard, {
  CategorySelect,
} from "../components/athlete/AthleteDetailCategoryCard";
import PageContextNav from "../components/PageContextNav";
import { useAuth } from "../context/AuthContext";
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

const formatIdentityList = (items = []) =>
  items.length > 0 ? items.join(", ") : "—";

export default function AthleteDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { data, isLoading, error } = useAthleteDetail(id);
  const { data: perCategoryData } = useAthletePerCategoryStats(id);
  const isAdmin = user?.role === "admin";

  const [selectedCategoryId, setSelectedCategoryId] = useState("");
  const [mergeSearch, setMergeSearch] = useState("");
  const [submittedMergeSearch, setSubmittedMergeSearch] = useState("");
  const [mergeMessage, setMergeMessage] = useState(null);
  const mergeMutation = useAdminMergeAthletes();

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

  useEffect(() => {
    if (!data?.athlete) return;
    const defaultSearch =
      `${data.athlete.first_name ?? ""} ${data.athlete.last_name ?? ""}`.trim();
    setMergeSearch(defaultSearch);
    setSubmittedMergeSearch(defaultSearch);
    setMergeMessage(null);
  }, [data?.athlete]);

  const mergeCandidatesQuery = useAdminAthleteMergeCandidates(
    isAdmin ? id : null,
    submittedMergeSearch,
  );

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
  const athleteMeta = [
    athlete.birth_year ? `Ročník ${athlete.birth_year}` : null,
    athlete.district ? `Okres ${athlete.district}` : null,
  ].filter(Boolean);
  const athleteTeams = athlete.teams ?? [];
  const athleteFsCodes = athlete.fs_codes ?? [];
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
  const mergeCandidates = mergeCandidatesQuery.data?.items ?? [];

  const handleMergeSearchSubmit = (event) => {
    event.preventDefault();
    setSubmittedMergeSearch(mergeSearch.trim());
    setMergeMessage(null);
  };

  const handleMerge = async (targetAthlete) => {
    if (!id || mergeMutation.isPending) return;

    const confirmed = window.confirm(
      `Opravdu chceš sloučit ${athleteName} do profilu ${targetAthlete.first_name} ${targetAthlete.last_name}? Výsledky budou převedeny na cílového závodníka.`,
    );
    if (!confirmed) return;

    try {
      await mergeMutation.mutateAsync({
        sourceAthleteId: id,
        targetAthleteId: targetAthlete.athlete_id,
      });
      setMergeMessage({
        type: "success",
        text: "Závodníci byli úspěšně sloučeni. Otevírám cílový profil.",
      });
      navigate(`/zavodnici/${targetAthlete.athlete_id}`, { replace: true });
    } catch (mergeError) {
      const detail = mergeError?.response?.data?.detail;
      setMergeMessage({
        type: "error",
        text:
          typeof detail === "string" && detail
            ? detail
            : "Sloučení se nepodařilo dokončit.",
      });
    }
  };

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

          <div className="athlete-profile-hero__identity">
            <div className="athlete-profile-hero__identity-group">
              <span className="athlete-profile-hero__identity-label">FS kódy</span>
              <div className="athlete-profile-hero__meta">
                {athleteFsCodes.length > 0 ? (
                  athleteFsCodes.map((code) => (
                    <span className="athlete-profile-hero__badge" key={code}>
                      {code}
                    </span>
                  ))
                ) : (
                  <span className="athlete-profile-hero__identity-empty">—</span>
                )}
              </div>
            </div>

            <div className="athlete-profile-hero__identity-group">
              <span className="athlete-profile-hero__identity-label">Sbory / týmy</span>
              <div className="athlete-profile-hero__meta">
                {athleteTeams.length > 0 ? (
                  athleteTeams.map((team) => (
                    <span className="athlete-profile-hero__badge" key={team}>
                      {team}
                    </span>
                  ))
                ) : (
                  <span className="athlete-profile-hero__identity-empty">—</span>
                )}
              </div>
            </div>
          </div>
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

      {isAdmin && (
        <section
          className="athlete-merge-card"
          aria-labelledby="athlete-merge-card-title"
        >
          <div className="athlete-merge-card__header">
            <h2 id="athlete-merge-card-title">Sloučení s existujícím závodníkem</h2>
            <p>
              Stejný závodník může být v datech veden pod více FS kódy nebo sbory.
              Tady můžeš najít kandidáty a ručně převést tento profil do
              existujícího canonical atleta.
            </p>
          </div>

          <form className="athlete-merge-card__search" onSubmit={handleMergeSearchSubmit}>
            <input
              type="text"
              value={mergeSearch}
              onChange={(event) => setMergeSearch(event.target.value)}
              placeholder="Vyhledat podle jména"
            />
            <button type="submit" disabled={mergeCandidatesQuery.isFetching}>
              {mergeCandidatesQuery.isFetching ? "Vyhledávám..." : "Vyhledat"}
            </button>
          </form>

          {mergeMessage ? (
            <p className={`athlete-merge-card__message athlete-merge-card__message--${mergeMessage.type}`}>
              {mergeMessage.text}
            </p>
          ) : null}

          {mergeCandidates.length > 0 ? (
            <div className="athlete-merge-card__list">
              {mergeCandidates.map((candidate) => {
                const candidateName = `${candidate.first_name} ${candidate.last_name}`;
                return (
                  <article className="athlete-merge-card__candidate" key={candidate.athlete_id}>
                    <div className="athlete-merge-card__candidate-main">
                      <h3>{candidateName}</h3>
                      <p>
                        {[
                          candidate.birth_year ? `Ročník ${candidate.birth_year}` : null,
                          `${candidate.result_count} výsledků`,
                        ]
                          .filter(Boolean)
                          .join(" • ")}
                      </p>
                      <p>FS kódy: {formatIdentityList(candidate.fs_codes)}</p>
                      <p>Sbory: {formatIdentityList(candidate.teams)}</p>
                    </div>

                    <button
                      type="button"
                      className="athlete-merge-card__merge-button"
                      onClick={() => handleMerge(candidate)}
                      disabled={mergeMutation.isPending}
                    >
                      Sloučit do tohoto závodníka
                    </button>
                  </article>
                );
              })}
            </div>
          ) : (
            <p className="athlete-merge-card__empty">
              {mergeCandidatesQuery.isFetching
                ? "Vyhledávám kandidáty..."
                : "Nebyl nalezen žádný vhodný kandidát."}
            </p>
          )}
        </section>
      )}
    </div>
  );
}
