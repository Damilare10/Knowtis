/*
WhatsApp Groups Page - Modernized Network Control Panel & Selective Keyword/Subject Monitor
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
  AlertTriangle,
  SlidersHorizontal,
  Filter,
  Plus,
  Tag,
  BookOpen,
  Check,
  Zap
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { formatDateShort } from '@/lib/datetime';

export default function GroupsPage() {
  const { 
    groups, 
    fetchGroups, 
    joinGroup, 
    unlinkGroup,
    updateGroupFilters, 
    loading, 
    error, 
    clearError,
    user
  } = useAppStore();

  const [inviteLink, setInviteLink] = useState('');
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [groupToUnlink, setGroupToUnlink] = useState<{ id: string; name: string } | null>(null);

  // Filter Modal State
  const [activeFilterGroup, setActiveFilterGroup] = useState<any | null>(null);
  const [filterMode, setFilterMode] = useState<'ALL' | 'FILTERED'>('ALL');
  const [monitoredCourses, setMonitoredCourses] = useState<string[]>([]);
  const [monitoredKeywords, setMonitoredKeywords] = useState<string[]>([]);
  const [courseInput, setCourseInput] = useState('');
  const [keywordInput, setKeywordInput] = useState('');
  const [isSavingFilters, setIsSavingFilters] = useState(false);

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

  const openFilterModal = (group: any) => {
    setActiveFilterGroup(group);
    setFilterMode(group.filter_mode || 'ALL');
    setMonitoredCourses(group.monitored_courses || []);
    setMonitoredKeywords(group.monitored_keywords || []);
    setCourseInput('');
    setKeywordInput('');
  };

  const handleAddCourse = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const clean = courseInput.trim().toUpperCase().replace(/\s+/g, '');
    if (clean && !monitoredCourses.includes(clean)) {
      setMonitoredCourses([...monitoredCourses, clean]);
      setCourseInput('');
    }
  };

  const handleRemoveCourse = (course: string) => {
    setMonitoredCourses(monitoredCourses.filter((c) => c !== course));
  };

  const handleAddKeyword = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const clean = keywordInput.trim().toLowerCase();
    if (clean && !monitoredKeywords.includes(clean)) {
      setMonitoredKeywords([...monitoredKeywords, clean]);
      setKeywordInput('');
    }
  };

  const handleRemoveKeyword = (keyword: string) => {
    setMonitoredKeywords(monitoredKeywords.filter((k) => k !== keyword));
  };

  const handleSaveFilters = async () => {
    if (!activeFilterGroup) return;

    // Automatically flush any pending text typed in course or keyword inputs before saving
    let finalCourses = [...monitoredCourses];
    const cleanCourse = courseInput.trim().toUpperCase().replace(/\s+/g, '');
    if (cleanCourse && !finalCourses.includes(cleanCourse)) {
      finalCourses.push(cleanCourse);
      setMonitoredCourses(finalCourses);
      setCourseInput('');
    }

    let finalKeywords = [...monitoredKeywords];
    const cleanKeyword = keywordInput.trim().toLowerCase();
    if (cleanKeyword && !finalKeywords.includes(cleanKeyword)) {
      finalKeywords.push(cleanKeyword);
      setMonitoredKeywords(finalKeywords);
      setKeywordInput('');
    }

    setIsSavingFilters(true);
    const success = await updateGroupFilters(activeFilterGroup.id, {
      monitored_courses: finalCourses,
      monitored_keywords: finalKeywords,
      filter_mode: filterMode,
    });
    setIsSavingFilters(false);
    if (success) {
      setActiveFilterGroup(null);
    }
  };

  const getStatusColor = (state: string, isPending: boolean = false) => {
    if (isPending || state === 'RECOVERING') return 'bg-[var(--info-dim)] text-[var(--info)] border-[#D8DFFF]';
    switch (state) {
      case 'ACTIVE': return 'bg-[var(--success-dim)] text-[var(--success)] border-[#A7F3D0]';
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
          Link class chats so Knowtis can pull out deadlines, alerts, and selective course updates.
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
                    <button onClick={clearError} className="ml-2 underline font-bold cursor-pointer">Dismiss</button>
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
              Knowtis watches class chats for academic announcements only. You can configure subject & keyword filters per group below.
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
                {groups.map((group) => {
                  const isPending = group.group_jid?.startsWith('pending-') || group.coverage_state === 'RECOVERING';
                  const isFiltered = group.filter_mode === 'FILTERED' && ((group.monitored_courses?.length || 0) > 0 || (group.monitored_keywords?.length || 0) > 0);
                  const coursesCount = group.monitored_courses?.length || 0;
                  const keywordsCount = group.monitored_keywords?.length || 0;
                  const displayStatus = isPending ? 'CONNECTING' : group.coverage_state;

                  return (
                    <motion.div 
                      key={group.id}
                      variants={itemVariants}
                      className="clay-card p-5 flex flex-col justify-between hover:-translate-y-0.5 transition-all duration-200"
                    >
                      <div>
                        <div className="flex justify-between items-center gap-3 mb-3">
                          <h4 className="font-black text-sm tracking-[-0.01em] text-[var(--text-1)] truncate">
                            {group.group_name}
                          </h4>

                          <span className={`px-2.5 py-0.5 rounded-full border text-[9px] font-extrabold flex items-center gap-1 shrink-0 ${getStatusColor(group.coverage_state, isPending)}`}>
                            <span className={`w-1.5 h-1.5 rounded-full bg-current ${group.coverage_state === 'ACTIVE' || isPending ? 'animate-pulse' : ''}`} />
                            {displayStatus}
                          </span>
                        </div>

                        {/* Filter & Monitoring status badge */}
                        <div className="mb-3">
                          {isPending ? (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-[var(--info-dim)] text-[var(--info)] text-[10px] font-extrabold border border-[#D8DFFF]">
                              <Clock className="w-3 h-3 animate-spin text-[var(--info)]" />
                              Connecting to WhatsApp group...
                            </span>
                          ) : isFiltered ? (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-[var(--primary-dim)] text-[var(--primary)] text-[10px] font-black border border-[#FFD8CC]">
                              <Filter className="w-3 h-3" />
                              Mode: Selective Filters ({coursesCount > 0 && `${coursesCount} course${coursesCount > 1 ? 's' : ''}`} {coursesCount > 0 && keywordsCount > 0 && '•'} {keywordsCount > 0 && `${keywordsCount} keyword${keywordsCount > 1 ? 's' : ''}`})
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-[var(--success-dim)] text-[var(--success)] text-[10px] font-extrabold border border-[#CFEFDD]">
                              <Zap className="w-3 h-3 text-[var(--success)]" />
                              Mode: All Messages & Announcements
                            </span>
                          )}
                        </div>

                        <p className="text-[11px] text-[var(--text-3)] font-semibold mb-4 flex items-center gap-1.5">
                          <Clock className="w-3.5 h-3.5" />
                          Linked {formatDateShort(group.join_date, true)}
                        </p>
                      </div>

                      <div className="flex justify-between items-center pt-3 border-t border-[var(--border-soft)]">
                        <motion.button
                          whileHover={{ scale: 1.04 }}
                          whileTap={{ scale: 0.96 }}
                          onClick={() => openFilterModal(group)}
                          className="px-3.5 py-1.5 rounded-[12px] bg-[#F4F3EF] hover:bg-[#EAE8E3] text-[var(--text-1)] text-xs font-black flex items-center gap-1.5 cursor-pointer shadow-sm"
                        >
                          <SlidersHorizontal className="w-3.5 h-3.5 text-[var(--primary)]" />
                          Configure Filters
                        </motion.button>

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
                  );
                })}
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
              Selective Subject Filters
            </h4>
            <ul className="space-y-4 text-xs text-[var(--text-2)] leading-relaxed font-medium">
              <li className="flex gap-3">
                <span className="w-5 h-5 rounded-full bg-[var(--primary-dim)] text-[var(--primary)] text-[10px] font-extrabold flex items-center justify-center shrink-0">1</span>
                <span>Tap <strong>Filters & Keywords</strong> on any group card.</span>
              </li>
              <li className="flex gap-3">
                <span className="w-5 h-5 rounded-full bg-[var(--primary-dim)] text-[var(--primary)] text-[10px] font-extrabold flex items-center justify-center shrink-0">2</span>
                <span>Enter your specific course codes (e.g., <strong>MCE301</strong> for outstanding courses).</span>
              </li>
              <li className="flex gap-3">
                <span className="w-5 h-5 rounded-full bg-[var(--primary-dim)] text-[var(--primary)] text-[10px] font-extrabold flex items-center justify-center shrink-0">3</span>
                <span>Add alert keywords like <strong>outstanding</strong>, <strong>exam</strong>, or <strong>test</strong>.</span>
              </li>
              <li className="flex gap-3">
                <span className="w-5 h-5 rounded-full bg-[var(--primary-dim)] text-[var(--primary)] text-[10px] font-extrabold flex items-center justify-center shrink-0">4</span>
                <span>Knowtis filters out chatter for other courses you aren&apos;t taking!</span>
              </li>
            </ul>
          </motion.div>

          <motion.div 
            variants={itemVariants}
            className="clay-card p-6 flex gap-3.5"
          >
            <ShieldAlert className="w-5 h-5 text-[#F2A53C] shrink-0 mt-0.5" />
            <div className="space-y-1.5">
              <h5 className="font-bold text-xs text-[var(--text-1)] font-black">Outstanding Course & Multi-level Protection</h5>
              <p className="text-[11px] text-[var(--text-2)] leading-relaxed font-medium">
                Perfect for students taking outstanding courses in higher-level WhatsApp groups. Filter by exact course codes so you only receive alerts for your target subjects.
              </p>
            </div>
          </motion.div>
        </div>
      </div>

      {/* ── Group Keyword & Subject Filter Modal ── */}
      <AnimatePresence>
        {activeFilterGroup && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 overflow-y-auto"
          >
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/30 backdrop-blur-sm"
              onClick={() => setActiveFilterGroup(null)}
            />

            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 15 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 15 }}
              transition={{ type: 'spring', stiffness: 220, damping: 24 }}
              className="relative w-full max-w-lg clay-card-strong p-6 space-y-6 z-10 max-h-[90vh] overflow-y-auto"
            >
              {/* Close Button */}
              <button
                onClick={() => setActiveFilterGroup(null)}
                className="absolute top-4 right-4 p-2 rounded-full text-[var(--text-3)] hover:bg-[#F4F3EF] cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>

              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-[var(--primary-dim)] flex items-center justify-center shrink-0">
                  <SlidersHorizontal className="w-5 h-5 text-[var(--primary)]" />
                </div>
                <div>
                  <h3 className="text-base font-black text-[var(--text-1)] tracking-[-0.01em]">
                    Group Filter Settings
                  </h3>
                  <p className="text-xs text-[var(--text-3)] font-semibold">
                    {activeFilterGroup.group_name}
                  </p>
                </div>
              </div>

              {/* Filter Mode Selector */}
              <div className="space-y-2">
                <label className="text-xs font-black text-[var(--text-1)] uppercase tracking-wider block">
                  Monitoring Mode
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setFilterMode('ALL')}
                    className={`p-3 rounded-2xl border text-left flex flex-col gap-1 transition-all cursor-pointer ${
                      filterMode === 'ALL'
                        ? 'bg-[var(--primary-dim)] border-[var(--primary)] text-[var(--primary)] font-black'
                        : 'bg-[#F4F3EF] border-transparent text-[var(--text-2)] font-bold hover:bg-[#EAE8E3]'
                    }`}
                  >
                    <span className="text-xs flex items-center gap-1.5">
                      <Zap className="w-3.5 h-3.5" />
                      All Group Updates
                    </span>
                    <span className="text-[10px] opacity-80 font-normal">Receive all announcements & deadlines from this group.</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setFilterMode('FILTERED')}
                    className={`p-3 rounded-2xl border text-left flex flex-col gap-1 transition-all cursor-pointer ${
                      filterMode === 'FILTERED'
                        ? 'bg-[var(--primary-dim)] border-[var(--primary)] text-[var(--primary)] font-black'
                        : 'bg-[#F4F3EF] border-transparent text-[var(--text-2)] font-bold hover:bg-[#EAE8E3]'
                    }`}
                  >
                    <span className="text-xs flex items-center gap-1.5">
                      <Filter className="w-3.5 h-3.5" />
                      Selective Courses/Keywords
                    </span>
                    <span className="text-[10px] opacity-80 font-normal">Only alert me for my specific subjects or keywords.</span>
                  </button>
                </div>
              </div>

              {filterMode === 'FILTERED' && (
                <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} className="space-y-6">
                  {/* Monitored Courses Section */}
                  <div className="space-y-3 pt-2 border-t border-[var(--border-soft)]">
                    <label className="text-xs font-black text-[var(--text-1)] flex items-center justify-between">
                      <span className="flex items-center gap-1.5">
                        <BookOpen className="w-4 h-4 text-[var(--primary)]" />
                        Monitored Courses / Subjects
                      </span>
                      <span className="text-[10px] font-semibold text-[var(--text-3)]">e.g., MCE301, CVE201</span>
                    </label>

                    <form onSubmit={handleAddCourse} className="flex gap-2">
                      <input
                        type="text"
                        placeholder="Add course code (e.g. MCE301)"
                        value={courseInput}
                        onChange={(e) => setCourseInput(e.target.value)}
                        className="input text-xs flex-grow uppercase font-bold"
                      />
                      <button
                        type="submit"
                        onClick={handleAddCourse}
                        className="px-4 py-2 bg-[var(--primary)] text-white rounded-full text-xs font-extrabold hover:brightness-110 flex items-center gap-1 cursor-pointer"
                      >
                        <Plus className="w-3.5 h-3.5" /> Add
                      </button>
                    </form>

                    {/* Course tags */}
                    <div className="flex flex-wrap gap-2 min-h-[32px] p-2 bg-[#F4F3EF] rounded-2xl">
                      {monitoredCourses.length === 0 ? (
                        <p className="text-[11px] text-[var(--text-3)] font-medium p-1">No specific course codes added yet.</p>
                      ) : (
                        monitoredCourses.map((c) => (
                          <span key={c} className="inline-flex items-center gap-1.5 px-3 py-1 bg-white text-[var(--primary)] font-black text-xs rounded-full border border-[var(--border-soft)] shadow-sm">
                            {c}
                            <button type="button" onClick={() => handleRemoveCourse(c)} className="hover:text-[var(--danger)] cursor-pointer">
                              <X className="w-3 h-3" />
                            </button>
                          </span>
                        ))
                      )}
                    </div>
                  </div>

                  {/* Monitored Keywords Section */}
                  <div className="space-y-3 pt-2 border-t border-[var(--border-soft)]">
                    <label className="text-xs font-black text-[var(--text-1)] flex items-center justify-between">
                      <span className="flex items-center gap-1.5">
                        <Tag className="w-4 h-4 text-[var(--primary)]" />
                        Alert Keywords
                      </span>
                      <span className="text-[10px] font-semibold text-[var(--text-3)]">e.g., outstanding, exam, test</span>
                    </label>

                    <form onSubmit={handleAddKeyword} className="flex gap-2">
                      <input
                        type="text"
                        placeholder="Add keyword (e.g. outstanding, test)"
                        value={keywordInput}
                        onChange={(e) => setKeywordInput(e.target.value)}
                        className="input text-xs flex-grow font-semibold"
                      />
                      <button
                        type="submit"
                        onClick={handleAddKeyword}
                        className="px-4 py-2 bg-[#1E1E1E] text-white rounded-full text-xs font-extrabold hover:bg-[#292929] flex items-center gap-1 cursor-pointer"
                      >
                        <Plus className="w-3.5 h-3.5" /> Add
                      </button>
                    </form>

                    {/* Keyword tags */}
                    <div className="flex flex-wrap gap-2 min-h-[32px] p-2 bg-[#F4F3EF] rounded-2xl">
                      {monitoredKeywords.length === 0 ? (
                        <p className="text-[11px] text-[var(--text-3)] font-medium p-1">No alert keywords added yet.</p>
                      ) : (
                        monitoredKeywords.map((k) => (
                          <span key={k} className="inline-flex items-center gap-1.5 px-3 py-1 bg-white text-[var(--text-1)] font-bold text-xs rounded-full border border-[var(--border-soft)] shadow-sm">
                            #{k}
                            <button type="button" onClick={() => handleRemoveKeyword(k)} className="hover:text-[var(--danger)] cursor-pointer">
                              <X className="w-3 h-3" />
                            </button>
                          </span>
                        ))
                      )}
                    </div>
                  </div>
                </motion.div>
              )}

              {/* Action Footer */}
              <div className="flex gap-3 pt-3 border-t border-[var(--border-soft)]">
                <button
                  type="button"
                  onClick={() => setActiveFilterGroup(null)}
                  className="flex-1 px-4 py-3 rounded-full bg-[#F4F3EF] hover:bg-[#EDECEA] font-black text-xs text-[var(--text-2)] cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={isSavingFilters}
                  onClick={handleSaveFilters}
                  className="flex-1 px-4 py-3 rounded-full bg-[var(--primary)] text-white font-black text-xs hover:brightness-110 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
                >
                  {isSavingFilters ? <span className="skeleton-soft block h-3 w-16 rounded-full" /> : (
                    <>
                      <Check className="w-4 h-4" /> Save Filters
                    </>
                  )}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

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
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-black/20 backdrop-blur-sm"
              onClick={() => setGroupToUnlink(null)}
            />

            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              transition={{ type: 'spring', stiffness: 200, damping: 22 }}
              className="relative w-full max-w-sm clay-card-strong p-6 space-y-5 text-center"
            >
              <button
                onClick={() => setGroupToUnlink(null)}
                className="absolute top-3 right-3 w-8 h-8 flex items-center justify-center rounded-[12px] text-[var(--text-3)] hover:bg-[var(--danger-dim)] hover:text-[var(--danger)] cursor-pointer"
                aria-label="Cancel"
              >
                <X className="w-4 h-4" />
              </button>

              <div className="mx-auto w-14 h-14 rounded-[20px] bg-[var(--danger-dim)] flex items-center justify-center">
                <AlertTriangle className="w-7 h-7 text-[var(--danger)]" />
              </div>

              <div>
                <h3 className="text-base font-black text-[var(--text-1)] tracking-[-0.01em]">
                  Unlink group?
                </h3>
                <p className="text-xs text-[var(--text-2)] font-medium mt-2 leading-relaxed">
                  The bot will leave <strong className="font-black text-[var(--text-1)]">{groupToUnlink.name}</strong> and stop monitoring it. You can re-link it later anytime.
                </p>
              </div>

              <div className="flex gap-2.5">
                <button
                  onClick={() => setGroupToUnlink(null)}
                  className="flex-1 px-4 py-3 rounded-full bg-[#F4F3EF] hover:bg-[#EDECEA] font-black text-xs text-[var(--text-2)] cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  onClick={() => {
                    unlinkGroup(groupToUnlink.id);
                    setGroupToUnlink(null);
                  }}
                  className="flex-1 px-4 py-3 rounded-full bg-[var(--danger)] text-white hover:brightness-110 font-black text-xs cursor-pointer"
                >
                  Yes, unlink
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
