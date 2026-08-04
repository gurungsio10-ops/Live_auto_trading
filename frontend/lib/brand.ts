/** Product identity — keep attribution subtle on trading screens. */

export const BRAND = {
  name: "Project Atlas",
  shortName: "Atlas",
  wordmark: "ATLAS",
  subtitle: "Personal Automated Trading Intelligence",
  ownerName: "Saugat Gurung",
  ownerInitials: "SG",
  attribution: "Developed by Saugat Gurung",
  /** Place the owner photograph here when available. */
  ownerImagePath: "/saugat-gurung.jpg",
  ownerImageFsPath: "frontend/public/saugat-gurung.jpg",
  paperBadge: "PAPER TRADING",
  paperDisclaimer:
    "Paper mode only — all fills are simulated. Results do not guarantee future performance.",
} as const;
