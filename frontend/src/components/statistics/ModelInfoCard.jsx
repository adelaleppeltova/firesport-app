import React, { useState } from "react";
import Card from "../Card";

// Mapování identifikátorů skupin na čitelné názvy
const CATEGORY_LABELS = {
  muz: "Muži / starší dorostenci",
  zena: "Ženy / dorostenky",
  mladsi_dorostenci: "Mladší a střední dorostenci",
};

function formatFullDate(dateStr) {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  return d.toLocaleDateString("cs-CZ", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function formatShortDate(dateStr) {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  return d.toLocaleDateString("cs-CZ", {
    day: "numeric",
    month: "numeric",
    year: "numeric",
  });
}

function formatContamination(c) {
  if (c == null) return "—";
  const pct = Math.round(c * 100);
  return `${c.toFixed(2).replace(".", ",")} (≈\u202f${pct}\u202f%)`;
}

function InfoRow({ label, value }) {
  return (
    <div className="model-info-card__row">
      <span className="model-info-card__label">{label}</span>
      <span className="model-info-card__value">{value ?? "—"}</span>
    </div>
  );
}

function SectionTitle({ children }) {
  return <h3 className="model-info-card__section-title">{children}</h3>;
}

/**
 * Karta s informacemi o nastavení modelu Isolation Forest.
 *
 * Props:
 *   run           – AnomalyRunInfo objekt (z API anomaly endpointu)
 *   athlete       – detailní objekt závodníka { first_name, last_name }
 *   categoryGroup – identifikátor skupiny kategorií (např. "muz", "zena")
 */
export default function ModelInfoCard({ run, athlete, categoryGroup }) {
  const [expanded, setExpanded] = useState(false);

  if (!run) return null;

  const athleteName = athlete
    ? `${athlete.first_name} ${athlete.last_name}`
    : "—";

  const categoryLabel = CATEGORY_LABELS[categoryGroup] ?? categoryGroup ?? "—";

  const windowRangeFull =
    run.window_start && run.window_end
      ? `${formatShortDate(run.window_start)} – ${formatShortDate(run.window_end)}`
      : "—";

  const computedDate = formatFullDate(run.created_at);
  const modelName = run.model_name ?? "Isolation Forest";
  const contamination = run.contamination; // float – skutečná hodnota pro tohoto závodníka
  const contaminationBase = run.contamination_base; // string – strategie (window runy)
  const contaminationStats = run.contamination_stats; // { min, median, max }
  const nEstimators = run.n_estimators;
  const randomState = run.random_state;
  const maxSamples = run.max_samples;
  const epsStd = run.eps_std;

  // Zobrazení počtu označených pro viditelnou část
  const nValid = run.n_valid_results_in_window;
  const nAnom = run.n_anomalies;
  const markedShort =
    nValid != null && nValid > 0 && nAnom != null
      ? `${nAnom} z ${nValid} (\u2248\u202f${Math.round((nAnom / nValid) * 100)}\u202f%)`
      : "—";

  // Zobrazení contamination pro detail
  const contaminationDetail =
    contamination != null ? (
      <>
        {formatContamination(contamination)}
        <span className="model-info-card__value-note">
          {`Označí se přibližně horních ${Math.round(contamination * 100)}\u202f% výsledků podle skóre atypičnosti`}
        </span>
      </>
    ) : contaminationBase ? (
      contaminationBase
    ) : (
      "—"
    );

  const contaminationStatsText = contaminationStats
    ? `min ${formatContamination(contaminationStats.min)}, medián ${formatContamination(contaminationStats.median)}, max ${formatContamination(contaminationStats.max)}`
    : null;

  return (
    <Card title="Detaily analýzy">
      <div className="model-info-card">
        {/* ── Viditelná část (vždy zobrazena) ── */}
        <div className="model-info-card__visible">
          <InfoRow label="Algoritmus" value={modelName} />
          <InfoRow label="Rozsah dat (okno)" value={windowRangeFull} />

          <InfoRow
            label="Výsledky (validní / vyřazené)"
            value={`${run.n_valid_results_in_window} / ${run.n_invalid_results_in_window ?? 0}`}
          />
          <InfoRow label="Označeno" value={markedShort} />
        </div>

        {/* ── Tlačítko pro rozbalení ── */}
        <button
          type="button"
          className="model-info-card__toggle"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
        >
          {expanded ? "Skrýt detaily" : "Zobrazit detaily"}
          <i
            className={`fa-solid ${expanded ? "fa-chevron-up" : "fa-chevron-down"} model-info-card__toggle-icon`}
          />
        </button>

        {/* ── Rozbalitelná část ── */}
        {expanded && (
          <div className="model-info-card__details">
            {/* Identifikace analýzy */}
            <SectionTitle>Identifikace analýzy</SectionTitle>
            <div className="model-info-card__section">
              <InfoRow label="Algoritmus" value={modelName} />
              <InfoRow label="Vypočteno" value={computedDate} />

              <InfoRow label="ID výpočtu (run ID)" value={run.run_id} />
            </div>

            {/* Kontext */}
            <SectionTitle>Kontext</SectionTitle>
            <div className="model-info-card__section">
              <InfoRow label="Závodník" value={athleteName} />
              <InfoRow label="Kategorie" value={categoryLabel} />
              <InfoRow
                label="Validní výsledky v okně"
                value={run.n_valid_results_in_window}
              />
              <InfoRow
                label="Vyřazené výsledky"
                value={run.n_invalid_results_in_window ?? 0}
              />
              <InfoRow label="Disciplína" value={run.discipline ?? "—"} />
            </div>

            {/* Hlavní parametry modelu */}
            <SectionTitle>Parametry detekce</SectionTitle>
            <div className="model-info-card__section">
              <InfoRow
                label="Nastavení prahu (contamination)"
                value={contaminationDetail}
              />
              {contaminationStats && (
                <InfoRow
                  label="Rozsah prahu napříč sportovci (min/medián/max)"
                  value={contaminationStatsText}
                />
              )}
              <InfoRow
                label="Seed (reprodukovatelnost)"
                value={randomState != null ? String(randomState) : "—"}
              />
              <InfoRow
                label="Počet stromů (n_estimators)"
                value={nEstimators != null ? nEstimators : "—"}
              />
              <InfoRow
                label="Velikost vzorku (max_samples)"
                value={maxSamples ?? "auto"}
              />
              {epsStd != null && (
                <InfoRow
                  label="Minimální variabilita dat"
                  value={`${String(epsStd).replace(".", ",")} (pokud jsou časy téměř stejné, detekce se nespustí)`}
                />
              )}
            </div>

            {/* Omezení metody */}
            <SectionTitle>Omezení metody</SectionTitle>
            <div className="model-info-card__section model-info-card__section--notes">
              <ul className="model-info-card__limits-list">
                <li>
                  Detekce pracuje pouze s časy výkonů (nezohledňuje podmínky
                  závodu).
                </li>
                <li>Neobvyklé mohou být rychlejší i pomalejší výkony.</li>
                <li>
                  Do výpočtu vstupují jen validní výsledky v okně analýzy.
                </li>
                <li>
                  Označení je podnět k interpretaci v kontextu, nikoli
                  automatický důkaz chyby.
                </li>
              </ul>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
