/*
Knowtis Date/Time helpers.

The backend persists datetimes as naive UTC and now serializes them through
`format_iso_for_api`, which appends ``Z`` so ``new Date(...)`` on the client
parses them as an absolute UTC instant. Every display-time formatter in the
UI then pins the ``timeZone`` option to Africa/Lagos so wall-clock values
shown to the user always match Nigerian local time, regardless of where the
browser is running.
*/

/** IANA timezone used for every date/time display. Nigeria = WAT (UTC+1, no DST). */
export const APP_TIMEZONE = "Africa/Lagos";

/** Shared options bag: locale + Africa/Lagos pin, 24-hour time, english names. */
const LAGOS: Intl.DateTimeFormatOptions = { timeZone: APP_TIMEZONE };

/** "Aug 14, 2026" */
export function formatDate(iso: string | null | undefined, opts?: Intl.DateTimeFormatOptions): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", { ...LAGOS, ...opts });
}

/** "14 Aug" / "14 Aug 2026" */
export function formatDateShort(iso: string | null | undefined, withYear = false): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", {
    ...LAGOS,
    month: "short",
    day: "numeric",
    ...(withYear ? { year: "numeric" } : {}),
  });
}

/** "Fri 14" / "Fri Aug 14" */
export function formatWeekdayShort(iso: string | null | undefined, withMonth = false): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", {
    ...LAGOS,
    weekday: "short",
    day: "numeric",
    ...(withMonth ? { month: "short" } : {}),
  });
}

/** "Today, 06:42" / "Yesterday, 09:00" / "Mon, 14:30" / "Aug 14, 09:00" */
export function formatRelative(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  const now = new Date();
  // Compare wall-clock days in Lagos.
  const lagosDate = (x: Date) =>
    new Intl.DateTimeFormat("en-CA", { timeZone: APP_TIMEZONE, year: "numeric", month: "2-digit", day: "2-digit" }).format(x);
  const todayKey = lagosDate(now);
  const targetKey = lagosDate(d);
  const time = d.toLocaleTimeString("en-US", { ...LAGOS, hour: "2-digit", minute: "2-digit", hour12: false });

  const oneDay = 86_400_000;
  const todayMidnight = new Date(now.toLocaleString("en-US", { timeZone: APP_TIMEZONE }));
  todayMidnight.setHours(0, 0, 0, 0);
  const targetMidnight = new Date(d.toLocaleString("en-US", { timeZone: APP_TIMEZONE }));
  targetMidnight.setHours(0, 0, 0, 0);

  const diffDays = Math.round((targetMidnight.getTime() - todayMidnight.getTime()) / oneDay);
  if (targetKey === todayKey) return `Today, ${time}`;
  if (diffDays === 1) return `Tomorrow, ${time}`;
  if (diffDays === -1) return `Yesterday, ${time}`;
  if (diffDays > 0 && diffDays <= 6) {
    const dow = d.toLocaleDateString("en-US", { ...LAGOS, weekday: "short" });
    return `${dow}, ${time}`;
  }
  return `${d.toLocaleDateString("en-US", { ...LAGOS, month: "short", day: "numeric" })}, ${time}`;
}

/** "14:30" — 24-hour, Lagos pin. */
export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString("en-US", { ...LAGOS, hour: "2-digit", minute: "2-digit", hour12: false });
}

/** "Just now" / "12m ago" / "3h ago" / "Aug 14, 09:00" — coarse relative for feeds/lists. */
export function formatTimeAgo(iso: string | null | undefined, nowMs: number = Date.now()): string {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  if (isNaN(t)) return "";
  const diff = Math.max(0, nowMs - t);
  if (diff < 60_000) return "just now";
  const mins = Math.floor(diff / 60_000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return formatDateShort(iso, true);
}
