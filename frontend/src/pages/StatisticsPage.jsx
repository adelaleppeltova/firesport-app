import React, { useState, useMemo, useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
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

// --- helpers ---

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

// Custom tooltip for scatter chart
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
      {p.isAnomaly && p.qualityFlag === "suspicious" && (
        <div className="anomaly-chart__tooltip-badge anomaly-chart__tooltip-badge--warning">
          Doporučeno ověřit záznam
        </div>
      )}
    </div>
  );
}

// --- year selector ---

function formatWindowLabel(window_start, window_end) {
  const fmt = (dateStr) =>
    new Date(dateStr).toLocaleDateString("cs-CZ", {
      year: "numeric",
    });
  return `${fmt(window_start)} – ${fmt(window_end)}`;
}

function YearSelect({ windows, value, onChange, isLoading, isError }) {
  if (isLoading) {
    return <div className="window-select__skeleton skeleton" />;
  }
  if (isError || !windows?.length) {
    return null; // no windows yet – silently hidden
  }
  const isDisabled = windows.length === 1;
  return (
    <div className="window-select">
      <label className="window-select__label" htmlFor="window-select">
        Okno analýzy:
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
    </div>
  );
}

// --- summary card ---

function SummaryCard({ run }) {
  if (!run) {
    return (
      <Card title="Přehled detekce">
        <p className="empty-state">
          Pro tohoto závodníka zatím nebyla provedena analýza neobvyklých výkonů
          v zadané kategorii a období.
        </p>
      </Card>
    );
  }

  const period = `${formatMonthYear(run.window_start)} – ${formatMonthYear(run.window_end)}`;
  const nAnomalies = run.n_anomalies;

  return (
    <Card title="Přehled detekce">
      <div className="anomaly-summary">
        <div className="anomaly-summary__item">
          <span className="anomaly-summary__label">
            Označeno jako neobvyklé
          </span>
          <span className="anomaly-summary__value anomaly-summary__value--highlight">
            {nAnomalies}
          </span>
        </div>
        <div className="anomaly-summary__item">
          <span className="anomaly-summary__label">Období</span>
          <span className="anomaly-summary__value">{period}</span>
        </div>
        <div className="anomaly-summary__item">
          <span className="anomaly-summary__label">Výsledky celkem</span>
          <span className="anomaly-summary__value">
            {run.n_valid_results_in_window +
              (run.n_invalid_results_in_window ?? 0)}
          </span>
        </div>
        <div className="anomaly-summary__item">
          <span className="anomaly-summary__label">Validní výsledky</span>
          <span className="anomaly-summary__value">
            {run.n_valid_results_in_window}
          </span>
        </div>
        <div className="anomaly-summary__item">
          <span className="anomaly-summary__label">Vyřazené výsledky</span>
          <span className="anomaly-summary__value">
            {run.n_invalid_results_in_window ?? 0}
          </span>
        </div>
        {run.median_time != null && (
          <div className="anomaly-summary__item">
            <span className="anomaly-summary__label">
              Referenční medián{" "}
              <InfoTooltip text="Medián slouží pouze jako referenční bod pro určení směru (rychlejší/pomalejší). Neovlivňuje detekci." />
            </span>
            <span className="anomaly-summary__value">
              {formatTime(run.median_time)}
            </span>
          </div>
        )}
      </div>
    </Card>
  );
}

// --- chart card ---

