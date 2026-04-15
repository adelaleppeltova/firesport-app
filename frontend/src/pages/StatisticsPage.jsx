import { useState, useMemo, useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from "recharts";
import Card from "../components/Card";
import ModelInfoCard from "../components/statistics/ModelInfoCard";
import { CategoryGroupSelect } from "../components/athlete/CategorySummaryCard";
import {
  useAthleteAnomalies,
  useAthleteDetail,
  useAthletes,
  useAllAthleteAnomalyItems,
  useMlWindows,
} from "../hooks/useApi";

function InfoTooltip({ text }) {
  return (
    <span className="info-tooltip" tabIndex={0} aria-label={text}>
      <i
        className="fa-solid fa-circle-info info-tooltip__icon"
        aria-hidden="true"
      />
      <span className="info-tooltip__text" role="tooltip">
        {text}
      </span>
    </span>
  );
}

function formatTime(seconds) {
  if (seconds == null) return "—";
  const mins = Math.floor(seconds / 60);
  const secs = (seconds % 60).toFixed(2).padStart(5, "0");
  return mins > 0 ? `${mins}:${secs}` : `${secs} s`;
}

function formatDate(dateStr) {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  return d.toLocaleDateString("cs-CZ", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function formatMonthYear(dateStr) {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  return d.toLocaleDateString("cs-CZ", { month: "long", year: "numeric" });
}

function formatMonthYearShort(dateStr) {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  return d.toLocaleDateString("cs-CZ", {
    month: "2-digit",
    year: "numeric",
  });
}

function pluralizePerformances(count) {
  if (count === 1) return "neobvyklý výkon";
  if (count >= 2 && count <= 4) return "neobvyklé výkony";
  return "neobvyklých výkonů";
}

function formatAnomalySentence(nAnomalies, nValid, periodShort) {
  const verb =
    nAnomalies === 0
      ? "bylo označeno"
      : nAnomalies === 1
        ? "byl označen"
        : "byly označeny";
  return `V analyzovaném období ${periodShort} ${verb} ${nAnomalies} z ${nValid} validních výsledků.`;
}

function buildTimeTicks(minX, maxX, count) {
  if (!Number.isFinite(minX) || !Number.isFinite(maxX) || count <= 1) {
    return [];
  }
  if (minX === maxX) return [minX];

  const step = (maxX - minX) / (count - 1);
  return Array.from({ length: count }, (_, index) =>
    Math.round(minX + step * index),
  );
}

function formatChartTick(value, useMonthYear) {
  const date = new Date(value);
  return useMonthYear
    ? date.toLocaleDateString("cs-CZ", {
        month: "2-digit",
        year: "2-digit",
      })
    : date.toLocaleDateString("cs-CZ", {
        day: "2-digit",
        month: "2-digit",
        year: "2-digit",
      });
}

function formatDeviation(diff) {
  if (diff == null) return null;
  return diff >= 0
    ? `+${diff.toFixed(2)} s vůči mediánu`
    : `${diff.toFixed(2)} s vůči mediánu`;
}

function AnomalyTooltip({ active, payload }) {
  if (!active || !payload || payload.length === 0) return null;
  const p = payload[0].payload;

  return (
    <div className="anomaly-chart__tooltip">
      <div className="anomaly-chart__tooltip-date">{formatDate(p.rawDate)}</div>
      <div className="anomaly-chart__tooltip-time">
        <strong>{formatTime(p.y)}</strong>
      </div>
      {p.competition && (
        <div className="anomaly-chart__tooltip-competition">
          {p.competition}
        </div>
      )}
      {p.deviationLabel && (
        <div className="anomaly-chart__tooltip-deviation">
          {p.deviationLabel}
        </div>
      )}
      {p.isAnomaly && p.qualityFlag === "suspicious" && (
        <div className="anomaly-chart__tooltip-badge anomaly-chart__tooltip-badge--warning">
          Doporučeno ověřit záznam
        </div>
      )}
    </div>
  );
}

function formatWindowLabel(window_start, window_end) {
  const fmt = (dateStr) =>
    new Date(dateStr).toLocaleDateString("cs-CZ", {
      year: "numeric",
    });
  return `${fmt(window_start)} – ${fmt(window_end)}`;
}

function getWindowSortTimestamp(window) {
  return Math.max(
    Date.parse(window?.window_end ?? "") || 0,
    Date.parse(window?.window_start ?? "") || 0,
  );
}

function YearSelect({
  windows,
  value,
  onChange,
  isLoading,
  isError,
  helperText,
}) {
  if (isLoading) {
    return <div className="window-select__skeleton skeleton" />;
  }
  if (isError || !windows?.length) {
    return null;
  }
  const isDisabled = windows.length === 1;
  return (
    <div className="window-select">
      <label className="window-select__label" htmlFor="window-select">
        Období analýzy:
      </label>
      <select
        id="window-select"
        className="window-select__input"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
        disabled={isDisabled}
      >
        {windows.map((w) => (
          <option key={w.run_id} value={w.run_id}>
            {formatWindowLabel(w.window_start, w.window_end)}
          </option>
        ))}
      </select>
      {helperText ? (
        <p className="window-select__helper">{helperText}</p>
      ) : null}
    </div>
  );
}

function SummaryCard({ run }) {
  if (!run) {
    return (
      <Card title="Přehled detekce" className="anomaly-summary-card">
        <p className="empty-state">
          Pro vybraného závodníka zatím není v tomto období dostupný přehled
          detekce.
        </p>
      </Card>
    );
  }

  const period = `${formatMonthYear(run.window_start)} – ${formatMonthYear(run.window_end)}`;
  const nAnomalies = run.n_anomalies;
  const nValid = run.n_valid_results_in_window ?? 0;
  const nInvalid = run.n_invalid_results_in_window ?? 0;
  const nTotal = nValid + nInvalid;
  const anomalyShare =
    nValid > 0 ? Math.round((nAnomalies / nValid) * 100) : null;
  const periodShort = `${formatMonthYearShort(run.window_start)}–${formatMonthYearShort(run.window_end)}`;
  const summaryTitle = pluralizePerformances(nAnomalies);
  const summaryText = formatAnomalySentence(nAnomalies, nValid, periodShort);

  return (
    <Card title="Přehled detekce" className="anomaly-summary-card">
      <div className="anomaly-summary">
        <div className="anomaly-summary__hero">
          <div className="anomaly-summary__primary">
            <div className="anomaly-summary__count">{nAnomalies}</div>
            <div className="anomaly-summary__headline">{summaryTitle}</div>
            {anomalyShare != null && (
              <div className="anomaly-summary__ratio">
                {anomalyShare} % označených výsledků
              </div>
            )}
            <p className="anomaly-summary__lead">{summaryText}</p>
          </div>

          <div className="anomaly-summary__metrics">
            <div className="anomaly-summary__item anomaly-summary__item--compact">
              <span className="anomaly-summary__label">Období</span>
              <span className="anomaly-summary__value">{period}</span>
            </div>
            <div className="anomaly-summary__item anomaly-summary__item--compact">
              <span className="anomaly-summary__label">Validní výsledky</span>
              <span className="anomaly-summary__value">{nValid}</span>
            </div>
            <div className="anomaly-summary__item anomaly-summary__item--compact">
              <span className="anomaly-summary__label">Vyřazené výsledky</span>
              <span className="anomaly-summary__value">{nInvalid}</span>
            </div>
            <div className="anomaly-summary__item anomaly-summary__item--compact">
              <span className="anomaly-summary__label">Výsledky celkem</span>
              <span className="anomaly-summary__value">{nTotal}</span>
            </div>
            {run.median_time != null && (
              <div className="anomaly-summary__item anomaly-summary__item--compact">
                <span className="anomaly-summary__label">
                  Medián
                  <InfoTooltip text="Medián slouží jen jako orientační bod pro směr odchylky. Neovlivňuje detekci." />
                </span>
                <span className="anomaly-summary__value">
                  {formatTime(run.median_time)}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}

function InterpretationCard({ run, items }) {
  if (!run) return null;

  const anomalyItems = items.filter((item) => item.is_anomaly);
  const nAnomalies = anomalyItems.length;
  const suspiciousCount = anomalyItems.filter(
    (item) => item.quality_flag === "suspicious",
  ).length;

  let directionSentence = "Směr odchylky vůči mediánu nelze určit.";

  if (run.median_time != null && anomalyItems.length > 0) {
    const slowerCount = anomalyItems.filter(
      (item) => item.final_time > run.median_time,
    ).length;
    const fasterCount = anomalyItems.filter(
      (item) => item.final_time < run.median_time,
    ).length;

    if (slowerCount === anomalyItems.length) {
      directionSentence =
        nAnomalies === 1
          ? "Označený výkon byl pomalejší než referenční medián."
          : "Všechny označené výkony byly pomalejší než referenční medián.";
    } else if (fasterCount === anomalyItems.length) {
      directionSentence =
        nAnomalies === 1
          ? "Označený výkon byl rychlejší než referenční medián."
          : "Všechny označené výkony byly rychlejší než referenční medián.";
    } else {
      directionSentence =
        "Označené výkony zahrnují rychlejší i pomalejší odchylky vůči mediánu.";
    }
  }

  const recommendationSentence =
    suspiciousCount > 0
      ? "Záznam je vhodné ověřit v kontextu závodu."
      : "Výsledek je vhodné posoudit v kontextu závodu a sezony.";

  const overviewSentence =
    nAnomalies === 0
      ? "V tomto období nebyl označen žádný neobvyklý výkon."
      : nAnomalies === 1
        ? "V tomto období byl označen 1 neobvyklý výkon."
        : `V tomto období byly označeny ${nAnomalies} neobvyklé výkony.`;

  return (
    <Card title="Interpretace" className="anomaly-interpretation-card">
      <div className="anomaly-interpretation">
        <p>{overviewSentence}</p>
        <p>{directionSentence}</p>
        <p>{recommendationSentence}</p>
      </div>
    </Card>
  );
}

function ChartCard({ items, medianTime }) {
  const [isMobile, setIsMobile] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.innerWidth < 640;
  });

  useEffect(() => {
    if (typeof window === "undefined") return undefined;

    const handleResize = () => setIsMobile(window.innerWidth < 640);

    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const { filtered, xDomain, yDomain, xTicks, useMonthYearTicks } =
    useMemo(() => {
      const mapped = items.map((it) => ({
        x: new Date(it.competition_date).getTime(),
        y: it.final_time,
        rawDate: it.competition_date,
        isAnomaly: it.is_anomaly,
        qualityFlag: it.quality_flag ?? "ok",
        score: it.score,
        competition: it.competition_name || it.competition_place || null,
        deviationLabel: formatDeviation(
          medianTime != null ? it.final_time - medianTime : null,
        ),
      }));

      if (mapped.length === 0)
        return {
          filtered: mapped,
          xDomain: ["auto", "auto"],
          yDomain: ["auto", "auto"],
          xTicks: [],
          useMonthYearTicks: false,
        };

      const allX = mapped.map((d) => d.x);
      const allY = mapped.map((d) => d.y);
      const minX = Math.min(...allX);
      const maxX = Math.max(...allX);
      const minY = Math.min(...allY);
      const maxY = Math.max(...allY);
      const xPad = Math.max(24 * 60 * 60 * 1000, (maxX - minX) * 0.04);
      const yPad = Math.max(0.2, (maxY - minY) * 0.05);
      const tickCount = isMobile ? 4 : 6;
      const xTicks = buildTimeTicks(minX, maxX, tickCount);
      const useMonthYearTicks = maxX - minX > 366 * 24 * 60 * 60 * 1000;

      return {
        filtered: mapped,
        xDomain: [minX - xPad, maxX + xPad],
        yDomain: [
          parseFloat((minY - yPad).toFixed(1)),
          parseFloat((maxY + yPad).toFixed(1)),
        ],
        xTicks,
        useMonthYearTicks,
      };
    }, [isMobile, items, medianTime]);

  const normal = filtered.filter((d) => !d.isAnomaly);
  const anomalies = filtered.filter((d) => d.isAnomaly);

  return (
    <Card title="Výsledky v čase">
      {filtered.length === 0 ? (
        <p className="empty-state">
          V grafu nejsou pro toto období žádné výsledky.
        </p>
      ) : (
        <>
          <div className="anomaly-chart__header">
            <div className="anomaly-chart__legend anomaly-chart__legend--header">
              <span className="anomaly-chart__legend-item">
                <svg width="10" height="10">
                  <circle cx="5" cy="5" r="5" fill="#cf362e" />
                </svg>
                Neobvyklý výkon
              </span>
              <span className="anomaly-chart__legend-item">
                <svg width="10" height="10">
                  <circle cx="5" cy="5" r="5" fill="#0f4d92" />
                </svg>
                Běžný výkon
              </span>
              {medianTime != null && (
                <span className="anomaly-chart__legend-item">
                  <svg width="18" height="10">
                    <line
                      x1="0"
                      y1="5"
                      x2="18"
                      y2="5"
                      stroke="#f5a623"
                      strokeWidth="2"
                      strokeDasharray="5 2"
                    />
                  </svg>
                  Medián
                </span>
              )}
            </div>
          </div>
          <div className="anomaly-chart__canvas">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart
                margin={{ top: 10, right: 20, bottom: 34, left: 12 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
                <XAxis
                  dataKey="x"
                  type="number"
                  scale="time"
                  domain={xDomain}
                  ticks={xTicks}
                  tickFormatter={(value) =>
                    formatChartTick(value, useMonthYearTicks)
                  }
                  stroke="#636363"
                  tick={{
                    fontSize: isMobile ? 10 : 11,
                    angle: 0,
                    textAnchor: "middle",
                  }}
                  height={42}
                  label={{
                    value: "Datum",
                    position: "bottom",
                    offset: 8,
                    fontSize: 13,
                  }}
                />
                <YAxis
                  dataKey="y"
                  type="number"
                  domain={yDomain}
                  tickFormatter={(v) => `${v.toFixed(1)} s`}
                  stroke="#636363"
                  tick={{ fontSize: 10 }}
                  width={58}
                  label={{
                    value: "Čas (s)",
                    angle: -90,
                    position: "left",
                    offset: 0,
                    fontSize: 13,
                  }}
                />
                <Tooltip
                  content={<AnomalyTooltip />}
                  isAnimationActive={false}
                />
                {medianTime != null && (
                  <ReferenceLine
                    y={medianTime}
                    stroke="#f5a623"
                    strokeWidth={2}
                    strokeDasharray="6 3"
                  />
                )}
                <Scatter
                  name="normal"
                  data={normal}
                  fill="#0f4d92"
                  opacity={0.85}
                  r={5}
                />
                <Scatter
                  name="anomaly"
                  data={anomalies}
                  fill="#cf362e"
                  opacity={0.9}
                  r={6}
                />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
          <p className="anomaly-chart__note">
            Referenční medián slouží pouze k orientačnímu porovnání směru
            odchylky. Neovlivňuje samotné označení neobvyklého výkonu.
          </p>
        </>
      )}
    </Card>
  );
}

function TableCard({ items, medianTime }) {
  const anomalyItems = useMemo(
    () =>
      items
        .filter((it) => it.is_anomaly)
        .sort(
          (a, b) => new Date(b.competition_date) - new Date(a.competition_date),
        ),
    [items],
  );

  const getDeviationLabel = (item) => {
    const diff = medianTime != null ? item.final_time - medianTime : null;
    if (diff == null) return "—";
    return diff >= 0
      ? `+${diff.toFixed(2)} s (pomalejší)`
      : `${diff.toFixed(2)} s (rychlejší)`;
  };

  const getCompetitionLabel = (item) =>
    item.competition_name || item.competition_place || "—";

  return (
    <Card title="Seznam označených výkonů">
      {anomalyItems.length === 0 ? (
        <p className="empty-state">Nebyl nalezen žádný označený výkon.</p>
      ) : (
        <>
          <div className="anomaly-table-mobile">
            {anomalyItems.map((it) => {
              const deviation = getDeviationLabel(it);
              return (
                <article className="anomaly-result-card" key={it.result_id}>
                  <div className="anomaly-result-card__date">
                    {formatDate(it.competition_date)}
                  </div>
                  <div className="anomaly-result-card__row">
                    <span className="anomaly-result-card__label">Čas</span>
                    <span className="anomaly-result-card__value">
                      {formatTime(it.final_time)}
                    </span>
                  </div>
                  <div className="anomaly-result-card__row">
                    <span className="anomaly-result-card__label">Závod</span>
                    <span className="anomaly-result-card__value">
                      {getCompetitionLabel(it)}
                    </span>
                  </div>
                  <div className="anomaly-result-card__row">
                    <span className="anomaly-result-card__label">Odchylka</span>
                    <span className="anomaly-result-card__value">
                      {deviation}
                    </span>
                  </div>
                  {it.quality_flag === "suspicious" && (
                    <div className="anomaly-result-card__footer">
                      <span className="anomaly-table__badge anomaly-table__badge--warning">
                        Doporučeno ověřit
                        <InfoTooltip text="Záznam je mimo běžné hranice kategorie nebo výrazně vybočuje z historie sportovce." />
                      </span>
                    </div>
                  )}
                </article>
              );
            })}
          </div>

          <div className="anomaly-table-wrapper">
            <table className="anomaly-table">
              <thead>
                <tr>
                  <th>Datum</th>
                  <th>Čas (s)</th>
                  <th>Závod</th>
                  <th>
                    Rozdíl vůči mediánu
                    <InfoTooltip text="Rozdíl času vůči mediánu v daném období. Slouží jen k určení směru odchylky." />
                  </th>
                </tr>
              </thead>
              <tbody>
                {anomalyItems.map((it) => {
                  const deviation = getDeviationLabel(it);
                  return (
                    <tr key={it.result_id}>
                      <td>{formatDate(it.competition_date)}</td>
                      <td>{formatTime(it.final_time)}</td>
                      <td>{getCompetitionLabel(it)}</td>
                      <td>
                        <div className="anomaly-table__deviation">
                          <span>{deviation}</span>
                          {it.quality_flag === "suspicious" && (
                            <span className="anomaly-table__badge anomaly-table__badge--warning">
                              Doporučeno ověřit
                              <InfoTooltip text="Záznam je mimo běžné hranice kategorie nebo výrazně vybočuje z historie sportovce." />
                            </span>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Card>
  );
}

function AthleteSearchCard({
  search,
  onSearchChange,
  selectedAthlete,
  selectedAthleteId,
  searchResults,
  isSearching,
  onSelectAthlete,
}) {
  const selectedAthleteTeams = selectedAthlete?.teams?.join(", ") || "—";

  return (
    <Card title="Vyhledání závodníka">
      <div className="statistics-athlete-search">
        <p className="statistics-athlete-search__desc">
          Vyberte závodníka pro zobrazení analýzy.
        </p>

        <div className="statistics-athlete-search__bar-wrapper">
          <div className="statistics-athlete-search__bar-iconwrap">
            <input
              id="statistics-athlete-search"
              name="statisticsAthleteSearch"
              className="statistics-athlete-search__bar"
              type="text"
              placeholder="Hledat jméno, rok nebo sbor..."
              value={search}
              onChange={(e) => onSearchChange(e.target.value)}
            />
            <i className="fa-solid fa-magnifying-glass statistics-athlete-search__icon" />
          </div>
        </div>

        {search.trim() && (
          <div
            className={`statistics-athlete-search__results${
              isSearching ? " statistics-athlete-search__results--fetching" : ""
            }`}
            aria-busy={isSearching}
          >
            {searchResults.length ? (
              <ul className="statistics-athlete-search__list">
                {searchResults.map((athlete) => (
                  <li key={athlete._id}>
                    <button
                      type="button"
                      className="statistics-athlete-search__item"
                      onClick={() => onSelectAthlete(athlete._id)}
                    >
                      <span className="statistics-athlete-search__name">
                        {athlete.first_name} {athlete.last_name}
                      </span>
                      <span className="statistics-athlete-search__detail">
                        {athlete.birth_year ?? "—"} •{" "}
                        {athlete.teams.join(", ") || "—"}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : isSearching ? (
              <p className="statistics-athlete-search__meta">Vyhledávám...</p>
            ) : (
              <p className="statistics-athlete-search__meta">
                Analýza pro toto období není k dispozici. Důvodem může být
                nedostatek validních výsledků.
              </p>
            )}
            {isSearching && searchResults.length > 0 && (
              <p className="statistics-athlete-search__meta statistics-athlete-search__meta--loading">
                Vyhledávám...
              </p>
            )}
          </div>
        )}

        {selectedAthleteId && (
          <div className="statistics-athlete-search__selected-card">
            <div className="statistics-athlete-search__selected-main">
              <span className="statistics-athlete-search__selected-label">
                Vybraný závodník
              </span>
              <strong className="statistics-athlete-search__selected-name">
                {selectedAthlete
                  ? `${selectedAthlete.first_name} ${selectedAthlete.last_name}`
                  : "Načítání..."}
              </strong>
              <span className="statistics-athlete-search__selected-meta">
                {selectedAthlete
                  ? `${selectedAthlete.birth_year ?? "—"} • ${selectedAthleteTeams}`
                  : "Načítám detail závodníka..."}
              </span>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

export default function StatisticsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedAthleteId = searchParams.get("athlete_id") || null;
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const debounceRef = useRef(null);

  const {
    data: windows,
    isLoading: windowsLoading,
    isError: windowsError,
  } = useMlWindows("yearly_3y", selectedAthleteId);

  const sortedWindows = useMemo(
    () =>
      [...(windows ?? [])].sort(
        (a, b) => getWindowSortTimestamp(b) - getWindowSortTimestamp(a),
      ),
    [windows],
  );

  const { runIdsByCategory } = useAllAthleteAnomalyItems(
    selectedAthleteId,
    sortedWindows,
  );

  const availableCategoryGroups = useMemo(() => {
    const latestWindowByRunId = new Map(
      sortedWindows.map((window) => [
        window.run_id,
        getWindowSortTimestamp(window),
      ]),
    );

    return [...runIdsByCategory.keys()].sort((a, b) => {
      const latestA = Math.max(
        ...[...(runIdsByCategory.get(a) ?? new Set())].map(
          (runId) => latestWindowByRunId.get(runId) ?? 0,
        ),
      );
      const latestB = Math.max(
        ...[...(runIdsByCategory.get(b) ?? new Set())].map(
          (runId) => latestWindowByRunId.get(runId) ?? 0,
        ),
      );

      if (latestA !== latestB) return latestB - latestA;
      return a.localeCompare(b, "cs");
    });
  }, [runIdsByCategory, sortedWindows]);

  const latestWindow = sortedWindows[0] ?? null;
  const latestWindowCategoryGroup = useMemo(() => {
    if (!latestWindow) return null;

    return (
      availableCategoryGroups.find((group) =>
        (runIdsByCategory.get(group) ?? new Set()).has(latestWindow.run_id),
      ) ?? null
    );
  }, [availableCategoryGroups, latestWindow, runIdsByCategory]);

  const [selectedCategoryGroup, setSelectedCategoryGroup] = useState(null);
  const [categoryWasAutoSelected, setCategoryWasAutoSelected] = useState(false);
  const prevAthleteRef = useRef(selectedAthleteId);
  useEffect(() => {
    if (prevAthleteRef.current !== selectedAthleteId) {
      setSelectedCategoryGroup(null);
      setCategoryWasAutoSelected(false);
      prevAthleteRef.current = selectedAthleteId;
    }
  }, [selectedAthleteId]);

  useEffect(() => {
    if (
      availableCategoryGroups.length > 0 &&
      !availableCategoryGroups.includes(selectedCategoryGroup)
    ) {
      setSelectedCategoryGroup(
        latestWindowCategoryGroup ?? availableCategoryGroups[0],
      );
      setCategoryWasAutoSelected(true);
    }
  }, [
    availableCategoryGroups,
    latestWindowCategoryGroup,
    selectedCategoryGroup,
  ]);

  const windowsForCategory = useMemo(() => {
    if (!selectedCategoryGroup) return sortedWindows;
    const runIds = runIdsByCategory.get(selectedCategoryGroup) ?? new Set();
    return sortedWindows.filter((w) => runIds.has(w.run_id));
  }, [sortedWindows, selectedCategoryGroup, runIdsByCategory]);

  const [selectedRunId, setSelectedRunId] = useState(null);
  const [runWasAutoSelected, setRunWasAutoSelected] = useState(false);
  useEffect(() => {
    if (windowsForCategory.length === 0) return;
    const stillValid = windowsForCategory.some(
      (w) => w.run_id === selectedRunId,
    );
    if (!stillValid) {
      setSelectedRunId(windowsForCategory[0].run_id);
      setRunWasAutoSelected(true);
    }
  }, [windowsForCategory, selectedRunId]);

  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(search.trim());
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [search]);

  const { data: athletesData, isFetching: isAthletesFetching } = useAthletes({
    search: debouncedSearch,
    page: 1,
    pageSize: 10,
    anomalyStatus: "processed",
  });

  const { data: selectedAthleteDetail } = useAthleteDetail(selectedAthleteId);

  const handleSelectAthlete = (athleteId) => {
    const next = new URLSearchParams(searchParams);
    next.set("athlete_id", athleteId);
    setSearchParams(next, { replace: true });
    setSearch("");
    setDebouncedSearch("");
    setSelectedRunId(null);
    setRunWasAutoSelected(false);
    setCategoryWasAutoSelected(false);
  };

  const { data, isLoading, isError } = useAthleteAnomalies(
    selectedAthleteId,
    selectedRunId,
  );

  const run = data?.run ?? null;
  const allItems = useMemo(() => data?.items ?? [], [data]);

  const items = useMemo(() => {
    if (!selectedCategoryGroup) return allItems;
    return allItems.filter((it) => it.category_group === selectedCategoryGroup);
  }, [allItems, selectedCategoryGroup]);

  const categoriesLoading =
    windowsLoading ||
    (!!selectedAthleteId &&
      !windowsError &&
      !!windows?.length &&
      availableCategoryGroups.length === 0);

  const searchResults = athletesData?.items ?? [];
  const categoryHelperText =
    categoryWasAutoSelected && availableCategoryGroups.length > 1
      ? "Automaticky vybrána poslední kategorie s analýzou."
      : null;
  const runHelperText =
    runWasAutoSelected && windowsForCategory.length > 1
      ? "Automaticky vybráno poslední dostupné období."
      : null;

  return (
    <div className="statistics-page page">
      <div className="statistics-page__header">
        <h1 className="statistics-page__title">Detekce neobvyklých výkonů</h1>
        <p className="statistics-page__desc">
          Analýza výkonů pomocí metody Isolation Forest v rámci vybraného období
          a kategorie.
        </p>
      </div>

      <AthleteSearchCard
        search={search}
        onSearchChange={setSearch}
        selectedAthlete={selectedAthleteDetail?.athlete}
        selectedAthleteId={selectedAthleteId}
        searchResults={searchResults}
        isSearching={isAthletesFetching}
        onSelectAthlete={handleSelectAthlete}
      />

      {/* Select kategorie + Select období – jeden wrapper pro responzivní layout */}
      {selectedAthleteId && (
        <div className="statistics-page__filters">
          {categoriesLoading ? (
            <div className="window-select__skeleton skeleton" />
          ) : availableCategoryGroups.length > 0 ? (
            <CategoryGroupSelect
              groups={availableCategoryGroups}
              value={selectedCategoryGroup}
              onChange={(value) => {
                setSelectedCategoryGroup(value);
                setCategoryWasAutoSelected(false);
              }}
              helperText={categoryHelperText}
            />
          ) : null}

          {selectedCategoryGroup && (
            <YearSelect
              windows={windowsForCategory}
              value={selectedRunId}
              onChange={(value) => {
                setSelectedRunId(value);
                setRunWasAutoSelected(false);
              }}
              isLoading={windowsLoading}
              isError={windowsError}
              helperText={runHelperText}
            />
          )}
        </div>
      )}

      {!selectedAthleteId ? (
        <div className="anomaly-no-athlete">
          <i className="fa-solid fa-user-magnifying-glass" />
          <p>Vyberte závodníka pro zobrazení analýzy.</p>
        </div>
      ) : windowsLoading ? (
        <>
          <div className="skeleton" style={{ height: 120, marginBottom: 16 }} />
          <div className="skeleton" style={{ height: 300, marginBottom: 16 }} />
          <div className="skeleton" style={{ height: 200 }} />
        </>
      ) : !windowsError && windows?.length === 0 ? (
        <div className="anomaly-no-athlete">
          <i className="fa-solid fa-chart-line" />
          <p>
            Analýza pro toto období není k dispozici. Důvodem může být
            nedostatek validních výsledků.
          </p>
        </div>
      ) : !selectedCategoryGroup || !selectedRunId ? (
        <>
          <div className="skeleton" style={{ height: 120, marginBottom: 16 }} />
          <div className="skeleton" style={{ height: 300, marginBottom: 16 }} />
          <div className="skeleton" style={{ height: 200 }} />
        </>
      ) : isLoading ? (
        <>
          <div className="skeleton" style={{ height: 120, marginBottom: 16 }} />
          <div className="skeleton" style={{ height: 300, marginBottom: 16 }} />
          <div className="skeleton" style={{ height: 200 }} />
        </>
      ) : isError ? (
        <p className="empty-state">
          Nepodařilo se načíst data. Zkuste to prosím znovu.
        </p>
      ) : (
        <>
          <SummaryCard run={run} />
          <InterpretationCard run={run} items={items} />
          <ChartCard items={items} medianTime={run?.median_time ?? null} />
          <TableCard items={items} medianTime={run?.median_time ?? null} />
          <ModelInfoCard
            run={run}
            athlete={selectedAthleteDetail?.athlete}
            categoryGroup={selectedCategoryGroup}
          />
        </>
      )}
    </div>
  );
}
