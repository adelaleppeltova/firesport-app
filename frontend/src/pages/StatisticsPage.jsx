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
} from "recharts";
import Card from "../components/Card";
import PrimaryButton from "../components/PrimaryButton";
import {
  useAthleteAnomalies,
  useAthleteDetail,
  useAthletes,
  useMlWindows,
} from "../hooks/useApi";

// --- helpers ---

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

  let anomalyLabel = null;
  if (p.isAnomaly) {
    anomalyLabel =
      p.qualityFlag === "suspicious"
        ? "neobvyklý výkon – vyžaduje ověření dat"
        : "neobvyklý výkon (pravděpodobně výkonová odchylka)";
  }

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
      {anomalyLabel && (
        <div className="anomaly-chart__tooltip-badge">{anomalyLabel}</div>
      )}
    </div>
  );
}

// --- year selector ---

function YearSelect({ windows, value, onChange, isLoading, isError }) {
  if (isLoading) {
    return <div className="window-select__skeleton skeleton" />;
  }
  if (isError || !windows?.length) {
    return null; // no windows yet – silently hidden
  }
  return (
    <div className="window-select">
      <label className="window-select__label" htmlFor="window-select">
        Období:
      </label>
      <select
        id="window-select"
        className="window-select__input"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
      >
        {windows.map((w) => (
          <option key={w.run_id} value={w.run_id}>
            {w.label}
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
      <Card title="Přehled anomálií">
        <p className="empty-state">
          Pro tohoto závodníka zatím nebyla provedena analýza anomálií.
        </p>
      </Card>
    );
  }

  const period = `${formatMonthYear(run.window_start)} – ${formatMonthYear(run.window_end)}`;

  return (
    <Card title="Přehled anomálií">
      <div className="anomaly-summary">
        <div className="anomaly-summary__item">
          <span className="anomaly-summary__label">
            Celkový počet neobvyklých výkonů
          </span>
          <span className="anomaly-summary__value anomaly-summary__value--highlight">
            {run.n_anomalies}
          </span>
        </div>
        <div className="anomaly-summary__item">
          <span className="anomaly-summary__label">Období</span>
          <span className="anomaly-summary__value">{period}</span>
        </div>
        <div className="anomaly-summary__item">
          <span className="anomaly-summary__label">Závody celkem</span>
          <span className="anomaly-summary__value">
            {run.n_valid_results_in_window}
          </span>
        </div>
        {run.median_time != null && (
          <div className="anomaly-summary__item">
            <span className="anomaly-summary__label">Medián výkonu</span>
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

function ChartCard({ items }) {
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
    <Card title="Vývoj neobvyklých výkonů">
      {filtered.length === 0 ? (
        <p className="empty-state">Žádná data pro vybranou sezónu.</p>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <ScatterChart margin={{ top: 10, right: 16, bottom: 10, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
            <XAxis
              dataKey="x"
              type="number"
              scale="time"
              domain={xDomain}
              ticks={xTicks}
              tickFormatter={tickFormatter}
              tick={{ fontSize: 11 }}
              tickLine={false}
            />
            <YAxis
              dataKey="y"
              type="number"
              reversed={true}
              domain={yDomain}
              tickFormatter={(v) => `${v.toFixed(1)} s`}
              tick={{ fontSize: 11 }}
              tickLine={false}
              width={58}
            />
            <Tooltip content={<AnomalyTooltip />} isAnimationActive={false} />
            <Legend
              formatter={(value) =>
                value === "normal" ? "Normální výkon" : "Neobvyklý výkon"
              }
              iconType="circle"
            />
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

const PAGE_SIZE = 5;

function TableCard({ items, medianTime }) {
  const [page, setPage] = useState(1);

  const anomalyItems = useMemo(
    () =>
      items
        .filter((it) => it.is_anomaly)
        .sort(
          (a, b) => new Date(b.competition_date) - new Date(a.competition_date),
        ),
    [items],
  );

  const totalPages = Math.max(1, Math.ceil(anomalyItems.length / PAGE_SIZE));
  const pageItems = anomalyItems.slice(
    (page - 1) * PAGE_SIZE,
    page * PAGE_SIZE,
  );

  return (
    <Card title="Seznam neobvyklých výkonů">
      {anomalyItems.length === 0 ? (
        <p className="empty-state">Žádné neobvyklé výkony nebyly nalezeny.</p>
      ) : (
        <table className="anomaly-table">
          <thead>
            <tr>
              <th>Datum</th>
              <th>Čas (s)</th>
              <th>Závod</th>
              <th>Vzdálenost od očekávaného výkonu</th>
            </tr>
          </thead>
          <tbody>
            {pageItems.map((it) => {
              const diff =
                medianTime != null ? it.final_time - medianTime : null;
              const deviation =
                diff == null
                  ? "—"
                  : diff >= 0
                    ? `+${diff.toFixed(2)} s`
                    : `${diff.toFixed(2)} s`;
              return (
                <tr key={it.result_id}>
                  <td>{formatDate(it.competition_date)}</td>
                  <td>{formatTime(it.final_time)}</td>
                  <td>{it.competition_name || "—"}</td>
                  <td>
                    <div className="anomaly-table__deviation">
                      <span>{deviation}</span>
                      <span className="anomaly-table__badge">
                        {it.quality_flag === "suspicious"
                          ? "neobvyklý výkon – vyžaduje ověření dat"
                          : "neobvyklý výkon (pravděpodobně výkonová odchylka)"}
                      </span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
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
                Pro zadaný dotaz nebyl nalezen žádný závodník.
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

  // 1) Fetch available detection windows
  const {
    data: windows,
    isLoading: windowsLoading,
    isError: windowsError,
  } = useMlWindows();

  // 2) Track selected run_id; default to first (newest) window
  const [selectedRunId, setSelectedRunId] = useState(null);
  useEffect(() => {
    if (windows?.length && selectedRunId === null) {
      setSelectedRunId(windows[0].run_id);
    }
  }, [windows, selectedRunId]);

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
    runId: selectedRunId ?? undefined,
  });

  const { data: selectedAthleteDetail } = useAthleteDetail(selectedAthleteId);

  const handleSelectAthlete = (athleteId) => {
    const next = new URLSearchParams(searchParams);
    next.set("athlete_id", athleteId);
    setSearchParams(next, { replace: true });
    setSearch("");
    setDebouncedSearch("");
  };

  // 3) Fetch anomalies for selected run
  const { data, isLoading, isError } = useAthleteAnomalies(
    selectedAthleteId,
    selectedRunId,
  );

  const run = data?.run ?? null;
  const items = data?.items ?? [];
  const searchResults = athletesData?.items ?? [];

  return (
    <div className="statistics-page page">
      <div className="statistics-page__header">
        <h1 className="statistics-page__title">Detekce neobvyklých výkonů</h1>
        <p className="statistics-page__desc">
          Analýza výkonů pomocí metody Isolation Forest. Neobvyklé výkony jsou
          výsledky výrazně odlišné od očekávaného pásma. Pro analýzu je potřeba
          alespoň 10 výsledků.
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

      {selectedAthleteId && (
        <YearSelect
          windows={windows}
          value={selectedRunId}
          onChange={setSelectedRunId}
          isLoading={windowsLoading}
          isError={windowsError}
        />
      )}

      {!selectedAthleteId ? (
        <div className="anomaly-no-athlete">
          <i className="fa-solid fa-user-magnifying-glass" />
          <p>
            Vyhledejte a vyberte závodníka. Jeho ID se uloží do URL a zobrazí se
            statistiky neobvyklých výkonů.
          </p>
        </div>
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
          <ChartCard items={items} />
          <TableCard items={items} medianTime={run?.median_time ?? null} />
        </>
      )}
    </div>
  );
}
