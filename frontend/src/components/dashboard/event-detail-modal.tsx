'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Clock, MapPin, Calendar, Check, Edit3, Trash2, ShieldCheck, AlertCircle, Save } from 'lucide-react';
import type { AcademicEvent, EventType } from '@/lib/events';
import { TYPE_META, EVENT_TYPES, daysLeft, formatDateTime } from '@/lib/events';
import { useAppStore } from '@/lib/store';

const EASE = [0.16, 1, 0.3, 1] as const;

function urgencyLabel(days: number): { color: string; text: string } {
  if (days < 0) return { color: '#E54835', text: `Due ${Math.abs(days)}d ago` };
  if (days === 0) return { color: '#E54835', text: 'Due today' };
  if (days === 1) return { color: '#F2A53C', text: 'Due tomorrow' };
  if (days <= 3) return { color: '#F2A53C', text: 'Soon' };
  return { color: '#4285F4', text: 'Upcoming' };
}

export default function EventDetailModal({
  event,
  onClose,
}: {
  event: AcademicEvent;
  onClose: () => void;
}) {
  const { updateEvent, confirmEvent, dismissEvent } = useAppStore();
  const [isEditing, setIsEditing] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [editTitle, setEditTitle] = useState(event.title);
  const [editCourseCode, setEditCourseCode] = useState(event.course_code || '');
  const [editVenue, setEditVenue] = useState(event.venue || '');
  const [editEventType, setEditEventType] = useState<EventType>(event.event_type);
  const [editDateTime, setEditDateTime] = useState(
    event.date_time ? new Date(event.date_time).toISOString().slice(0, 16) : ''
  );

  const meta = TYPE_META[isEditing ? editEventType : event.event_type];
  const days = daysLeft(event.date_time);
  const urgent = urgencyLabel(days);

  const handleConfirm = async () => {
    setIsSubmitting(true);
    await confirmEvent(event.id);
    setIsSubmitting(false);
    onClose();
  };

  const handleDismiss = async () => {
    setIsSubmitting(true);
    await dismissEvent(event.id);
    setIsSubmitting(false);
    onClose();
  };

  const handleSaveEdit = async () => {
    setIsSubmitting(true);
    const patch: Partial<AcademicEvent> = {
      title: editTitle.trim(),
      course_code: editCourseCode.trim() || undefined,
      venue: editVenue.trim() || undefined,
      event_type: editEventType,
      date_time: editDateTime ? new Date(editDateTime).toISOString() : undefined,
    };
    await updateEvent(event.id, patch);
    setIsSubmitting(false);
    setIsEditing(false);
    onClose();
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="fixed inset-0 z-[100] flex items-center justify-center bg-[#171717]/50 backdrop-blur-sm p-4 overflow-y-auto"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.96 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 20, scale: 0.96 }}
        transition={{ duration: 0.3, ease: EASE }}
        className="w-full max-w-lg rounded-[28px] bg-white shadow-[0_32px_64px_rgba(0,0,0,0.18),inset_0_1px_0_rgba(255,255,255,1)] overflow-hidden my-auto"
      >
        {/* Header */}
        <div className="relative p-5 pb-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2.5">
              <div className="flex h-10 w-10 items-center justify-center rounded-[16px] bg-white shadow-[0_8px_16px_rgba(30,30,30,0.06),inset_0_2px_4px_rgba(255,255,255,1)]">
                <meta.icon className="w-5 h-5 text-[#171717]" />
              </div>
              <div>
                <span className="badge text-[10px]">{meta.tag}</span>
                {(isEditing ? editCourseCode : event.course_code) && (
                  <span className="ml-2 text-[11px] font-bold text-[#74736D]">
                    {isEditing ? editCourseCode : event.course_code}
                  </span>
                )}
              </div>
            </div>
            <button
              onClick={onClose}
              className="flex h-12 w-12 items-center justify-center rounded-full bg-[#F4F3EF] text-[#74736D] hover:bg-[#E9E9E6] transition-colors"
              aria-label="Close"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {!isEditing ? (
            <h2 className="text-[22px] font-black tracking-[-0.03em] text-[#171717] leading-[1.15]">
              {event.title}
            </h2>
          ) : (
            <div className="space-y-2 mt-1">
              <label className="block text-[11px] font-bold uppercase tracking-wider text-[#74736D]">Event Title</label>
              <input
                type="text"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                className="input text-[16px] font-bold w-full"
                placeholder="Title"
              />
            </div>
          )}
        </div>

        {/* Details & Actions */}
        <div className="px-5 pb-5 space-y-4">
          {/* Needs Review Prompt Banner */}
          {event.needs_review && !isEditing && (
            <div className="rounded-[20px] bg-[#FFF8EE] border border-[#FFE2B8] p-4 flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-[#D97706] shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-[13px] font-black text-[#92400E]">Review Required</p>
                <p className="text-[12px] font-semibold text-[#B45309] mt-0.5">
                  AI extracted this announcement. Please confirm it is correct or edit details.
                </p>
                <div className="flex flex-wrap gap-2 mt-3">
                  <button
                    onClick={handleConfirm}
                    disabled={isSubmitting}
                    className="min-h-[48px] px-4 rounded-xl bg-[#10B981] hover:bg-[#059669] text-white text-xs font-bold flex items-center gap-1.5 shadow-sm transition-all active:scale-[0.98]"
                  >
                    <Check className="w-4 h-4" /> Confirm Correct
                  </button>
                  <button
                    onClick={() => setIsEditing(true)}
                    disabled={isSubmitting}
                    className="min-h-[48px] px-4 rounded-xl bg-white border border-[#E5E7EB] text-[#374151] hover:bg-[#F9FAFB] text-xs font-bold flex items-center gap-1.5 shadow-sm transition-all active:scale-[0.98]"
                  >
                    <Edit3 className="w-4 h-4" /> Edit
                  </button>
                  <button
                    onClick={handleDismiss}
                    disabled={isSubmitting}
                    className="min-h-[48px] px-4 rounded-xl bg-[#FEE2E2] hover:bg-[#FCA5A5] text-[#B91C1C] text-xs font-bold flex items-center gap-1.5 transition-all active:scale-[0.98]"
                  >
                    <Trash2 className="w-4 h-4" /> Dismiss
                  </button>
                </div>
              </div>
            </div>
          )}

          {!isEditing ? (
            <>
              {/* Date & Venue */}
              <div className="flex flex-wrap gap-3">
                {event.date_time && (
                  <div className="flex items-center gap-2 rounded-[14px] bg-[#F4F3EF] px-3 py-2">
                    <Calendar className="w-4 h-4 text-[#74736D]" />
                    <span className="text-[13px] font-bold text-[#171717]">
                      {formatDateTime(event.date_time, event.date_precision)}
                    </span>
                  </div>
                )}
                {event.venue && (
                  <div className="flex items-center gap-2 rounded-[14px] bg-[#F4F3EF] px-3 py-2">
                    <MapPin className="w-4 h-4 text-[#74736D]" />
                    <span className="text-[13px] font-bold text-[#171717]">{event.venue}</span>
                  </div>
                )}
              </div>

              {/* Urgency pill & Days left */}
              <div className="flex items-center gap-2">
                <span
                  className="inline-flex items-center gap-1 rounded-full px-3 py-1 text-[11px] font-black uppercase tracking-wide"
                  style={{ background: `${urgent.color}15`, color: urgent.color }}
                >
                  <Clock className="w-3.5 h-3.5" /> {urgent.text}
                </span>
                {days > 0 && (
                  <span className="text-[11px] font-bold text-[#74736D]">{days} day{days !== 1 ? 's' : ''} left</span>
                )}
              </div>

              {/* Description */}
              {event.description && (
                <div className="rounded-[20px] bg-[#F4F3EF] p-4">
                  <p className="text-[14px] font-semibold leading-relaxed text-[#5F5F59]">{event.description}</p>
                </div>
              )}

              {/* Provenance info */}
              <div className="pt-2 border-t border-[#F4F3EF] flex flex-col items-center gap-1 text-center">
                <p className="text-[12px] font-bold text-[#74736D]">
                  {event.group_name ? `From ${event.group_name}` : 'From WhatsApp Channel'}
                </p>
                <p className="text-[11px] font-semibold text-[#A3A29C]">
                  Extracted {new Date(event.created_at).toLocaleDateString('en-US', { timeZone: 'Africa/Lagos', month: 'short', day: 'numeric', year: 'numeric' })}
                </p>
              </div>

              {/* Bottom quick actions if not already reviewing */}
              {!event.needs_review && (
                <div className="flex items-center justify-end gap-2 pt-1">
                  <button
                    onClick={() => setIsEditing(true)}
                    className="min-h-[48px] px-4 rounded-xl bg-[#F4F3EF] hover:bg-[#E9E9E6] text-[#374151] text-xs font-bold flex items-center gap-1.5 transition-all"
                  >
                    <Edit3 className="w-4 h-4" /> Edit
                  </button>
                  <button
                    onClick={handleDismiss}
                    className="min-h-[48px] px-4 rounded-xl bg-[#FFF1F0] hover:bg-[#FEE2E2] text-[#E54835] text-xs font-bold flex items-center gap-1.5 transition-all"
                  >
                    <Trash2 className="w-4 h-4" /> Delete
                  </button>
                </div>
              )}
            </>
          ) : (
            /* Editing form */
            <div className="space-y-3">
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-[#74736D] mb-1">Course Code</label>
                <input
                  type="text"
                  value={editCourseCode}
                  onChange={(e) => setEditCourseCode(e.target.value)}
                  className="input w-full"
                  placeholder="e.g. CSC301"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-[#74736D] mb-1">Event Type</label>
                <div className="grid grid-cols-2 gap-2">
                  {EVENT_TYPES.map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => setEditEventType(t)}
                      className={`min-h-[48px] rounded-xl text-xs font-bold px-3 py-2 border transition-all ${
                        editEventType === t
                          ? 'bg-[#FF5A36] text-white border-[#FF5A36]'
                          : 'bg-[#F4F3EF] text-[#374151] border-transparent hover:bg-[#E9E9E6]'
                      }`}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-[#74736D] mb-1">Date & Time</label>
                <input
                  type="datetime-local"
                  value={editDateTime}
                  onChange={(e) => setEditDateTime(e.target.value)}
                  className="input w-full"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-[#74736D] mb-1">Venue / Location</label>
                <input
                  type="text"
                  value={editVenue}
                  onChange={(e) => setEditVenue(e.target.value)}
                  className="input w-full"
                  placeholder="e.g. Science Complex Hall 2"
                />
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={handleSaveEdit}
                  disabled={isSubmitting}
                  className="flex-1 min-h-[48px] rounded-xl bg-[#FF5A36] hover:bg-[#E04826] text-white text-xs font-bold flex items-center justify-center gap-1.5 shadow-sm transition-all"
                >
                  <Save className="w-4 h-4" /> Save Changes
                </button>
                <button
                  type="button"
                  onClick={() => setIsEditing(false)}
                  disabled={isSubmitting}
                  className="min-h-[48px] px-4 rounded-xl bg-[#F4F3EF] hover:bg-[#E9E9E6] text-[#74736D] text-xs font-bold transition-all"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}