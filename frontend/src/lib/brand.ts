/** Central presentation brand for VaaniDesk customer surfaces. */

export const brand = {
  companyName: "VaaniDesk Demo Store",
  assistantName: "VaaniDesk Support",
  productName: "VaaniDesk",
  supportGreeting: "Hi, how can I help you today?",
  supportSubtext: "AI-powered customer support",
} as const;

export const SUGGESTION_CHIPS = [
  "Track my order",
  "Return or refund",
  "Change delivery address",
  "Talk to support",
] as const;

/** Dev inspector is OFF unless explicitly enabled for local engineering. */
export const DEV_INSPECTOR_ENABLED =
  process.env.NEXT_PUBLIC_ENABLE_DEV_INSPECTOR === "true";
