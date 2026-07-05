/*
WhatsApp Groups Page - Modernized Network Control Panel & Stats
*/
'use client';

import React, { useState, useEffect } from 'react';
import { useAppStore } from '@/lib/store';
import {
  Link2,
  Trash2,
  WifiOff,
  RefreshCw,
  ShieldAlert,
  HelpCircle,
  Clock,
  X,
  AlertTriangle
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { formatDateShort } from '@/lib/datetime';

export default function GroupsPage() {
  const { 
    groups, 
    fetchGroups, 
    joinGroup, 
    unlinkGroup, 
    loading, 
    error, 
    clearError,
    user
  } = useAppStore();

  const [inviteLink, setInviteLink] = useState('');
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [groupToUnlink, setGroupToUnlink] = useState<{ id: string; name: string } | null>(null);

  useEffect(() => {
    fetchGroups();
  }, [fetchGroups]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteLink) return;
    setSuccessMsg(null);

    if (user?.tier === 'free' && groups.length >= 2) {
      setSuccessMsg("Free accounts can link 2 class chats. Upgrade when you need more.");
      return;
    }

    const success = await joinGroup(inviteLink);
    if (success) {
      setSuccessMsg("Invite received. Knowtis will connect to the chat shortly.");
      setInviteLink('');
      setTimeout(() => setSuccessMsg(null), 5000);
    }
  };

  const getStatusColor = (state: string) => {
    switch (state) {
      case 'ACTIVE': return 'bg-[var(--success-dim)] text-[var(--success)] border-[#A7F3D0]';
      case 'RECOVERING': return 'bg-[var(--info-dim)] text-[var(--info)] border-[#D8DFFF]';
      case 'DEGRADED': return 'bg-[var(--warning-dim)] text-[var(--warning)] border-[#F8E1AF]';
      default: return 'bg-[#F4F3EF] text-[var(--text-2)] border-[#E9E9E6]';
    }
  };

  const containerVariants = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { staggerChildren: 0.06 } }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 14 },
    show: { opacity: 1, y: 0, transition: { type: 'spring' as const, stiffness: 100, damping: 16 } }
  };

  return (
    <motion.div 
      variants={containerVariants}
      initial="hidden"
      animate="show"
      className="app-page max-w-7xl"
    >
      <motion.div variants={itemVariants}>
        <h1 className="page-title">
          WhatsApp <span className="orange-highlight">monitor</span>
        </h1>
        <p className="page-copy mt-2">
          Link class chats so Knowtis can pull out deadlines, alerts, and schedule changes.
        </p>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-8">
          <motion.div 
            variants={itemVariants}
            className="clay-card-strong p-6 space-y-5 relative overflow-hidden"
          >
            <div className="absolute top-0 right-0 w-24 h-24 bg-[#FFF0EB] rounded-full blur-xl" />
            
            <h3 className="font-black text-sm tracking-[-0.01em] text-[var(--text-1)] flex items-center gap-2.5">
              <div className="w-9 h-9 clay-icon bg-[var(--primary-dim)] flex items-center justify-center">
                <Link2 className="w-4 h-4 text-[var(--primary)]" />
              </div>
              Link a class chat
            </h3>
            
            {(error || successMsg) && (
              <AnimatePresence>
                {error && (
                  <motion.div 
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="p-4 bg-[var(--danger-dim)] border border-[#FECACA] rounded-2xl text-xs font-semibold text-[var(--danger)]"
                  >
                    {error}
                    <button onClick={clearError} className="ml-2 underline font-bold">Dismiss</button>
                  </motion.div>
                )}
                {successMsg && (
                  <motion.div
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="p-4 bg-[var(--success-dim)] border border-[#CFEFDD] rounded-2xl text-xs font-semibold text-[var(--success)]"
                  >
                    {successMsg}
                  </motion.div>
                )}
              </AnimatePresence>
            )}

            <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3">
              <input
                type="text"
                aria-label="WhatsApp group invite link"
                required
                placeholder="Paste WhatsApp Group Invite Link (https://chat.whatsapp.com/...)"
                value={inviteLink}
                onChange={(e) => setInviteLink(e.target.value)}
                className="input flex-grow font-semibold placeholder:text-[var(--text-3)]"
              />
              <motion.button
                whileHover={{ scale: 1.02, boxShadow: '0 22px 44px rgba(30,30,30,0.20)' }}
                whileTap={{ scale: 0.97, boxShadow: '0 8px 20px rgba(30,30,30,0.12)' }}
                transition={{ type: 'spring', stiffness: 400, damping: 20 }}
                type="submit"
                disabled={loading}
                className="px-6 py-3.5 rounded-full bg-[#1E1E1E] text-white hover:bg-[#292929] font-black text-sm shadow-[0_18px_36px_rgba(30,30,30,0.16)] disabled:opacity-50 cursor-pointer"
              >
                 {loading ? <span className="skeleton-soft block h-3 w-16 rounded-full" /> : 'Link chat'}
              </motion.button>
            </form>
            
            <p className="text-[11px] text-[var(--text-3)] font-medium leading-relaxed">
              Knowtis watches the class chat for school-related updates only. Repeated messages are grouped automatically.
            </p>
          </motion.div>

          <div className="space-y-4">
            <div className="flex justify-between items-center">
                <h3 className="font-black text-sm tracking-[-0.01em] text-[var(--text-1)] flex items-center gap-2.5">
                Linked chats ({groups.length})
              </h3>
              <motion.button 
                whileHover={{ scale: 1.08, rotate: 180 }}
                whileTap={{ scale: 0.92 }}
                transition={{ type: 'spring', stiffness: 300, damping: 15 }}
                onClick={() => fetchGroups()}
                aria-label="Refresh linked chats"
                className="p-2 rounded-[14px] text-[var(--text-3)] hover:bg-white hover:text-[var(--text-1)] border border-transparent hover:border-[var(--border)] cursor-pointer"
              >
                <RefreshCw className="w-4 h-4" />
              </motion.button>
            </div>

            {groups.length === 0 ? (
              <motion.div 
                variants={itemVariants}
                className="clay-card-strong p-16 text-center text-[var(--text-3)] text-sm flex flex-col items-center justify-center"
              >
                <div className="w-16 h-16 rounded-[20px] clay-icon bg-[#F4F3EF] flex items-center justify-center mb-4">
                  <WifiOff className="w-7 h-7 text-[var(--text-3)]" />
                </div>
                <p className="font-bold text-[var(--text-2)]">No chats linked yet</p>
                <p className="body-sm text-[var(--text-3)] mt-1">Paste an invite link above to start.</p>
              </motion.div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {groups.map((group) => (
                  <motion.div 
                    key={group.id}
                    variants={itemVariants}
                    className="clay-card p-5 flex flex-col justify-between hover:-translate-y-0.5 transition-all duration-200"
                  >
                    <div>
                      <div className="flex justify-between items-center gap-3 mb-4">
                        <h4 className="font-black text-sm tracking-[-0.01em] text-[var(--text-1)] truncate">
                          {group.group_name}
                        </h4>

                        <span className={`px-2.5 py-0.5 rounded-full border text-[9px] font-extrabold flex items-center gap-1 shrink-0 ${getStatusColor(group.coverage_state)}`}>
                          <span className={`w-1.5 h-1.5 rounded-full bg-current ${group.coverage_state === 'ACTIVE' || group.coverage_state === 'RECOVERING' ? 'animate-pulse' : ''}`} />
                          {group.coverage_state}
                        </span>
                      </div>

                      <p className="text-[11px] text-[var(--text-3)] font-semibold mb-4 flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5" />
                        Linked {formatDateShort(group.join_date, true)}
                      </p>
                    </div>

                    <div className="flex justify-end items-center pt-3 border-t border-[var(--border-soft)]">
                      <motion.button
                        whileHover={{ scale: 1.1, backgroundColor: 'var(--danger-dim)', color: 'var(--danger)' }}
                        whileTap={{ scale: 0.9 }}
                        transition={{ type: 'spring', stiffness: 400, damping: 18 }}
                        onClick={() => setGroupToUnlink({ id: group.id, name: group.group_name })}
                        aria-label={`Unlink ${group.group_name}`}
                        className="p-2 rounded-[14px] text-[var(--text-3)] cursor-pointer"
                        title="Unlink Group"
                      >
                        <Trash2 className="w-4 h-4" />
                      </motion.button>
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="space-y-6">
          <motion.div 
            variants={itemVariants}
            className="clay-card p-6 space-y-5"
          >
            <h4 className="font-black text-sm tracking-[-0.01em] text-[var(--text-1)] flex items-center gap-2.5">
              <div className="w-9 h-9 clay-icon bg-[var(--primary-dim)] flex items-center justify-center">
                <HelpCircle className="w-4 h-4 text-[var(--primary)]" />
              </div>
              Listener Pipeline
            </h4>
            <ul className="space-y-4 text-xs text-[var(--text-2)] leading-relaxed font-medium">
              <li className="flex gap-3">
                <span className="w-5 h-5 rounded-full bg-[var(--primary-dim)] text-[var(--primary)] text-[10px] font-extrabold flex items-center justify-center shrink-0">1</span>
                <span>Copy the WhatsApp group invite link from your group settings.</span>
              </li>
              <li className="flex gap-3">
                <span className="w-5 h-5 rounded-full bg-[var(--primary-dim)] text-[var(--primary)] text-[10px] font-extrabold flex items-center justify-center shrink-0">2</span>
                  <span>Paste it here and tap Link chat.</span>
              </li>
              <li className="flex gap-3">
                <span className="w-5 h-5 rounded-full bg-[var(--primary-dim)] text-[var(--primary)] text-[10px] font-extrabold flex items-center justify-center shrink-0">3</span>
                  <span>Knowtis starts watching for deadline and schedule messages.</span>
              </li>
              <li className="flex gap-3">
                <span className="w-5 h-5 rounded-full bg-[var(--primary-dim)] text-[var(--primary)] text-[10px] font-extrabold flex items-center justify-center shrink-0">4</span>
                  <span>Useful updates appear in your feed, calendar, and reminders.</span>
              </li>
            </ul>
          </motion.div>

          <motion.div 
            variants={itemVariants}
            className="clay-card p-6 flex gap-3.5"
          >
            <ShieldAlert className="w-5 h-5 text-[#F2A53C] shrink-0 mt-0.5" />
            <div className="space-y-1.5">
              <h5 className="font-bold text-xs text-[var(--text-1)]">Safe joining</h5>
              <p className="text-[11px] text-[var(--text-2)] leading-relaxed font-medium">
                New chats may take a short moment to connect. Knowtis avoids private messages and only keeps school-related updates.
              </p>
            </div>
          </motion.div>
        </div>
      </div>

      {/* ── Delete confirmation modal ── */}
      <AnimatePresence>
        {groupToUnlink && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
          >
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-black/20 backdrop-blur-sm"
              onClick={() => setGroupToUnlink(null)}
            />

            {/* Modal card */}
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              transition={{ type: 'spring', stiffness: 200, damping: 22 }}
              className="relative w-full max-w-sm clay-card-strong p-6 space-y-5 text-center"
            >
              {/* Close button */}
              <motion.button
                whileHover={{ scale: 1.1, rotate: 90 }}
                whileTap={{ scale: 0.9 }}
                transition={{ type: 'spring', stiffness: 400, damping: 18 }}
                onClick={() => setGroupToUnlink(null)}
                className="absolute top-3 right-3 w-8 h-8 flex items-center justify-center rounded-[12px] text-[var(--text-3)] hover:bg-[var(--danger-dim)] hover:text-[var(--danger)] cursor-pointer"
                aria-label="Cancel"
              >
                <X className="w-4 h-4" />
              </motion.button>

              {/* Icon */}
              <div className="mx-auto w-14 h-14 rounded-[20px] bg-[var(--danger-dim)] flex items-center justify-center">
                <AlertTriangle className="w-7 h-7 text-[var(--danger)]" />
              </div>

              {/* Text */}
              <div>
                <h3 className="text-base font-black text-[var(--text-1)] tracking-[-0.01em]">
                  Unlink group?
                </h3>
                <p className="text-xs text-[var(--text-2)] font-medium mt-2 leading-relaxed">
                  The bot will leave <strong className="font-black text-[var(--text-1)]">{groupToUnlink.name}</strong> and stop monitoring it. You can re-link it later anytime.
                </p>
              </div>

              {/* Actions */}
              <div className="flex gap-2.5">
                <motion.button
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.96 }}
                  transition={{ type: 'spring', stiffness: 400, damping: 20 }}
                  onClick={() => setGroupToUnlink(null)}
                  className="flex-1 px-4 py-3 rounded-full bg-[#F4F3EF] hover:bg-[#EDECEA] font-black text-xs text-[var(--text-2)] cursor-pointer"
                >
                  Cancel
                </motion.button>
                <motion.button
                  whileHover={{ scale: 1.03, filter: 'brightness(1.1)' }}
                  whileTap={{ scale: 0.96 }}
                  transition={{ type: 'spring', stiffness: 400, damping: 20 }}
                  onClick={() => {
                    unlinkGroup(groupToUnlink.id);
                    setGroupToUnlink(null);
                  }}
                  className="flex-1 px-4 py-3 rounded-full bg-[var(--danger)] text-white hover:brightness-110 font-black text-xs cursor-pointer"
                >
                  Yes, unlink
                </motion.button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
