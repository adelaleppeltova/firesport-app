import { useState } from "react";
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
  const contaminationMode = run.contamination_mode ?? "auto";
  const nEstimators = run.n_estimators;
  const randomState = run.random_state;
  const maxSamples = run.max_samples;
  const epsStd = run.eps_std;

  const nValid = run.n_valid_results_in_window;
  const nAnom = run.n_anomalies;
  const markedShort =
    nValid != null && nValid > 0 && nAnom != null
      ? `${nAnom} z ${nValid} (\u2248\u202f${Math.round((nAnom / nValid) * 100)}\u202f%)`
      : "—";

  const contaminationDetail =
    contaminationMode === "auto" ? (
      <>
        auto
        <span className="model-info-card__value-note">
          Podíl anomálií určuje model.
        </span>
      </>
    ) : "—";

  return (
    <Card title="Detaily analýzy">
      <div className="model-info-card">
        <div className="model-info-card__visible">
          <InfoRow label="Algoritmus" value={modelName} />
          <InfoRow label="Období analýzy" value={windowRangeFull} />

          <InfoRow
            label="Validní / vyřazené"
            value={`${run.n_valid_results_in_window} / ${run.n_invalid_results_in_window ?? 0}`}
          />
          <InfoRow label="Označeno" value={markedShort} />
        </div>

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

        {expanded && (
          <div className="model-info-card__details">
            <SectionTitle>Identifikace analýzy</SectionTitle>
            <div className="model-info-card__section">
              <InfoRow label="Algoritmus" value={modelName} />
              <InfoRow label="Vypočteno" value={computedDate} />

              <InfoRow label="Run ID" value={run.run_id} />
            </div>

            <SectionTitle>Kontext</SectionTitle>
            <div className="model-info-card__section">
              <InfoRow label="Závodník" value={athleteName} />
              <InfoRow label="Kategorie" value={categoryLabel} />
              <InfoRow
                label="Validní výsledky"
                value={run.n_valid_results_in_window}
              />
              <InfoRow
                label="Vyřazené výsledky"
                value={run.n_invalid_results_in_window ?? 0}
              />
              <InfoRow label="Disciplína" value={run.discipline ?? "—"} />
            </div>

            <SectionTitle>Parametry detekce</SectionTitle>
            <div className="model-info-card__section">
              <InfoRow
                label="Režim contamination"
                value={contaminationDetail}
              />
              <InfoRow
                label="Seed"
                value={randomState != null ? String(randomState) : "—"}
              />
              <InfoRow
                label="Počet stromů"
                value={nEstimators != null ? nEstimators : "—"}
              />
              <InfoRow
                label="Velikost vzorku"
                value={maxSamples ?? "auto"}
              />
              {epsStd != null && (
                <InfoRow
                  label="Minimální variabilita dat"
                  value={`${String(epsStd).replace(".", ",")} (při téměř shodných časech se detekce nespustí)`}
                />
              )}
            </div>

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
                <li>Označení samo o sobě neznamená chybu.</li>
              </ul>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
