import { useEffect, useMemo, useRef, useState } from "react";

import Card from "../components/Card";
import PrimaryButton from "../components/PrimaryButton";
import {
  useAdminAssignResultAthlete,
  useAdminCreateAthleteFromResult,
  useAdminDeleteReviewResults,
  useAdminCategoryReview,
  useAdminAthleteSearch,
  useAdminImportResults,
  useAdminImportReview,
  useAdminUnassignResultAthlete,
} from "../hooks/useApi";

function formatAthleteLabel(athlete) {
  return `${athlete.first_name} ${athlete.last_name}`;
}

function formatAthleteMeta(athlete) {
  return [
    athlete.birth_year ? `Ročník ${athlete.birth_year}` : null,
    athlete.teams?.length ? athlete.teams.join(", ") : null,
    athlete.fs_codes?.length ? `FS kódy ${athlete.fs_codes.join(", ")}` : null,
  ]
    .filter(Boolean)
    .join(" • ");
}

const matchReasons = {
  source_name_restored_identity_unverified: "Jméno doloženo, vazba na profil k ověření",
  name_segmentation_review: "Rozdělení jména vyžaduje kontrolu",
  missing_name: "Ve zdroji chybí jméno nebo příjmení.",
  shared_fscode: "FSCode sdílí více aktivních profilů.",
  conflicting_fscode: "FSCode je v rozporu se jménem nebo rokem narození.",
  unrecognized_fscode: "Profil má evidované jiné FSCode.",
  multiple_name_candidates: "Údajům odpovídá více profilů.",
  conflicting_birth_year: "Rok narození se liší od evidovaných profilů.",
  insufficient_identity: "Jméno a dostupné údaje k potvrzení identity nestačí.",
  possible_name_variant: "Podobný záznam může patřit existujícímu závodníkovi.",
  no_match: "Import nenašel odpovídající profil.",
  manual_admin_unassignment: "Přiřazení ručně odebral administrátor.",
};

const categoryReviewReasons = {
  unsupported_discipline: "Nepodporovaná disciplína",
  missing_discipline: "Chybí doložená disciplína",
  conflicting_result_discipline: "Disciplína výsledku a kategorie se liší",
  missing_verified_individual_or_birth_year: "Chybí potvrzený ročník nebo individuální řádek",
  unverified_60m_category: "Je potřeba ověřit rozdělení kategorií 60 m",
  noncanonical_60m_age_range: "Publikované rozmezí neodpovídá schválené kategorii",
  possible_duplicate_official_row: "Možná duplicitní výsledková listina",
  outside_canonical_age_range: "Ročník je mimo schválené věkové rozmezí",
  missing_100m_age_range_or_gender: "Chybí věkové rozmezí nebo doložené pohlaví",
  outside_source_or_canonical_age_range: "Věk neodpovídá publikovanému rozmezí",
  team_member_result_requires_separate_treatment: "Publikovaný běh člena družstva vyžaduje samostatné zařazení",
  unverified_team_or_progression: "Družstvo nebo postupovou soutěž je potřeba ověřit",
  possible_placeholder_final_time: "Výsledný čas může být zástupná hodnota",
  missing_or_invalid_official_final_time: "Chybí platný oficiální čas",
};

function formatImportedLabel(item) {
  const imported = item.imported_athlete;
  return imported.first_name && imported.last_name
    ? `${imported.first_name} ${imported.last_name}`
    : item.source_full_name || "Jméno nezjištěno";
}

function formatSelectedImportedLabel(item) {
  const imported = item.imported_athlete;
  return [
    formatImportedLabel(item),
    imported.birth_year ?? null,
    imported.fscode ?? null,
    item.team || null,
  ]
    .filter(Boolean)
    .join(", ");
}