function ChartCard({ items, medianTime }) {
  const { filtered, xDomain, yDomain, xTicks } = useMemo(() => {
    const mapped = items.map((it) => ({
      x: new Date(it.competition_date).getTime(),
      y: it.final_time,
      rawDate: it.competition_date,
      isAnomaly: it.is_anomaly,
      qualityFlag: it.quality_flag ?? "ok",
      score: it.score,
      competition: it.competition_place || null,
    }));

    if (mapped.length === 0)
      return {
        filtered: mapped,
        xDomain: ["auto", "auto"],
        yDomain: ["auto", "auto"],
        xTicks: [],
      };

    const allX = mapped.map((d) => d.x);
    const allY = mapped.map((d) => d.y);
    const minX = Math.min(...allX);
    const maxX = Math.max(...allX);
    const minY = Math.min(...allY);
    const maxY = Math.max(...allY);
    const xPad = Math.max(24 * 60 * 60 * 1000, (maxX - minX) * 0.04); // min 1 den
    const yPad = Math.max(0.2, (maxY - minY) * 0.05);

    const xTicks = [...new Set(allX)].sort((a, b) => a - b);

    return {
      filtered: mapped,
      xDomain: [minX - xPad, maxX + xPad],
      yDomain: [
        parseFloat((minY - yPad).toFixed(1)),
        parseFloat((maxY + yPad).toFixed(1)),
      ],
      xTicks,
    };
  }, [items]);

  const normal = filtered.filter((d) => !d.isAnomaly);
  const anomalies = filtered.filter((d) => d.isAnomaly);

  const tickFormatter = (val) => {
    const d = new Date(val);
    return `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}.${d.getFullYear()}`;
  };

  return (
    <Card title="Výsledky v čase">
      {filtered.length === 0 ? (
        <p className="empty-state">Žádná data pro vybrané okno analýzy.</p>
      ) : (
        <ResponsiveContainer width="100%" height={320}>
          <ScatterChart margin={{ top: 10, right: 16, bottom: 50, left: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
            <XAxis
              dataKey="x"
              type="number"
              scale="time"
              domain={xDomain}
              ticks={xTicks}
              tickFormatter={tickFormatter}
              tick={{ fontSize: 10, angle: -30, textAnchor: "end" }}
              tickLine={false}
              height={50}
              label={{
                value: "Datum",
                position: "insideBottom",
                offset: -5,
                fontSize: 13,
              }}
            />
            <YAxis
              dataKey="y"
              type="number"
              domain={yDomain}
              tickFormatter={(v) => `${v.toFixed(1)} s`}
              tick={{ fontSize: 10 }}
              tickLine={false}
              width={50}
              label={{
                value: "Čas (s)",
                angle: -90,
                position: "insideLeft",
                offset: 4,
                fontSize: 13,
              }}
            />
            <Tooltip content={<AnomalyTooltip />} isAnimationActive={false} />
            <Legend
              wrapperStyle={{ bottom: -10 }}
              content={() => (
                <div
                  style={{
                    display: "flex",
                    justifyContent: "center",
                    flexWrap: "wrap",
                    gap: "6px 16px",
                    fontSize: 13,
                  }}
                >
                  <span
                    style={{ display: "flex", alignItems: "center", gap: 6 }}
                  >
                    <svg width="10" height="10">
                      <circle cx="5" cy="5" r="5" fill="#cf362e" />
                    </svg>
                    Označeno jako neobvyklé
                  </span>
                  <span
                    style={{ display: "flex", alignItems: "center", gap: 6 }}
                  >
                    <svg width="10" height="10">
                      <circle cx="5" cy="5" r="5" fill="#0f4d92" />
                    </svg>
                    Normální výkon
                  </span>
                  {medianTime != null && (
                    <span
                      style={{ display: "flex", alignItems: "center", gap: 6 }}
                    >
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
                      Referenční medián
                    </span>
                  )}
                </div>
              )}
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
      )}
    </Card>
  );
}

// --- table card ---

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

  return (
    <Card title="Seznam označených výkonů">
      {anomalyItems.length === 0 ? (
        <p className="empty-state">Žádné označené výkony nebyly nalezeny.</p>
      ) : (
        <div className="anomaly-table-wrapper">
          <table className="anomaly-table">
            <thead>
              <tr>
                <th>Datum</th>
                <th>Čas (s)</th>
                <th>Závod</th>
                <th>
                  Rozdíl vůči mediánu
                  <InfoTooltip text="Rozdíl času vůči mediánu v daném období. Slouží pouze k určení směru (rychlejší/pomalejší)." />
                </th>
              </tr>
            </thead>
            <tbody>
              {anomalyItems.map((it) => {
                const diff =
                  medianTime != null ? it.final_time - medianTime : null;
                const deviation =
                  diff == null
                    ? "—"
                    : diff >= 0
                      ? `+${diff.toFixed(2)} s (pomalejší)`
                      : `${diff.toFixed(2)} s (rychlejší)`;
                return (
                  <tr key={it.result_id}>
                    <td>{formatDate(it.competition_date)}</td>
                    <td>{formatTime(it.final_time)}</td>
                    <td>{it.competition_name || "—"}</td>
                    <td>
                      <div className="anomaly-table__deviation">
                        <span>{deviation}</span>
                        {it.quality_flag === "suspicious" && (
                          <span className="anomaly-table__badge anomaly-table__badge--warning">
                            Doporučeno ověřit záznam
                            <InfoTooltip text="Záznam je mimo běžné hranice kategorie nebo obsahuje nezvykle velký skok oproti historii sportovce." />
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
  return (
    <Card title="Vyhledání závodníka">
      <div className="statistics-athlete-search">
        <p className="statistics-athlete-search__desc">
          Vyhledejte závodníka pro zobrazení neobvyklých výkonů.
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
          <div className="statistics-athlete-search__results">
            {isSearching ? (
              <p className="statistics-athlete-search__meta">Hledám...</p>
            ) : searchResults.length ? (
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
            ) : (
              <p className="statistics-athlete-search__meta">
                Pro tohoto závodníka zatím není k dispozici detekce neobvyklých
                výkonů. <br />
                Pro výpočet je potřeba alespoň 10 validních výsledků v dané
                kategorii a období.
              </p>
            )}
          </div>
        )}

        {selectedAthleteId && (
          <div className="statistics-athlete-search__selected">
            <span className="statistics-athlete-search__selected-label">
              Vybraný závodník:
            </span>
            <span className="statistics-athlete-search__selected-value">
              {selectedAthlete
                ? `${selectedAthlete.first_name} ${selectedAthlete.last_name}`
                : "Načítání..."}
            </span>
          </div>
        )}
      </div>
    </Card>
  );
}

// --- main page ---

export default function StatisticsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedAthleteId = searchParams.get("athlete_id") || null;
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const debounceRef = useRef(null);

  // 1) Fetch ALL detection windows for the athlete
  const {
    data: windows,
    isLoading: windowsLoading,
    isError: windowsError,
  } = useMlWindows("yearly_3y", selectedAthleteId);

  // 2) Fetch items from ALL windows to build category list and all-time stats
  const { runIdsByCategory } = useAllAthleteAnomalyItems(
    selectedAthleteId,
    windows,
  );

  // 3) Available categories derived from all windows
  const availableCategoryGroups = useMemo(
    () => [...runIdsByCategory.keys()].sort(),
    [runIdsByCategory],
  );

  // 4) Selected category – reset only when athlete changes
  const [selectedCategoryGroup, setSelectedCategoryGroup] = useState(null);
  const prevAthleteRef = useRef(selectedAthleteId);
  useEffect(() => {
    if (prevAthleteRef.current !== selectedAthleteId) {
      setSelectedCategoryGroup(null);
      prevAthleteRef.current = selectedAthleteId;
    }
  }, [selectedAthleteId]);

  // Auto-select first category when list first becomes available
  useEffect(() => {
    if (
      availableCategoryGroups.length > 0 &&
      !availableCategoryGroups.includes(selectedCategoryGroup)
    ) {
      setSelectedCategoryGroup(availableCategoryGroups[0]);
    }
  }, [availableCategoryGroups, selectedCategoryGroup]);

  // 5) Windows filtered to selected category
  const windowsForCategory = useMemo(() => {
    if (!selectedCategoryGroup || !windows) return windows ?? [];
    const runIds = runIdsByCategory.get(selectedCategoryGroup) ?? new Set();
    return windows.filter((w) => runIds.has(w.run_id));
  }, [windows, selectedCategoryGroup, runIdsByCategory]);

  // 6) Selected run_id – auto-adjust when not in filtered windows
  const [selectedRunId, setSelectedRunId] = useState(null);
  useEffect(() => {
    if (windowsForCategory.length === 0) return;
    const stillValid = windowsForCategory.some(
      (w) => w.run_id === selectedRunId,
    );
    if (!stillValid) {
      setSelectedRunId(windowsForCategory[0].run_id);
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
  };

  // 7) Fetch anomalies for selected run
  const { data, isLoading, isError } = useAthleteAnomalies(
    selectedAthleteId,
    selectedRunId,
  );

  const run = data?.run ?? null;
  const allItems = useMemo(() => data?.items ?? [], [data]);

  // Items for current window filtered by category
  const items = useMemo(() => {
    if (!selectedCategoryGroup) return allItems;
    return allItems.filter((it) => it.category_group === selectedCategoryGroup);
  }, [allItems, selectedCategoryGroup]);

  // Whether categories are still loading (windows loaded but items not yet in)
  const categoriesLoading =
    windowsLoading ||
    (!!selectedAthleteId &&
      !windowsError &&
      !!windows?.length &&
      availableCategoryGroups.length === 0);

  const searchResults = athletesData?.items ?? [];

  return (
    <div className="statistics-page page">
      <div className="statistics-page__header">
        <h1 className="statistics-page__title">Detekce neobvyklých výkonů</h1>
        <p className="statistics-page__desc">
          Analýza výkonů pomocí metody Isolation Forest. Pro výpočet je potřeba
          alespoň 10 validních výsledků v daném období.
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
              onChange={setSelectedCategoryGroup}
            />
          ) : null}

          {selectedCategoryGroup && (
            <YearSelect
              windows={windowsForCategory}
              value={selectedRunId}
              onChange={setSelectedRunId}
              isLoading={windowsLoading}
              isError={windowsError}
            />
          )}
        </div>
      )}

      {!selectedAthleteId ? (
        <div className="anomaly-no-athlete">
          <i className="fa-solid fa-user-magnifying-glass" />
          <p>
            Vyhledejte a vyberte závodníka. Zobrazí se přehled neobvyklých
            výkonů včetně detailů analýzy.
          </p>
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
            Pro tohoto závodníka není k dispozici žádná detekce neobvyklých
            výkonů. Pro analýzu je potřeba alespoň 10 výsledků v daném období.
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
