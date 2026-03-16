export function getHistoryTrendModifier(trend) {
  switch (trend) {
    case "up":
      return "up";
    case "down":
      return "down";
    case "stable":
      return "stable";
    case "insufficient":
    default:
      return "neutral";
  }
}

const STABILITY_CONFIG = {
  stable: {
    match: (rating) => rating.includes("stabilní"),
    modifier: "stable",
  },
  variable: {
    match: (rating) => rating.includes("kolísavé"),
    modifier: "variable",
  },
  unknown: {
    match: () => true,
    modifier: "unknown",
  },
};

export function getStabilityModifier(rating = "") {
  const normalized = rating.toLowerCase();

  return (
    Object.values(STABILITY_CONFIG).find((config) => config.match(normalized))
      ?.modifier ?? "unknown"
  );
}
