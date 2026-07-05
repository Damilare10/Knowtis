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

export interface AcademicEvent {
  id: string;
  event_type: EventType;
  course_code?: string;
  title: string;
  description?: string;
  venue?: string;
  date_time?: string;
  urgency_score: number;
  confidence_score: number;
  is_duplicate: boolean;
  created_at: string;
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

function startOfDay(d: Date): number {
  // Compute midnight in the app timezone (Africa/Lagos), not the browser's
  // local zone, so day-boundary math agrees with the rest of the UI.
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Africa/Lagos",
    year: "numeric", month: "numeric", day: "numeric",
  }).formatToParts(d);
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

export function formatDateTime(iso?: string): string {
  if (!iso) return 'No date set';
  const d = new Date(iso);
  const timeStr = d.toLocaleTimeString('en-US', {
    timeZone: 'Africa/Lagos', hour: 'numeric', minute: '2-digit', hour12: true,
  });
  const dateStr = d.toLocaleDateString('en-US', {
    timeZone: 'Africa/Lagos', month: 'short', day: 'numeric',
  });
  // Treat 9 AM as the default "no specific time"; suppress it for cleaner display.
  if (timeStr === '9:00 AM') return dateStr;
  return `${dateStr} · ${timeStr}`;
}

export function relativeDay(iso?: string): string {
  const days = daysLeft(iso);
  if (days < 0) return `${Math.abs(days)}d overdue`;
  if (days === 0) return 'Today';
  if (days === 1) return 'Tomorrow';
  if (days <= 6) return `In ${days} days`;
  return formatDateTime(iso);
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

/* Sort events by soonest deadline (overdue first, undated last). */
export function sortBySoonest(a: AcademicEvent, b: AcademicEvent): number {
  return daysLeft(a.date_time) - daysLeft(b.date_time);
}
