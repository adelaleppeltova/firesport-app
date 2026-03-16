/**
 * Shared empty / error state for home dashboard cards.
 *
 * type:
 *   "error"       – data se nepodařilo načíst (síťová chyba)
 *   "no-data"     – data zatím nejsou k dispozici
 *   "insufficient"– nedostatek záznamů pro výpočet
 */

const STATE_CONFIG = {
  error: {
    icon: "fa-triangle-exclamation",
    defaultText: "Načtení se nezdařilo.",
    modifier: "error",
  },
  "no-data": {
    icon: "fa-inbox",
    defaultText: "Žádné záznamy.",
    modifier: "no-data",
  },
  insufficient: {
    icon: "fa-circle-question",
    defaultText: "Nedostatek výsledků.",
    modifier: "insufficient",
  },
};

export default function CardState({ type = "no-data", text }) {
  const config = STATE_CONFIG[type] ?? STATE_CONFIG["no-data"];
  return (
    <div className={`empty-state empty-state--${config.modifier}`}>
      <i className={`fa-solid ${config.icon} empty-state__icon`} />
      <span className="empty-state__text">{text ?? config.defaultText}</span>
    </div>
  );
}
