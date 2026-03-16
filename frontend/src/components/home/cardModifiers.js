export const HISTORY_TREND_CONFIG = {
  up: {
    icon: "fa-arrow-up",
    label: "Zlepšení",
    state: "positive",
  },
  down: {
    icon: "fa-arrow-down",
    label: "Zhoršení",
    state: "negative",
  },
  stable: {
    icon: "fa-minus",
    label: "Beze změny",
    state: "neutral",
  },
  insufficient: {
    icon: "fa-circle-question",
    label: "Málo výsledků",
    state: "neutral",
  },
  default: {
    icon: "fa-minus",
    label: "Bez hodnocení",
    state: "neutral",
  },
};

const STABILITY_CONFIG = {
  stable: {
    match: (rating) => rating.includes("stabilní"),
    icon: "fa-check-circle",
    description: "Výsledky jsou stabilní a pravidelné.",
    state: "positive",
  },
  variable: {
    match: (rating) => rating.includes("kolísavé"),
    icon: "fa-circle-half-stroke",
    description: "Výkony se mezi závody výrazněji liší.",
    state: "warning",
  },
  unknown: {
    match: () => true,
    icon: "fa-circle-question",
    description: "Pro hodnocení zatím není dost výsledků.",
    state: "neutral",
  },
};

export function getHistoryTrendConfig(trend) {
  return HISTORY_TREND_CONFIG[trend] ?? HISTORY_TREND_CONFIG.default;
}

export function getHistoryTrendModifier(trend) {
  return getHistoryTrendConfig(trend).state;
}

export function getStabilityConfig(rating = "") {
  const normalized = rating.toLowerCase();

  return (
    Object.values(STABILITY_CONFIG).find((config) => config.match(normalized)) ??
    STABILITY_CONFIG.unknown
  );
}

export function getStabilityModifier(rating = "") {
  return getStabilityConfig(rating).state;
}
