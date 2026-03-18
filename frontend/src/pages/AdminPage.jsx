import { useEffect, useMemo, useRef, useState } from "react";

import Card from "../components/Card";
import PrimaryButton from "../components/PrimaryButton";
import {
  useAdminAssignResultAthlete,
  useAdminCreateAthleteFromResult,
  useAdminDeleteReviewResults,
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
    athlete.fs_codes?.length
      ? `FS kódy ${athlete.fs_codes.join(", ")}`
      : athlete.fscode
        ? `FSCode ${athlete.fscode}`
        : null,
  ]
    .filter(Boolean)
    .join(" • ");
}

function formatImportedLabel(item) {
  const imported = item.imported_athlete;
  return `${imported.first_name} ${imported.last_name}`.trim();
}

function formatSelectedImportedLabel(item) {
  const imported = item.imported_athlete;
  return [
    `${imported.first_name} ${imported.last_name}`.trim(),
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
  const [selectedResult, setSelectedResult] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState("");
  const [importSummary, setImportSummary] = useState(null);
  const [message, setMessage] = useState(null);
  const debounceRef = useRef(null);

  const reviewQuery = useAdminImportReview();
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
        type: "success",
        text: `Import dokončen. Zpracováno souborů: ${response.data?.files_processed ?? selectedFiles.length}. Vytvořeno výsledků: ${response.data?.results_created ?? 0}. Ke kontrole: ${(response.data?.results_needs_review ?? 0) + (response.data?.results_unmatched ?? 0)}.`,
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

  const reviewItems = reviewQuery.data?.items ?? [];
  const summary = reviewQuery.data?.summary ?? {
    total: 0,
    needs_review: 0,
    unmatched: 0,
  };
  const importStatus = {
    totalImported: importSummary?.total_imported ?? 0,
    reviewRequired: importSummary?.review_required ?? summary.total,
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
              <span>Vytvoření</span>
              <strong>{importStatus.athletesCreatedNew}</strong>
            </div>
            <div className="admin-page__summary-item">
              <span>Existující</span>
              <strong>{importStatus.athletesExistingMatched}</strong>
            </div>
          </div>
        </Card>
      </div>

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
                  assignMutation.isPending || createAthleteMutation.isPending
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
                        {item.match_status}
                      </span>
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
