/*
Shared academic-event helpers + taxonomy.
Single source of truth for event types, urgency tones, and the
Sticky Note Cascade palette used across the dashboard, updates,
calendar, and AI pages.
*/
import {
  AlertTriangle, Calendar, Bell, Flame, type LucideIcon,
} from 'lucide-react';

export type EventType = 'DEADLINE' | 'EVENT' | 'ALERT' | 'INFO';
export type EventStatus = 'ACTIVE' | 'CANCELLED' | 'SUPERSEDED';
export type DatePrecision = 'exact' | 'day_only' | 'unknown';

export interface AcademicEvent {
  id: string;
  user_id?: string;
  group_id?: string;
  group_name?: string;
  source_group_jid?: string;
  source_message_id?: string;
  event_type: EventType;
  course_code?: string;
  title: string;
  description?: string;
  venue?: string;
  date_time?: string;
  date_precision?: DatePrecision;
  status?: EventStatus;
  needs_review?: boolean;
  urgency_score: number;
  confidence_score: number;
  relevance_score?: number;
  actionability_score?: number;
  is_duplicate: boolean;
  is_archived?: boolean;
  revisions?: any[];
  created_at: string;
  updated_at?: string;
}

export const EVENT_TYPES: EventType[] = ['DEADLINE', 'ALERT', 'EVENT', 'INFO'];

export const TYPE_META: Record<EventType, { icon: LucideIcon; tag: string }> = {
  DEADLINE: { icon: Flame, tag: 'DEADLINE' },
  ALERT: { icon: AlertTriangle, tag: 'ALERT' },
  EVENT: { icon: Calendar, tag: 'EVENT' },
  INFO: { icon: Bell, tag: 'INFO' },
};

/* Solid color per event type (dots, bars, accents). */
export const TYPE_COLOR: Record<EventType, string> = {
  DEADLINE: 'var(--warning)',
  ALERT: 'var(--danger)',
  EVENT: 'var(--success)',
  INFO: 'var(--info)',
};

/* Dim background + foreground per event type (badges, icons). */
export const TYPE_STYLE: Record<EventType, { bg: string; fg: string }> = {
  ALERT: { bg: 'var(--danger-dim)', fg: 'var(--danger)' },
  DEADLINE: { bg: 'var(--warning-dim)', fg: 'var(--warning)' },
  EVENT: { bg: 'var(--success-dim)', fg: 'var(--success)' },
  INFO: { bg: 'var(--info-dim)', fg: 'var(--info)' },
};

const LAGOS_FORMAT = new Intl.DateTimeFormat("en-US", {
  timeZone: "Africa/Lagos",
  year: "numeric", month: "numeric", day: "numeric",
});

function startOfDay(d: Date): number {
  const parts = LAGOS_FORMAT.formatToParts(d);
  const get = (t: string) => Number(parts.find((p) => p.type === t)?.value);
  return new Date(get("year"), get("month") - 1, get("day"), 0, 0, 0, 0).getTime();
}

/**
 * Whole calendar days from today (local midnight diff).
 * Returns 0 for today, 1 for tomorrow, negative for overdue, Infinity when undated.
 */
export function daysLeft(iso?: string): number {
  if (!iso) return Infinity;
  return Math.round((startOfDay(new Date(iso)) - startOfDay(new Date())) / 86_400_000);
}

export function formatDateTime(iso?: string, precision?: DatePrecision): string {
  if (!iso) return precision === 'unknown' ? 'Date TBD' : 'No date set';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return 'No date set';

  const dateStr = d.toLocaleDateString('en-US', {
    timeZone: 'Africa/Lagos', month: 'short', day: 'numeric',
  });

  // If precision is day_only, suppress time entirely
  if (precision === 'day_only') {
    return dateStr;
  }

  const timeStr = d.toLocaleTimeString('en-US', {
    timeZone: 'Africa/Lagos', hour: 'numeric', minute: '2-digit', hour12: true,
  });

  // Treat 9 AM as the default "no specific time"; suppress it for cleaner display.
  if (timeStr === '9:00 AM') return dateStr;
  return `${dateStr} · ${timeStr}`;
}

export function relativeDay(iso?: string, precision?: DatePrecision): string {
  if (!iso) return precision === 'unknown' ? 'Date TBD' : 'No date set';
  const days = daysLeft(iso);
  if (days < 0) return `Due ${Math.abs(days)}d ago`;
  if (days === 0) return 'Today';
  if (days === 1) return 'Tomorrow';
  if (days <= 6) return `In ${days} days`;
  return formatDateTime(iso, precision);
}

/* Urgency tone used by list/card UI (solid semantic colors). */
export function urgencyTone(days: number) {
  if (days <= 1) return { color: 'var(--danger)', dim: 'var(--danger-dim)', label: 'Critical' };
  if (days <= 3) return { color: 'var(--warning)', dim: 'var(--warning-dim)', label: 'Soon' };
  return { color: 'var(--primary)', dim: 'var(--primary-dim)', label: 'Upcoming' };
}

/*
Sticky Note Cascade palette. Maps an event to a pastel sticky-note
background + label, following the PRD cascade colours:
  coral     -> deadline soon / alert
  lemon     -> upcoming
  mint      -> low urgency
  lavender  -> informational
*/
export function cascadeTone(e: AcademicEvent): { bg: string; label: string } {
  const d = daysLeft(e.date_time);
  if (e.event_type === 'INFO') return { bg: 'var(--lavender)', label: 'Info' };
  if (e.event_type === 'ALERT' || d <= 1) return { bg: 'var(--coral)', label: 'Deadline soon' };
  if (d <= 3) return { bg: 'var(--lemon)', label: 'Upcoming' };
  return { bg: 'var(--mint)', label: 'Low urgency' };
}

/* Sort upcoming deadlines first, then past deadlines by nearest date. */
export function sortBySoonest(a: AcademicEvent, b: AcademicEvent): number {
  const da = daysLeft(a.date_time);
  const db = daysLeft(b.date_time);

  const aPast = Number.isFinite(da) && da < 0;
  const bPast = Number.isFinite(db) && db < 0;

  if (aPast !== bPast) return aPast ? 1 : -1;

  const aTime = a.date_time ? new Date(a.date_time).getTime() : Infinity;
  const bTime = b.date_time ? new Date(b.date_time).getTime() : Infinity;
  return aTime - bTime;
}