export default function AdminPage() {
  const pageTopRef = useRef(null);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [nameProblemsOnly, setNameProblemsOnly] = useState(false);
  const [selectedResult, setSelectedResult] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState("");
  const [importSummary, setImportSummary] = useState(null);
  const [message, setMessage] = useState(null);
  const debounceRef = useRef(null);

  const reviewQuery = useAdminImportReview();
  const [categoryReviewPage, setCategoryReviewPage] = useState(1);
  const categoryReview = useAdminCategoryReview(categoryReviewPage);
  const importMutation = useAdminImportResults();
  const assignMutation = useAdminAssignResultAthlete();
  const createAthleteMutation = useAdminCreateAthleteFromResult();
  const deleteReviewMutation = useAdminDeleteReviewResults();
  const unassignMutation = useAdminUnassignResultAthlete();
  const athleteSearchQuery = useAdminAthleteSearch(debouncedSearchQuery);

  const selectedReviewItem = useMemo(
    () =>
      reviewQuery.data?.items?.find(
        (item) => item.result_id === selectedResult,
      ) ?? null,
    [reviewQuery.data, selectedResult],
  );

  useEffect(() => {
    if (!selectedReviewItem) return;
    const imported = selectedReviewItem.imported_athlete;
    const nextQuery = [imported.first_name, imported.last_name]
      .filter(Boolean)
      .join(" ")
      .trim();
    setSearchQuery(nextQuery);
    setDebouncedSearchQuery(nextQuery);
  }, [selectedReviewItem]);

  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedSearchQuery(searchQuery.trim());
    }, 300);

    return () => clearTimeout(debounceRef.current);
  }, [searchQuery]);

  const handleSelectReviewItem = (resultId) => {
    setSelectedResult(resultId);
    pageTopRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const handleImport = async () => {
    if (!selectedFiles.length || importMutation.isPending) return;
    try {
      const response = await importMutation.mutateAsync(selectedFiles);
      setImportSummary(response.data ?? null);
      setMessage({
        type: response.data?.errors?.length ? "error" : "success",
        text: response.data?.errors?.length ? "Import dokončen s chybami nebo konflikty." : "Import dokončen.",
      });
      setSelectedFiles([]);
    } catch (error) {
      setMessage({
        type: "error",
        text:
          error?.response?.data?.detail ||
          "Import se nepodařilo dokončit. Zkus to prosím znovu.",
      });
    }
  };

  const handleAssign = async (athleteId) => {
    if (!selectedReviewItem || assignMutation.isPending) return;
    try {
      await assignMutation.mutateAsync({
        resultId: selectedReviewItem.result_id,
        athleteId,
      });
      setMessage({
        type: "success",
        text: "Výsledek byl přiřazen k vybranému závodníkovi.",
      });
      setSelectedResult(null);
      setSearchQuery("");
      setDebouncedSearchQuery("");
    } catch (error) {
      setMessage({
        type: "error",
        text:
          error?.response?.data?.detail || "Přiřazení se nepodařilo dokončit.",
      });
    }
  };

  const handleUnassign = async (resultId) => {
    if (unassignMutation.isPending) return;
    try {
      await unassignMutation.mutateAsync(resultId);
      setMessage({
        type: "success",
        text: "Přiřazení výsledku bylo zrušeno.",
      });
    } catch (error) {
      setMessage({
        type: "error",
        text:
          error?.response?.data?.detail || "Odpárování se nepodařilo dokončit.",
      });
    }
  };

  const handleDeleteReviewResults = async () => {
    if (deleteReviewMutation.isPending) return;

    const confirmed = window.confirm(
      "Opravdu chceš smazat všechny záznamy v tabulce Záznamy ke kontrole?",
    );
    if (!confirmed) return;

    try {
      const response = await deleteReviewMutation.mutateAsync();
      setMessage({
        type: "success",
        text: `Smazáno záznamů: ${response.deleted_count ?? 0}.`,
      });
      setSelectedResult(null);
      setSearchQuery("");
      setDebouncedSearchQuery("");
    } catch (error) {
      setMessage({
        type: "error",
        text:
          error?.response?.data?.detail ||
          "Mazání záznamů se nepodařilo dokončit.",
      });
    }
  };

  const handleCreateAthlete = async () => {
    if (!selectedReviewItem || createAthleteMutation.isPending) return;
    try {
      await createAthleteMutation.mutateAsync(selectedReviewItem.result_id);
      setMessage({
        type: "success",
        text: "Byl vytvořen nový závodník a výsledek se k němu přiřadil.",
      });
      setSelectedResult(null);
      setSearchQuery("");
      setDebouncedSearchQuery("");
    } catch (error) {
      setMessage({
        type: "error",
        text:
          error?.response?.data?.detail ||
          "Vytvoření závodníka se nepodařilo dokončit.",
      });
    }
  };

  const allReviewItems = reviewQuery.data?.items ?? [];
  const reviewItems = nameProblemsOnly
    ? allReviewItems.filter((item) => item.name_issues?.length)
    : allReviewItems;
  const summary = reviewQuery.data?.summary ?? {
    total: 0,
    needs_review: 0,
    unmatched: 0,
  };
  const importStatus = {
    totalImported: importSummary?.total_imported ?? 0,
    reviewRequired: importSummary?.results_needs_review ?? summary.needs_review,
    unmatched: importSummary?.results_unmatched ?? summary.unmatched,
    duplicates: importSummary?.results_duplicates_skipped ?? 0,
    errors: importSummary?.errors ?? [],
    athletesCreatedNew: importSummary?.athletes_created_new ?? 0,
    athletesExistingMatched: importSummary?.athletes_existing_matched ?? 0,
  };

  return (
    <div className="admin-page page" ref={pageTopRef}>
      <header className="admin-page__header">
        <div>
          <p className="admin-page__eyebrow">Administrace importu</p>
          <h1>Kontrola párování výsledků</h1>
          <p className="admin-page__lead">
            Import spouštěj přes JSON soubor a problematické záznamy dořeš
            ručně.
          </p>
        </div>
      </header>

      <div className="admin-page__grid">
        <Card title="Spuštění importu">
          <div className="admin-page__import">
            <label className="admin-page__field">
              <span>JSON soubor s výsledky</span>
              <input
                type="file"
                accept=".json,application/json"
                multiple
                onChange={(event) =>
                  setSelectedFiles(Array.from(event.target.files ?? []))
                }
              />
            </label>
            {selectedFiles.length ? (
              <p className="admin-page__hint">
                Vybráno souborů: <strong>{selectedFiles.length}</strong>
              </p>
            ) : null}
            <PrimaryButton
              type="button"
              onClick={handleImport}
              disabled={!selectedFiles.length || importMutation.isPending}
              isLoading={importMutation.isPending}
            >
              Spustit import
            </PrimaryButton>
            {message ? (
              <p
                className={`admin-page__message admin-page__message--${message.type}`}
                role="status"
              >
                {message.text}
              </p>
            ) : null}
          </div>
        </Card>

        <Card title="Stav importu">
          <div className="admin-page__summary">
            <div className="admin-page__summary-item">
              <span>Celkem importováno</span>
              <strong>{importStatus.totalImported}</strong>
            </div>
            <div className="admin-page__summary-item">
              <span>Ke kontrole</span>
              <strong>{importStatus.reviewRequired}</strong>
            </div>
            <div className="admin-page__summary-item">
              <span>Noví závodníci</span>
              <strong>{importStatus.athletesCreatedNew}</strong>
            </div>
            <div className="admin-page__summary-item">
              <span>Automaticky přiřazené výsledky</span>
              <strong>{importStatus.athletesExistingMatched}</strong>
            </div>
            <div className="admin-page__summary-item">
              <span>Bez potvrzené identity</span>
              <strong>{importStatus.unmatched}</strong>
            </div>
            <div className="admin-page__summary-item">
              <span>Přeskočené duplicity</span>
              <strong>{importStatus.duplicates}</strong>
            </div>
            <div className="admin-page__summary-item">
              <span>Zařazení ke kontrole</span>
              <strong>{importSummary?.classification_review_required ?? 0}</strong>
            </div>
            <div className="admin-page__summary-item">
              <span>Chyby a konflikty</span>
              <strong>{importStatus.errors.length}</strong>
            </div>
          </div>
          {importStatus.errors.length > 0 && (
            <ul>
              {importStatus.errors.map((error, index) => (
                <li key={index}>{error}</li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card title="Kategorie a disciplíny ke kontrole">
        {categoryReview.isError ? <p>Kontrolu se nepodařilo načíst.</p> : (
          <>
            <p>{categoryReview.data?.total ?? "—"} výsledků mimo veřejné statistiky.</p>
            <ul>
              {categoryReview.data?.items.map((item) => (
                <li key={item.result_id}>
                  {item.date?.slice(0, 10)} · {item.discipline ?? "Neznámá disciplína"} ·{" "}
                  {item.category || "Kategorie neuvedena"} ·{" "}
                  {categoryReviewReasons[item.reason] ?? "Ověřit údaje ve výsledkové listině"}
                  {item.rank != null && ` · pořadí ${item.rank}`}
                  {" · "}<small>ID {item.result_id}</small>
                  {/^https?:\/\//i.test(item.source_url ?? "") && (
                    <> · <a href={item.source_url}>Zdroj</a></>
                  )}
                </li>
              ))}
            </ul>
            {categoryReviewPage > 1 && (
              <button type="button" onClick={() => setCategoryReviewPage(categoryReviewPage - 1)}>Předchozí</button>
            )}
            {categoryReviewPage * 25 < categoryReview.data?.total && (
              <button type="button" onClick={() => setCategoryReviewPage(categoryReviewPage + 1)}>Další</button>
            )}
          </>
        )}
      </Card>

      <Card title="Vyhledání athlete pro ruční spojení">
        {!selectedReviewItem ? (
          <p className="admin-page__hint">
            Vyber v tabulce záznam, který chceš ručně přiřadit.
          </p>
        ) : (
          <div className="admin-page__assignment">
            <div className="admin-page__assignment-header">
              <p className="admin-page__hint">
                Vybraný záznam:{" "}
                <strong>{formatSelectedImportedLabel(selectedReviewItem)}</strong>
              </p>
              <button
                type="button"
                className="btn admin-page__action-button admin-page__action-button--secondary admin-page__assignment-create"
                onClick={handleCreateAthlete}
                disabled={
                  assignMutation.isPending || createAthleteMutation.isPending ||
                  ["missing_name", "name_segmentation_review"].includes(selectedReviewItem.match_reason)
                }
              >
                Vytvořit závodníka
              </button>
            </div>

            <label className="admin-page__field">
              <span>Vyhledat atleta</span>
              <input
                type="search"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="Jméno, příjmení nebo FS kód"
              />
            </label>

            <div className="admin-page__search-results">
              {athleteSearchQuery.isFetching ? (
                <p>Vyhledávám…</p>
              ) : athleteSearchQuery.data?.items?.length ? (
                athleteSearchQuery.data.items.map((athlete) => (
                  <div key={athlete._id}>
                    <div className="admin-page__search-result">
                      <strong>{formatAthleteLabel(athlete)}</strong>
                      {formatAthleteMeta(athlete) ? (
                        <span className="admin-page__candidate-meta">
                          {formatAthleteMeta(athlete)}
                        </span>
                      ) : null}
                      <div className="admin-page__search-result-actions">
                        <button
                          type="button"
                          className="btn admin-page__action-button"
                          onClick={() => handleAssign(athlete._id)}
                          disabled={
                            assignMutation.isPending ||
                            createAthleteMutation.isPending
                          }
                        >
                          Přiřadit závodníka
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              ) : debouncedSearchQuery.length >= 2 ? (
                <div className="admin-page__search-result">
                  <p className="admin-page__hint">
                    Nebyl nalezen žádný závodník.
                  </p>
                </div>
              ) : (
                <p>Zadej alespoň 2 znaky.</p>
              )}
            </div>
          </div>
        )}
      </Card>

      <Card title="Záznamy ke kontrole">
        <div className="admin-page__table-actions">
          <button
            type="button"
            className="btn admin-page__action-button admin-page__action-button--danger"
            onClick={handleDeleteReviewResults}
            disabled={
              deleteReviewMutation.isPending || reviewItems.length === 0
            }
          >
            Smazat tabulku
          </button>
        </div>
        <div className="admin-page__table-wrapper">
          <label>
            <input type="checkbox" checked={nameProblemsOnly}
              onChange={(event) => setNameProblemsOnly(event.target.checked)} />
            Pouze záznamy s problémem ve jménu
          </label>
          <table className="table table--compact admin-review-table">
            <colgroup>
              <col className="admin-review-table__col admin-review-table__col--imported" />
              <col className="admin-review-table__col admin-review-table__col--status" />
              <col className="admin-review-table__col admin-review-table__col--birth-year" />
              <col className="admin-review-table__col admin-review-table__col--fscode" />
              <col className="admin-review-table__col admin-review-table__col--team" />
              <col className="admin-review-table__col admin-review-table__col--actions" />
            </colgroup>
            <thead>
              <tr>
                <th>Importovaný závodník</th>
                <th>Stav</th>
                <th>Rok narození</th>
                <th>FSCode</th>
                <th>Sbor</th>
                <th>Akce</th>
              </tr>
            </thead>
            <tbody>
              {reviewQuery.isLoading ? (
                <tr>
                  <td colSpan={6}>Načítám záznamy ke kontrole…</td>
                </tr>
              ) : reviewItems.length === 0 ? (
                <tr>
                  <td colSpan={6}>Žádné nevyřešené záznamy.</td>
                </tr>
              ) : (
                reviewItems.map((item) => (
                  <tr
                    key={item.result_id}
                    className={
                      selectedResult === item.result_id
                        ? "admin-review-table__row admin-review-table__row--active"
                        : "admin-review-table__row"
                    }
                  >
                    <td>
                      <strong>{formatImportedLabel(item)}</strong>
                      {(!!item.name_issues?.length || item.source_full_name) && (
                        <details>
                          <summary>Původní hodnoty jména</summary>
                          {item.source_full_name && <div>{item.source_full_name}</div>}
                          <div>{JSON.stringify(item.source_person_name)}</div>
                        </details>
                      )}
                      {item.source_url?.startsWith("https://") && (
                        <a href={item.source_url}>Zdroje výsledku</a>
                      )}
                      <div className="admin-review-table__meta">
                        {item.date
                          ? new Date(item.date).toLocaleDateString("cs-CZ")
                          : "Datum neznámé"}
                      </div>
                    </td>
                    <td>
                      <span
                        className={`admin-badge admin-badge--${item.match_status}`}
                      >
                        {item.match_status === "needs_review" ? "Vyžaduje kontrolu" : "Bez propojení s profilem"}
                      </span>
                      {item.match_reason && (
                        <div className="admin-review-table__meta">
                          {matchReasons[item.match_reason] ?? item.match_reason}
                        </div>
                      )}
                    </td>
                    <td>{item.imported_athlete.birth_year ?? "—"}</td>
                    <td>{item.imported_athlete.fscode ?? "—"}</td>
                    <td>{item.team || "—"}</td>
                    <td>
                      <div className="admin-review-table__actions">
                        <button
                          type="button"
                          className="btn admin-page__table-button"
                          onClick={() => handleSelectReviewItem(item.result_id)}
                        >
                          Přiřadit atleta
                        </button>
                        {item.current_athlete ? (
                          <button
                            type="button"
                            className="btn admin-page__table-button admin-page__table-button--danger"
                            onClick={() => handleUnassign(item.result_id)}
                          >
                            Zrušit přiřazení
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
