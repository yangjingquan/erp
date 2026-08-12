export const ERP_TIME_ZONE = "Asia/Shanghai";

type DateParts = Record<string, string>;

function localParts(value: Date): DateParts {
  return Object.fromEntries(
    new Intl.DateTimeFormat("zh-CN", {
      timeZone: ERP_TIME_ZONE,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hourCycle: "h23",
    })
      .formatToParts(value)
      .filter((part) => part.type !== "literal")
      .map((part) => [part.type, part.value]),
  );
}

export function localDateString(value: Date = new Date()): string {
  const parts = localParts(value);
  return `${parts.year}-${parts.month}-${parts.day}`;
}

export function localMonthString(value: Date = new Date()): string {
  const parts = localParts(value);
  return `${parts.year}-${parts.month}`;
}

export function localDateTimeString(value: Date = new Date()): string {
  const parts = localParts(value);
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}:${parts.second}`;
}

export function formatLocalDateTime(value: unknown): string {
  if (!value) return "-";
  const raw = String(value);
  const hasTimezone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(raw);
  if (!hasTimezone && /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/.test(raw)) {
    return raw.replace("T", " ").slice(0, 19);
  }
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return raw.replace("T", " ").slice(0, 19);
  return localDateTimeString(parsed).replace("T", " ");
}
