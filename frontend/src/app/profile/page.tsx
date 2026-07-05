'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '@/lib/store';
import ProfileAvatar from '@/components/profile-avatar';
import {
  Moon, ChevronRight,
  Smartphone, LogOut, Edit3, Settings,
  ArrowLeft, Check, Camera, HelpCircle, MessageSquare,
  Star, Trash2, ShieldAlert, Sparkles, Calendar,
  X, Eye, EyeOff, Phone
} from 'lucide-react';
import AndroidWidgetPreview from '@/components/dashboard/android-widget-preview';

type ViewState = 'default' | 'edit_profile' | 'subscription' | 'quiet_hours' | 'settings' | 'widget';

interface QuietHoursConfig {
  enableQuietHours: boolean;
  quietFrom: string;
  quietTo: string;
  quietDays: string[];
  allowHighPriority: boolean;
  weekendQuiet: boolean;
}

function loadQuietHours(): Partial<QuietHoursConfig> {
  if (typeof window === 'undefined') return {};
  const saved = localStorage.getItem('knowtis_quiet_hours');
  if (!saved) return {};
  try {
    return JSON.parse(saved) as Partial<QuietHoursConfig>;
  } catch {
    return {};
  }
}

function dimFor(color: string): string {
  switch (color) {
    case 'var(--primary)': return 'var(--primary-dim)';
    case 'var(--success)': return 'var(--success-dim)';
    case 'var(--info)': return 'var(--info-dim)';
    case 'var(--warning)': return 'var(--warning-dim)';
    default: return color + '18';
  }
}

interface SettingsRowProps {
  icon: React.ElementType;
  label: string;
  value?: string;
  color?: string;
  onClick?: () => void;
  badge?: string;
  danger?: boolean;
}

interface PlanFeature {
  label: string;
  free: boolean;
  pro: boolean;
  freeNote?: string;
  proNote?: string;
}

const PLAN_FEATURES: PlanFeature[] = [
  { label: 'WhatsApp group monitoring', free: true, pro: true, freeNote: 'Up to 2 groups', proNote: 'Unlimited' },
  { label: 'AI catch-up assistant (Groq)', free: true, pro: true, freeNote: '10k token cap', proNote: 'Unlimited' },
  { label: 'Daily AI Brief summary', free: true, pro: true },
  { label: 'Confidence-level classification', free: true, pro: true },
  { label: 'Basic text notifications', free: true, pro: true },
  { label: 'Real-time push alerts & custom alarms', free: false, pro: true },
  { label: 'Google & Outlook Calendar sync', free: false, pro: true },
  { label: 'Smart photo scanning for timetables & PDFs', free: false, pro: true },
];

function FeatureRow({ feature, tier }: { feature: PlanFeature; tier: 'free' | 'pro' }) {
  const included = tier === 'free' ? feature.free : feature.pro;
  const note = tier === 'free' ? feature.freeNote : feature.proNote;
  const accent = tier === 'pro' ? 'var(--primary)' : 'var(--success)';
  return (
    <li className="flex items-center gap-2">
      {included ? (
        <Check className="w-4 h-4 shrink-0" style={{ color: accent }} />
      ) : (
        <X className="w-4 h-4 shrink-0 text-[var(--text-3)]/40" />
      )}
      <span className={included ? '' : 'text-[var(--text-3)] line-through decoration-[var(--text-3)]/30'}>
        {feature.label}
      </span>
      {included && note && (
        <span className="text-[10px] font-black uppercase tracking-wider text-[var(--text-3)]">({note})</span>
      )}
    </li>
  );
}

function SettingsRow({ icon: Icon, label, value, color = 'var(--primary)', onClick, badge, danger }: SettingsRowProps) {
  const dim = danger ? 'var(--danger-dim)' : dimFor(color);
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-4 py-3.5 hover:bg-[#FBFBFA]/60 active:bg-[#FBFBFA] transition-colors text-left ${danger ? 'text-[var(--danger)]' : ''}`}
    >
      <div className="w-9 h-9 clay-icon flex items-center justify-center shrink-0 rounded-[18px]" style={{ background: dim }}>
        <Icon className="w-[18px] h-[18px]" style={{ color: danger ? 'var(--danger)' : color }} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className={`text-sm font-semibold ${danger ? 'text-[var(--danger)]' : 'text-[var(--text-1)]'}`}>{label}</p>
          {badge && (
            <span className="text-[10px] font-black uppercase tracking-wider px-1.5 py-0.5 rounded-md bg-[var(--primary-dim)] text-[var(--primary)] border border-[var(--primary-mid)]">
              {badge}
            </span>
          )}
        </div>
        {value && <p className="text-xs text-[var(--text-3)] font-medium mt-0.5 truncate">{value}</p>}
      </div>
      <ChevronRight className={`w-4 h-4 shrink-0 ${danger ? 'text-[var(--danger)]/50' : 'text-[var(--text-3)]'}`} />
    </button>
  );
}

export default function ProfilePage() {
  const router = useRouter();
  const {
    user, logout, updateProfile, deleteAccount, upgradeToPremium,
    loading, error, clearError, clearAIChat, aiClearing,
    activeSubscription, fetchActiveSubscription,
    widgetData, fetchWidgetData,
  } = useAppStore();

  React.useEffect(() => {
    fetchActiveSubscription();
    fetchWidgetData();
  }, [fetchActiveSubscription, fetchWidgetData]);

  const [activeView, setActiveView] = useState<ViewState>('default');

  // Modals
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [showSuccessToast, setShowSuccessToast] = useState<string | null>(null);
  const [showConnectWhatsApp, setShowConnectWhatsApp] = useState(false);
  const [connectNumber, setConnectNumber] = useState('');
  const [connecting, setConnecting] = useState(false);

  // Edit Profile States
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [whatsappNumber, setWhatsappNumber] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  // Quiet Hours States (persisted locally — hydrated once via lazy initializer)
  const stored = loadQuietHours();
  const [enableQuietHours, setEnableQuietHours] = useState(stored.enableQuietHours ?? true);
  const [quietFrom, setQuietFrom] = useState(stored.quietFrom ?? '22:00');
  const [quietTo, setQuietTo] = useState(stored.quietTo ?? '07:00');
  const [quietDays, setQuietDays] = useState<string[]>(stored.quietDays ?? ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']);
  const [allowHighPriority, setAllowHighPriority] = useState(stored.allowHighPriority ?? true);
  const [weekendQuiet, setWeekendQuiet] = useState(stored.weekendQuiet ?? false);

  // Subscription States
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly');

  const openEditProfile = () => {
    setFullName(user?.full_name ?? '');
    setEmail(user?.email ?? '');
    setWhatsappNumber(user?.whatsapp_number ?? '');
    setPassword('');
    setActiveView('edit_profile');
  };

  // Save quiet hours to localStorage
  const saveQuietHours = (updatedData?: Partial<QuietHoursConfig>) => {
    const data: QuietHoursConfig = {
      enableQuietHours,
      quietFrom,
      quietTo,
      quietDays,
      allowHighPriority,
      weekendQuiet,
      ...updatedData,
    };
    localStorage.setItem('knowtis_quiet_hours', JSON.stringify(data));
    triggerToast('Quiet hours preferences updated!');
  };

  const triggerToast = (msg: string) => {
    setShowSuccessToast(msg);
    setTimeout(() => setShowSuccessToast(null), 3000);
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    const success = await updateProfile({
      full_name: fullName,
      email: email,
      whatsapp_number: whatsappNumber,
      password: password || undefined,
    });
    if (success) {
      setPassword('');
      triggerToast('Profile updated successfully!');
      setActiveView('default');
    }
  };

  const handleUpgrade = async (tier: 'free' | 'premium') => {
    const success = await upgradeToPremium(tier);
    if (success) {
      triggerToast(tier === 'premium' ? 'Successfully upgraded to Knowtis Pro!' : 'Downgraded to Free plan.');
      setActiveView('default');
    }
  };

  const handleDeleteAccount = async () => {
    const success = await deleteAccount();
    if (success) {
      setShowDeleteConfirm(false);
      // logout/redirect is handled by store
    }
  };

  const handleClearAIChat = async () => {
    setShowClearConfirm(false);
    const success = await clearAIChat();
    if (success) triggerToast('AI chat cleared.');
  };

  const isWhatsAppConnected = !!user?.whatsapp_number;

  const openConnectWhatsApp = () => {
    setConnectNumber(user?.whatsapp_number ?? '');
    clearError();
    setShowConnectWhatsApp(true);
  };

  const handleConnectWhatsApp = async (e: React.FormEvent) => {
    e.preventDefault();
    setConnecting(true);
    const success = await updateProfile({
      full_name: user?.full_name ?? '',
      email: user?.email ?? '',
      whatsapp_number: connectNumber,
    });
    setConnecting(false);
    if (success) {
      setShowConnectWhatsApp(false);
      triggerToast('WhatsApp connected successfully!');
    }
  };

  const name = user?.full_name ?? 'Student';
  const userEmail = user?.email ?? 'dev@example.com';
  const isPremium = user?.tier === 'premium';

  return (
    <div className="app-page relative">
      {/* Toast Alert */}
      <AnimatePresence>
        {showSuccessToast && (
          <motion.div
            initial={{ opacity: 0, y: -20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -20, scale: 0.95 }}
            className="fixed top-4 left-1/2 -translate-x-1/2 z-50 bg-[#171717] text-white text-xs font-bold px-4 py-3 rounded-full shadow-lg flex items-center gap-2 border border-white/10"
          >
            <Check className="w-3.5 h-3.5 text-[var(--success)]" />
            {showSuccessToast}
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence mode="wait">
        {/* ── 1. DEFAULT PROFILE VIEW ── */}
        {activeView === 'default' && (
          <motion.div
            key="default"
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -15 }}
            transition={{ duration: 0.25 }}
            className="space-y-5"
          >
            <div className="flex items-center justify-between">
              <div>
                <h1 className="page-title">My <span className="orange-highlight">Profile</span></h1>
                <p className="page-copy mt-1.5">Manage your identity, settings, and notifications.</p>
              </div>
              <button
                onClick={() => setActiveView('settings')}
                className="w-10 h-10 rounded-[18px] bg-white border border-[var(--border)] flex items-center justify-center shadow-sm hover:bg-[var(--surface-2)] transition-all active:scale-95"
              >
                <Settings className="w-[18px] h-[18px] text-[var(--text-2)]" />
              </button>
            </div>

            {/* Profile Avatar Card */}
            <div className="clay-card-strong p-5 flex items-center gap-4 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-32 h-32 bg-[var(--primary)]/5 rounded-full blur-3xl pointer-events-none" />
              <div className="relative">
                <div className="h-16 w-16 overflow-hidden rounded-[22px] bg-[#D9F1EC] shadow-sm border border-white">
                  <ProfileAvatar name={name} email={userEmail} className="h-full w-full object-cover" />
                </div>
                <div className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full bg-[var(--success)] border-2 border-white flex items-center justify-center">
                  <div className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
                </div>
              </div>
              <div className="flex-1 min-w-0">
                <h2 className="text-[22px] font-black tracking-[-0.03em] text-[var(--text-1)] truncate">{name}</h2>
                <p className="text-xs text-[var(--text-3)] font-semibold mt-0.5 truncate">{userEmail}</p>
                <div className="flex items-center gap-1.5 mt-2">
                  <span className={`badge ${isPremium ? 'badge-primary' : 'badge-neutral'}`}>
                    {isPremium ? 'Pro Member' : 'Free Account'}
                  </span>
                </div>
              </div>
              <button
                onClick={openEditProfile}
                className="w-9 h-9 rounded-[18px] bg-[var(--surface-2)] hover:bg-white border border-[var(--border)] flex items-center justify-center shrink-0 transition-all hover:shadow-sm active:scale-95"
              >
                <Edit3 className="w-4 h-4 text-[var(--text-2)]" />
              </button>
            </div>

            {/* Upgrade Banner (if Free) */}
            {!isPremium && (
              <motion.div
                whileHover={{ y: -2 }}
                onClick={() => setActiveView('subscription')}
                className="relative overflow-hidden rounded-[24px] bg-gradient-to-br from-[#171717] to-[#2a2a2a] p-5 text-white shadow-[0_18px_40px_rgba(30,30,30,0.18)] cursor-pointer group"
              >
                <div className="absolute -right-4 -bottom-4 w-24 h-24 bg-[var(--primary)]/20 rounded-full blur-xl group-hover:scale-125 transition-transform duration-500" />
                <div className="flex items-center justify-between relative z-10">
                  <div className="space-y-1">
                    <div className="flex items-center gap-1.5">
                      <Sparkles className="w-4 h-4 text-[var(--primary)]" />
                      <span className="text-xs font-black uppercase tracking-widest text-white/70">Upgrade to Pro</span>
                    </div>
                    <p className="text-base font-black tracking-tight mt-1">Unlock unlimited groups, calendar sync & smart photo scanning</p>
                  </div>
                  <div className="w-10 h-10 rounded-full bg-[var(--primary)]/20 backdrop-blur-md flex items-center justify-center shrink-0 group-hover:bg-[var(--primary)]/30 transition-colors">
                    <ChevronRight className="w-5 h-5 text-white" />
                  </div>
                </div>
              </motion.div>
            )}

            {/* Settings Sections */}
            <div className="space-y-4 lg:grid lg:grid-cols-2 lg:gap-4 lg:space-y-0">
              <div>
                <p className="text-[11px] font-black uppercase tracking-wider text-[var(--text-3)] mb-2 px-1">Settings & Preferences</p>
                <div className="clay-card overflow-hidden divide-y divide-[var(--border-soft)]">
                  <SettingsRow
                    icon={Edit3}
                    label="Edit Profile"
                    value="Update name, email, and password"
                    color="var(--primary)"
                    onClick={openEditProfile}
                  />
                  <SettingsRow
                    icon={Star}
                    label="Subscription Plan"
                    value={
                      isPremium
                        ? activeSubscription?.price
                          ? `You are on Knowtis Pro ($4.99/mo • paid ₦${activeSubscription.price.toLocaleString()}/mo)`
                          : "You are on Knowtis Pro ($4.99/mo)"
                        : "Free tier - limited to 2 groups"
                    }
                    color="var(--warning)"
                    badge={isPremium ? "Pro" : "Free"}
                    onClick={() => setActiveView('subscription')}
                  />
                  <SettingsRow
                    icon={Moon}
                    label="Quiet Hours"
                    value={enableQuietHours ? `Reminders muted ${quietFrom} - ${quietTo}` : "Disabled"}
                    color="var(--primary)"
                    onClick={() => setActiveView('quiet_hours')}
                  />
                </div>
              </div>

              <div>
                <p className="text-[11px] font-black uppercase tracking-wider text-[var(--text-3)] mb-2 px-1">Integrations & System</p>
                <div className="clay-card overflow-hidden divide-y divide-[var(--border-soft)]">
                  <SettingsRow
                    icon={MessageSquare}
                    label="Connect WhatsApp"
                    value={isWhatsAppConnected ? "Connected" : "Link a class chat to monitor"}
                    color="var(--success)"
                    badge={isWhatsAppConnected ? "Connected" : undefined}
                    onClick={openConnectWhatsApp}
                  />
                  <SettingsRow
                    icon={Smartphone}
                    label="Connected WhatsApp Groups"
                    value="Manage group coverage & links"
                    color="var(--success)"
                    onClick={() => router.push('/groups')}
                  />
                  <SettingsRow
                    icon={Calendar}
                    label="Calendar Sync"
                    value={isPremium ? "Google & Outlook calendar active" : "Premium feature"}
                    color="var(--info)"
                    onClick={() => router.push('/calendar')}
                  />
                  <SettingsRow
                    icon={Smartphone}
                    label="Android Widget Preview"
                    value="Configure and preview your home screen widget"
                    color="var(--primary)"
                    onClick={() => setActiveView('widget')}
                  />
                </div>
              </div>

              {/* Log Out */}
              <div className="pt-2">
                <button
                  onClick={() => setShowLogoutConfirm(true)}
                  className="w-full flex items-center gap-3 px-4 py-4 rounded-[22px] bg-white border border-[var(--border)] hover:bg-[var(--danger-dim)] hover:border-[var(--danger)]/20 transition-all text-left group shadow-sm active:scale-[0.99]"
                >
                  <div className="w-9 h-9 rounded-[18px] bg-[var(--danger-dim)] flex items-center justify-center shrink-0 transition-colors group-hover:bg-[var(--danger)]">
                    <LogOut className="w-[18px] h-[18px] text-[var(--danger)] group-hover:text-white transition-colors" />
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-bold text-[var(--danger)]">Sign Out</p>
                    <p className="text-xs text-[var(--text-3)] font-semibold mt-0.5">Log out of your current session</p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-[var(--danger)]/40 group-hover:text-[var(--danger)]" />
                </button>
              </div>
            </div>

            <div className="pt-4 text-center">
              <p className="text-[10px] font-bold text-[var(--text-3)] uppercase tracking-widest">Knowtis v1.2 • Premium Edition</p>
            </div>
          </motion.div>
        )}

        {/* ── 2. EDIT PROFILE VIEW ── */}
        {activeView === 'edit_profile' && (
          <motion.div
            key="edit_profile"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.25 }}
            className="space-y-5"
          >
            <div className="flex items-center justify-between">
              <button
                onClick={() => setActiveView('default')}
                className="w-9 h-9 rounded-[18px] bg-white border border-[var(--border)] flex items-center justify-center shrink-0 shadow-sm hover:bg-[var(--surface-2)] transition-all active:scale-95"
              >
                <ArrowLeft className="w-4 h-4 text-[var(--text-2)]" />
              </button>
              <h2 className="text-base font-black text-[var(--text-1)]">Edit Profile</h2>
              <button
                onClick={handleSaveProfile}
                disabled={loading}
                className="text-xs font-black uppercase tracking-wider text-[var(--primary)] hover:text-[var(--primary)]/80 disabled:text-[var(--text-3)]"
              >
                {loading ? 'Saving...' : 'Save'}
              </button>
            </div>

            <form onSubmit={handleSaveProfile} className="space-y-4">
              {/* Avatar Uploader UI */}
              <div className="flex flex-col items-center justify-center py-6">
                <div className="relative group cursor-pointer">
                  <div className="h-24 w-24 overflow-hidden rounded-[32px] bg-[#D9F1EC] border-2 border-white shadow-md">
                    <ProfileAvatar name={fullName || name} email={email || userEmail} className="h-full w-full object-cover" />
                  </div>
                  <div className="absolute inset-0 rounded-[32px] bg-black/45 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                    <Camera className="w-6 h-6 text-white" />
                  </div>
                </div>
                <p className="text-xs font-bold text-[var(--text-3)] mt-3">Click to upload custom picture</p>
              </div>

              {error && (
                <div className="p-3.5 rounded-[18px] bg-[var(--danger-dim)] text-[var(--danger)] text-xs font-semibold flex items-center gap-2 border border-[var(--danger)]/14">
                  <ShieldAlert className="w-4 h-4 shrink-0" />
                  {error}
                  <button type="button" onClick={clearError} className="ml-auto text-[var(--danger)]/60 hover:text-[var(--danger)]">
                    <X className="w-4 h-4" />
                  </button>
                </div>
              )}

              <div className="space-y-3.5">
                <div>
                  <label className="text-[11px] font-black uppercase tracking-wider text-[var(--text-3)] mb-1.5 block px-1">Full Name</label>
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className="w-full h-12 px-4 rounded-[18px] border border-[var(--border)] bg-white text-sm font-semibold text-[var(--text-1)] focus:border-[var(--primary)] focus:outline-none transition-all shadow-sm"
                    placeholder="Enter full name"
                  />
                </div>

                <div>
                  <label className="text-[11px] font-black uppercase tracking-wider text-[var(--text-3)] mb-1.5 block px-1">Email Address</label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full h-12 px-4 rounded-[18px] border border-[var(--border)] bg-white text-sm font-semibold text-[var(--text-1)] focus:border-[var(--primary)] focus:outline-none transition-all shadow-sm"
                    placeholder="Enter email address"
                  />
                </div>

                <div>
                  <label className="text-[11px] font-black uppercase tracking-wider text-[var(--text-3)] mb-1.5 block px-1">WhatsApp Phone Number (Optional)</label>
                  <input
                    type="text"
                    value={whatsappNumber}
                    onChange={(e) => setWhatsappNumber(e.target.value)}
                    className="w-full h-12 px-4 rounded-[18px] border border-[var(--border)] bg-white text-sm font-semibold text-[var(--text-1)] focus:border-[var(--primary)] focus:outline-none transition-all shadow-sm"
                    placeholder="e.g. +234 801 234 5678"
                  />
                  <p className="text-[10px] text-[var(--text-3)] font-semibold mt-1 px-1">Used to identify your account when tagging the bot in groups</p>
                </div>

                <div>
                  <label className="text-[11px] font-black uppercase tracking-wider text-[var(--text-3)] mb-1.5 block px-1">New Password (Optional)</label>
                  <div className="relative">
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="w-full h-12 pl-4 pr-12 rounded-[18px] border border-[var(--border)] bg-white text-sm font-semibold text-[var(--text-1)] focus:border-[var(--primary)] focus:outline-none transition-all shadow-sm"
                      placeholder="••••••••••••"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-4 top-4 text-[var(--text-3)] hover:text-[var(--text-1)] focus:outline-none"
                    >
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  <p className="text-[10px] text-[var(--text-3)] font-semibold mt-1 px-1">Leave empty to keep current password</p>
                </div>
              </div>

              <div className="pt-4">
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full h-12 rounded-full bg-[#171717] hover:bg-black active:scale-[0.99] text-white text-sm font-black tracking-[-0.01em] transition-all shadow-[0_18px_36px_rgba(30,30,30,0.16)] flex items-center justify-center"
                >
                  {loading ? 'Saving Changes...' : 'Save Profile Details'}
                </button>
              </div>
            </form>
          </motion.div>
        )}

        {/* ── 3. CHOOSE A PLAN (SUBSCRIPTION VIEW) ── */}
        {activeView === 'subscription' && (
          <motion.div
            key="subscription"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.25 }}
            className="space-y-5"
          >
            <div className="flex items-center justify-between">
              <button
                onClick={() => setActiveView('default')}
                className="w-9 h-9 rounded-[18px] bg-white border border-[var(--border)] flex items-center justify-center shrink-0 shadow-sm hover:bg-[var(--surface-2)] transition-all active:scale-95"
              >
                <ArrowLeft className="w-4 h-4 text-[var(--text-2)]" />
              </button>
              <h2 className="text-base font-black text-[var(--text-1)] mx-auto">Choose a plan</h2>
              <div className="w-9 h-9 opacity-0" />
            </div>

            {/* Toggle monthly / yearly */}
            <div className="flex justify-center">
              <div className="bg-[var(--surface-2)] p-1 rounded-full border border-[var(--border)] flex items-center gap-1 relative">
                <button
                  onClick={() => setBillingCycle('monthly')}
                  className={`px-4 py-2 text-xs font-black rounded-[14px] transition-all ${billingCycle === 'monthly' ? 'bg-white text-[var(--text-1)] shadow-sm' : 'text-[var(--text-3)]'}`}
                >
                  Monthly
                </button>
                <button
                  onClick={() => setBillingCycle('yearly')}
                  className={`px-4 py-2 text-xs font-black rounded-[14px] transition-all flex items-center gap-1.5 ${billingCycle === 'yearly' ? 'bg-white text-[var(--text-1)] shadow-sm' : 'text-[var(--text-3)]'}`}
                >
                  Yearly
                  <span className="text-[9px] font-black bg-[var(--primary-dim)] text-[var(--primary)] px-1 py-0.5 rounded uppercase">Save 17%</span>
                </button>
              </div>
            </div>

            {/* Plan cards */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Free Plan */}
              <div className={`clay-card p-5 border-2 transition-all ${!isPremium ? 'border-[var(--primary)]' : 'border-[var(--border)] opacity-85'}`}>
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="text-lg font-black text-[var(--text-1)]">Free Tier</h3>
                    <p className="text-xs text-[var(--text-3)] font-semibold mt-1">Always free for students</p>
                  </div>
                  <div className="text-right">
                    <span className="text-2xl font-black text-[var(--text-1)]">$0</span>
                    <span className="text-xs text-[var(--text-3)] font-bold">/mo</span>
                  </div>
                </div>

                <div className="my-4 border-t border-[var(--border-soft)]" />

                <ul className="space-y-2 text-xs font-semibold text-[var(--text-2)]">
                  {PLAN_FEATURES.map(f => <FeatureRow key={f.label} feature={f} tier="free" />)}
                </ul>

                {!isPremium ? (
                  <button
                    disabled
                    className="w-full h-11 mt-4 rounded-[14px] bg-[var(--surface-2)] text-[var(--text-3)] text-xs font-black uppercase border border-[var(--border)]"
                  >
                    Current Plan
                  </button>
                ) : (
                  <button
                    onClick={() => handleUpgrade('free')}
                    className="w-full h-11 mt-4 rounded-[14px] bg-white border border-[var(--border)] hover:bg-[var(--surface-2)] text-[var(--text-1)] text-xs font-black uppercase transition-all"
                  >
                    Downgrade to Free
                  </button>
                )}
              </div>

              {/* Pro Plan */}
              <div className={`clay-card p-5 border-2 transition-all relative overflow-hidden bg-gradient-to-b from-white to-[var(--primary-dim)]/40 ${isPremium ? 'border-[var(--primary)] shadow-md' : 'border-[var(--border)]'}`}>
                {/* Accent glow */}
                <div className="absolute -top-12 -right-12 w-24 h-24 bg-[var(--primary)]/10 rounded-full blur-xl pointer-events-none" />
                
                <div className="flex justify-between items-start">
                  <div>
                    <div className="flex items-center gap-1.5">
                      <h3 className="text-lg font-black text-[var(--text-1)]">Knowtis Pro</h3>
                      <span className="text-[9px] font-black bg-[var(--primary)] text-white px-1.5 py-0.5 rounded-full uppercase tracking-wider">Popular</span>
                    </div>
                    <p className="text-xs text-[var(--text-3)] font-semibold mt-1">Your academic super-agent</p>
                  </div>
                  <div className="text-right">
                    <span className="text-2xl font-black text-[var(--text-1)]">
                      {billingCycle === 'monthly' ? '$4.99' : '$49.99'}
                    </span>
                    <span className="text-xs text-[var(--text-3)] font-bold">
                      {billingCycle === 'monthly' ? '/mo' : '/yr'}
                    </span>
                  </div>
                </div>

                <div className="my-4 border-t border-[var(--border-soft)]" />

                <ul className="space-y-2 text-xs font-semibold text-[var(--text-2)]">
                  {PLAN_FEATURES.map(f => <FeatureRow key={f.label} feature={f} tier="pro" />)}
                </ul>

                {isPremium ? (
                  <button
                    disabled
                    className="w-full h-11 mt-4 rounded-[14px] bg-[var(--primary-dim)] border border-[var(--primary-mid)] text-[var(--primary)] text-xs font-black uppercase"
                  >
                    Current Plan
                  </button>
                ) : (
                  <button
                    onClick={() => handleUpgrade('premium')}
                    className="w-full h-11 mt-4 rounded-[14px] bg-[#171717] hover:bg-[#292929] text-white text-xs font-black uppercase tracking-wider transition-all shadow-md active:scale-[0.99]"
                  >
                    Upgrade to Pro Plan
                  </button>
                )}
              </div>
            </div>
          </motion.div>
        )}

        {/* ── 4. QUIET HOURS VIEW ── */}
        {activeView === 'quiet_hours' && (
          <motion.div
            key="quiet_hours"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.25 }}
            className="space-y-5"
          >
            <div className="flex items-center justify-between">
              <button
                onClick={() => { saveQuietHours(); setActiveView('default'); }}
                className="w-9 h-9 rounded-[18px] bg-white border border-[var(--border)] flex items-center justify-center shrink-0 shadow-sm hover:bg-[var(--surface-2)] transition-all active:scale-95"
              >
                <ArrowLeft className="w-4 h-4 text-[var(--text-2)]" />
              </button>
              <h2 className="text-base font-black text-[var(--text-1)] mx-auto">Quiet hours</h2>
              <button
                onClick={() => { saveQuietHours(); setActiveView('default'); }}
                className="text-xs font-black uppercase tracking-wider text-[var(--primary)] hover:text-[var(--primary)]/80"
              >
                Done
              </button>
            </div>

            {/* Toggle Enable */}
            <div className="clay-card-strong p-4 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-[var(--text-1)]">Enable quiet hours</h3>
                <p className="text-xs text-[var(--text-3)] font-semibold mt-0.5">Knowtis won&apos;t notify you during quiet times</p>
              </div>
              <button
                onClick={() => setEnableQuietHours(v => !v)}
                role="switch"
                aria-checked={enableQuietHours}
                className={`w-12 h-6 rounded-full transition-colors relative shrink-0 ${enableQuietHours ? 'bg-[var(--primary)]' : 'bg-[#E9E9E6]'}`}
              >
                <div className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${enableQuietHours ? 'translate-x-6' : 'translate-x-0.5'}`} />
              </button>
            </div>

            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: enableQuietHours ? 1 : 0.45, y: 0 }}
              transition={{ duration: 0.25 }}
              className={`space-y-5 ${enableQuietHours ? '' : 'pointer-events-none select-none'}`}
              aria-hidden={!enableQuietHours}
            >
                {/* Time picker range */}
                <div className="clay-card p-4 space-y-4">
                  <p className="text-[11px] font-black uppercase tracking-wider text-[var(--text-3)] px-1">Quiet period</p>
                  <div className="flex items-center gap-4">
                    <div className="flex-1">
                      <label className="text-[10px] font-bold text-[var(--text-3)] mb-1 block px-1">From</label>
                      <input
                        type="time"
                        value={quietFrom}
                        onChange={(e) => setQuietFrom(e.target.value)}
                        className="w-full h-11 px-3.5 rounded-[14px] border border-[var(--border)] text-sm font-bold text-[var(--text-1)] focus:outline-none"
                      />
                    </div>
                    <div className="flex-1">
                      <label className="text-[10px] font-bold text-[var(--text-3)] mb-1 block px-1">To</label>
                      <input
                        type="time"
                        value={quietTo}
                        onChange={(e) => setQuietTo(e.target.value)}
                        className="w-full h-11 px-3.5 rounded-[14px] border border-[var(--border)] text-sm font-bold text-[var(--text-1)] focus:outline-none"
                      />
                    </div>
                  </div>
                  <div className="p-3 bg-[var(--primary-dim)] text-[var(--primary)] rounded-[14px] text-xs font-semibold text-center border border-[var(--primary-mid)]">
                    ⏰ Reminders paused during quiet hours
                  </div>
                </div>

                {/* Day selector pills */}
                <div className="clay-card p-4">
                  <p className="text-[11px] font-black uppercase tracking-wider text-[var(--text-3)] mb-3 px-1">Repeat on</p>
                  <div className="flex flex-wrap justify-between gap-1.5">
                    {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(day => {
                      const active = quietDays.includes(day);
                      return (
                        <button
                          key={day}
                          onClick={() => {
                            if (active) {
                              setQuietDays(quietDays.filter(d => d !== day));
                            } else {
                              setQuietDays([...quietDays, day]);
                            }
                          }}
                          className={`w-10 h-10 rounded-full font-bold text-xs flex items-center justify-center transition-all border ${
                            active ? 'bg-[var(--primary)] text-white border-[var(--primary)] shadow-sm' : 'bg-white text-[var(--text-2)] border-[var(--border)] hover:bg-[var(--surface-2)]'
                          }`}
                        >
                          {day.substring(0, 1)}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Quiet preferences */}
                <div className="clay-card overflow-hidden divide-y divide-[var(--border-soft)]">
                  <div className="flex items-center justify-between p-4">
                    <div>
                      <p className="text-sm font-bold text-[var(--text-1)]">Allow high priority tasks</p>
                      <p className="text-xs text-[var(--text-3)] font-semibold mt-0.5">Still notify for urgent exams/deadlines</p>
                    </div>
                    <button
                      onClick={() => setAllowHighPriority(v => !v)}
                      role="switch"
                      aria-checked={allowHighPriority}
                      className={`w-12 h-6 rounded-full transition-colors relative shrink-0 ${allowHighPriority ? 'bg-[var(--primary)]' : 'bg-[#E9E9E6]'}`}
                    >
                      <div className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${allowHighPriority ? 'translate-x-6' : 'translate-x-0.5'}`} />
                    </button>
                  </div>

                  <div className="flex items-center justify-between p-4">
                    <div>
                      <p className="text-sm font-bold text-[var(--text-1)]">Weekend quiet hours</p>
                      <p className="text-xs text-[var(--text-3)] font-semibold mt-0.5">Apply quiet hours schedule on Sat & Sun</p>
                    </div>
                    <button
                      onClick={() => setWeekendQuiet(v => !v)}
                      role="switch"
                      aria-checked={weekendQuiet}
                      className={`w-12 h-6 rounded-full transition-colors relative shrink-0 ${weekendQuiet ? 'bg-[var(--primary)]' : 'bg-[#E9E9E6]'}`}
                    >
                      <div className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${weekendQuiet ? 'translate-x-6' : 'translate-x-0.5'}`} />
                    </button>
                  </div>
                </div>

                <p className="text-center text-xs text-[var(--text-3)] font-bold px-4 italic leading-relaxed">
                  🌙 Missed alerts during quiet hours will appear in your Daily AI Brief when you wake up.
                </p>
            </motion.div>
          </motion.div>
        )}

        {/* ── 6. SETTINGS VIEW ── */}
        {activeView === 'settings' && (
          <motion.div
            key="settings"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.25 }}
            className="space-y-5"
          >
            <div className="flex items-center justify-between">
              <button
                onClick={() => setActiveView('default')}
                className="w-9 h-9 rounded-[18px] bg-white border border-[var(--border)] flex items-center justify-center shrink-0 shadow-sm hover:bg-[var(--surface-2)] transition-all active:scale-95"
              >
                <ArrowLeft className="w-4 h-4 text-[var(--text-2)]" />
              </button>
              <h2 className="text-base font-black text-[var(--text-1)] mx-auto">Settings</h2>
              <div className="w-9 h-9 opacity-0" />
            </div>

            {/* General — links to existing functional views */}
            <div>
              <p className="text-[11px] font-black uppercase tracking-wider text-[var(--text-3)] mb-2 px-1">General</p>
              <div className="clay-card overflow-hidden divide-y divide-[var(--border-soft)]">
                <SettingsRow
                  icon={Edit3}
                  label="Edit Profile"
                  value="Name, email, and password"
                  color="var(--primary)"
                  onClick={openEditProfile}
                />
                <SettingsRow
                  icon={Star}
                  label="Subscription"
                  value={isPremium ? "Knowtis Pro ($4.99/mo)" : "Free tier — 2 groups"}
                  color="var(--warning)"
                  badge={isPremium ? "Pro" : "Free"}
                  onClick={() => setActiveView('subscription')}
                />
                <SettingsRow
                  icon={Moon}
                  label="Quiet Hours"
                  value={enableQuietHours ? `Muted ${quietFrom} – ${quietTo}` : "Disabled"}
                  color="var(--info)"
                  onClick={() => setActiveView('quiet_hours')}
                />
                <SettingsRow
                  icon={Smartphone}
                  label="Android Widget"
                  value="Preview your home screen widget"
                  color="var(--primary)"
                  onClick={() => setActiveView('widget')}
                />
              </div>
            </div>

            {/* Support — real links */}
            <div>
              <p className="text-[11px] font-black uppercase tracking-wider text-[var(--text-3)] mb-2 px-1">Support</p>
              <div className="clay-card overflow-hidden divide-y divide-[var(--border-soft)]">
                <a
                  href="mailto:support@knowtis.app?subject=Knowtis%20Help"
                  className="w-full flex items-center gap-3 px-4 py-3.5 hover:bg-[#FBFBFA]/60 active:bg-[#FBFBFA] transition-colors text-left"
                >
                  <div className="w-9 h-9 clay-icon flex items-center justify-center shrink-0 rounded-[18px]" style={{ background: 'var(--success-dim)' }}>
                    <HelpCircle className="w-[18px] h-[18px]" style={{ color: 'var(--success)' }} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-[var(--text-1)]">Help & FAQ</p>
                    <p className="text-xs text-[var(--text-3)] font-medium mt-0.5 truncate">Email us — we reply fast</p>
                  </div>
                  <ChevronRight className="w-4 h-4 shrink-0 text-[var(--text-3)]" />
                </a>
                <a
                  href="mailto:feedback@knowtis.app?subject=Knowtis%20Feedback"
                  className="w-full flex items-center gap-3 px-4 py-3.5 hover:bg-[#FBFBFA]/60 active:bg-[#FBFBFA] transition-colors text-left"
                >
                  <div className="w-9 h-9 clay-icon flex items-center justify-center shrink-0 rounded-[18px]" style={{ background: 'var(--info-dim)' }}>
                    <MessageSquare className="w-[18px] h-[18px]" style={{ color: 'var(--info)' }} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-[var(--text-1)]">Send feedback</p>
                    <p className="text-xs text-[var(--text-3)] font-medium mt-0.5 truncate">Tell us how we can improve</p>
                  </div>
                  <ChevronRight className="w-4 h-4 shrink-0 text-[var(--text-3)]" />
                </a>
              </div>
            </div>

            {/* About */}
            <div>
              <p className="text-[11px] font-black uppercase tracking-wider text-[var(--text-3)] mb-2 px-1">About</p>
              <div className="clay-card p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-[var(--text-2)]">Version</span>
                  <span className="text-sm font-black text-[var(--text-1)] tabular-nums">1.2.0</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-[var(--text-2)]">Plan</span>
                  <span className="text-sm font-black text-[var(--text-1)]">{isPremium ? "Premium" : "Free"}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-[var(--text-2)]">Member since</span>
                  <span className="text-sm font-black text-[var(--text-1)] tabular-nums">
                    {user?.created_at ? new Date(user.created_at).toLocaleDateString('en-US', { timeZone: 'Africa/Lagos', month: 'short', year: 'numeric' }) : '—'}
                  </span>
                </div>
              </div>
            </div>

            {/* Account settings / delete */}
            <div>
              <p className="text-[11px] font-black uppercase tracking-wider text-[var(--text-3)] mb-2 px-1">Danger Zone</p>
              <div className="clay-card overflow-hidden divide-y divide-[var(--border-soft)]">
                <button
                  onClick={() => setShowClearConfirm(true)}
                  disabled={aiClearing}
                  className="w-full flex items-center gap-3 px-4 py-3.5 hover:bg-[var(--danger-dim)] transition-colors text-left group disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  <div className="w-9 h-9 rounded-[18px] bg-[var(--danger-dim)] flex items-center justify-center shrink-0 transition-colors group-hover:bg-[var(--danger)]">
                    <MessageSquare className="w-[18px] h-[18px] text-[var(--danger)] group-hover:text-white transition-colors" />
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-bold text-[var(--danger)]">Clear AI chat</p>
                    <p className="text-xs text-[var(--text-3)] font-semibold mt-0.5">{aiClearing ? 'Clearing your conversation…' : 'Remove the entire AI conversation history'}</p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-[var(--danger)]/50 group-hover:text-[var(--danger)]" />
                </button>
                <button
                  onClick={() => setShowDeleteConfirm(true)}
                  className="w-full flex items-center gap-3 px-4 py-3.5 hover:bg-[var(--danger-dim)] transition-colors text-left group"
                >
                  <div className="w-9 h-9 rounded-[18px] bg-[var(--danger-dim)] flex items-center justify-center shrink-0 transition-colors group-hover:bg-[var(--danger)]">
                    <Trash2 className="w-[18px] h-[18px] text-[var(--danger)] group-hover:text-white transition-colors" />
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-bold text-[var(--danger)]">Delete account</p>
                    <p className="text-xs text-[var(--text-3)] font-semibold mt-0.5">Permanently delete your profile and synced data</p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-[var(--danger)]/50 group-hover:text-[var(--danger)]" />
                </button>
              </div>
            </div>
          </motion.div>
        )}

        {/* ── 7. ANDROID WIDGET PREVIEW VIEW ── */}
        {activeView === 'widget' && (
          <motion.div
            key="widget"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.25 }}
            className="space-y-5"
          >
            <div className="flex items-center justify-between">
              <button
                onClick={() => setActiveView('default')}
                className="w-9 h-9 rounded-[18px] bg-white border border-[var(--border)] flex items-center justify-center shrink-0 shadow-sm hover:bg-[var(--surface-2)] transition-all active:scale-95"
              >
                <ArrowLeft className="w-4 h-4 text-[var(--text-2)]" />
              </button>
              <h2 className="text-base font-black text-[var(--text-1)] mx-auto">Android Widget</h2>
              <div className="w-9 h-9 opacity-0" />
            </div>

            <div className="clay-card p-6 flex flex-col items-center justify-center">
              <AndroidWidgetPreview widgetData={widgetData} isLoading={loading} />
              
              <div className="mt-6 text-center space-y-2 max-w-sm">
                <h3 className="text-sm font-black text-[var(--text-1)]">Add Widget to Home Screen</h3>
                <p className="text-xs text-[var(--text-3)] font-semibold leading-relaxed">
                  To view your academic timeline directly on your Android phone, long press on your home screen, choose Widgets, select Knowtis, and drag it to your screen.
                </p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── MODAL: LOGOUT CONFIRMATION ── */}
      <AnimatePresence>
        {showLogoutConfirm && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setShowLogoutConfirm(false)}
              className="absolute inset-0 bg-black/30 backdrop-blur-sm"
            />
            {/* Dialog */}
            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              className="relative w-full max-w-sm bg-white rounded-[28px] p-6 shadow-xl border border-[var(--border)] overflow-hidden"
            >
              <div className="flex flex-col items-center text-center">
                <div className="w-14 h-14 rounded-full bg-[var(--danger-dim)] flex items-center justify-center mb-4">
                  <LogOut className="w-6 h-6 text-[var(--danger)]" />
                </div>
                <h3 className="text-[17px] font-black text-[var(--text-1)]">Are you sure you want to log out?</h3>
                <p className="text-xs text-[var(--text-3)] font-semibold mt-1 px-4">
                  You will need to enter your credentials to access your academic feed again.
                </p>
                <div className="flex gap-3 w-full mt-6">
                  <button
                    onClick={() => setShowLogoutConfirm(false)}
                    className="flex-1 h-12 rounded-[18px] border border-[var(--border)] hover:bg-[var(--surface-2)] text-xs font-bold text-[var(--text-2)] transition-colors active:scale-95"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => {
                      setShowLogoutConfirm(false);
                      logout();
                    }}
                    className="flex-1 h-12 rounded-[18px] bg-[#171717] hover:bg-[#292929] text-white text-xs font-black uppercase tracking-wider transition-colors active:scale-95"
                  >
                    Log out
                  </button>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ── MODAL: DELETE ACCOUNT CONFIRMATION ── */}
      <AnimatePresence>
        {showDeleteConfirm && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setShowDeleteConfirm(false)}
              className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            />
            {/* Dialog */}
            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              className="relative w-full max-w-sm bg-white rounded-[28px] p-6 shadow-xl border border-[var(--border)] overflow-hidden"
            >
              <div className="flex flex-col items-center text-center">
                <div className="w-14 h-14 rounded-full bg-[var(--danger-dim)] flex items-center justify-center mb-4 border border-[var(--danger)]/15">
                  <Trash2 className="w-6 h-6 text-[var(--danger)]" />
                </div>
                <h3 className="text-[17px] font-black text-[var(--danger)]">Delete your account permanently?</h3>
                <p className="text-xs text-[var(--text-3)] font-semibold mt-1 px-4 leading-relaxed">
                  This action cannot be undone. All your WhatsApp groups, calendars, reminders, and notifications will be permanently erased.
                </p>
                <div className="flex gap-3 w-full mt-6">
                  <button
                    onClick={() => setShowDeleteConfirm(false)}
                    className="flex-1 h-12 rounded-[18px] border border-[var(--border)] hover:bg-[var(--surface-2)] text-xs font-bold text-[var(--text-2)] transition-colors active:scale-95"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleDeleteAccount}
                    disabled={loading}
                    className="flex-1 h-12 rounded-[18px] bg-[var(--danger)] hover:bg-[var(--danger)]/90 text-white text-xs font-black uppercase tracking-wider transition-colors active:scale-95 disabled:bg-[var(--text-3)]"
                  >
                    {loading ? 'Deleting...' : 'Delete Account'}
                  </button>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ── MODAL: CLEAR AI CHAT CONFIRMATION ── */}
      <AnimatePresence>
        {showClearConfirm && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setShowClearConfirm(false)}
              className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            />
            {/* Dialog */}
            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              className="relative w-full max-w-sm bg-white rounded-[28px] p-6 shadow-xl border border-[var(--border)] overflow-hidden"
            >
              <div className="flex flex-col items-center text-center">
                <div className="w-14 h-14 rounded-full bg-[var(--danger-dim)] flex items-center justify-center mb-4 border border-[var(--danger)]/15">
                  <MessageSquare className="w-6 h-6 text-[var(--danger)]" />
                </div>
                <h3 className="text-[17px] font-black text-[var(--danger)]">Clear AI chat history?</h3>
                <p className="text-xs text-[var(--text-3)] font-semibold mt-1 px-4 leading-relaxed">
                  This action cannot be undone. Your entire AI chat conversation history will be permanently deleted.
                </p>
                <div className="flex gap-3 w-full mt-6">
                  <button
                    onClick={() => setShowClearConfirm(false)}
                    className="flex-1 h-12 rounded-[18px] border border-[var(--border)] hover:bg-[var(--surface-2)] text-xs font-bold text-[var(--text-2)] transition-colors active:scale-95"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleClearAIChat}
                    disabled={aiClearing}
                    className="flex-1 h-12 rounded-[18px] bg-[var(--danger)] hover:bg-[var(--danger)]/90 text-white text-xs font-black uppercase tracking-wider transition-colors active:scale-95 disabled:bg-[var(--text-3)]"
                  >
                    {aiClearing ? 'Clearing...' : 'Clear Chat'}
                  </button>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ── MODAL: CONNECT WHATSAPP ── */}
      <AnimatePresence>
        {showConnectWhatsApp && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => !connecting && setShowConnectWhatsApp(false)}
              className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            />
            {/* Dialog */}
            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              className="relative w-full max-w-sm bg-white rounded-[28px] p-6 shadow-xl border border-[var(--border)] overflow-hidden"
            >
              <form onSubmit={handleConnectWhatsApp} className="flex flex-col items-center text-center">
                <div className="w-14 h-14 rounded-full bg-[var(--success-dim)] flex items-center justify-center mb-4 border border-[var(--success)]/15">
                  <Phone className="w-6 h-6 text-[var(--success)]" />
                </div>
                <h3 className="text-[17px] font-black text-[var(--text-1)]">Connect WhatsApp</h3>
                <p className="text-xs text-[var(--text-3)] font-semibold mt-1 px-2 leading-relaxed">
                  Enter the WhatsApp number linked to your account. We use it to identify you when tagging the bot in groups.
                </p>

                <div className="w-full mt-5 text-left">
                  <label className="text-[11px] font-black uppercase tracking-wider text-[var(--text-3)] mb-1.5 block px-1">WhatsApp Phone Number</label>
                  <input
                    type="tel"
                    autoFocus
                    value={connectNumber}
                    onChange={(e) => setConnectNumber(e.target.value)}
                    disabled={connecting}
                    className="w-full h-12 px-4 rounded-[18px] border border-[var(--border)] bg-white text-sm font-semibold text-[var(--text-1)] focus:border-[var(--primary)] focus:outline-none transition-all shadow-sm disabled:opacity-60"
                    placeholder="e.g. +234 801 234 5678"
                  />
                </div>

                {error && (
                  <div className="w-full mt-3 p-3 rounded-[18px] bg-[var(--danger-dim)] text-[var(--danger)] text-xs font-semibold flex items-center gap-2 border border-[var(--danger)]/14">
                    <ShieldAlert className="w-4 h-4 shrink-0" />
                    {error}
                    <button type="button" onClick={clearError} className="ml-auto text-[var(--danger)]/60 hover:text-[var(--danger)]">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                )}

                <div className="flex gap-3 w-full mt-6">
                  <button
                    type="button"
                    onClick={() => setShowConnectWhatsApp(false)}
                    disabled={connecting}
                    className="flex-1 h-12 rounded-[18px] border border-[var(--border)] hover:bg-[var(--surface-2)] text-xs font-bold text-[var(--text-2)] transition-colors active:scale-95 disabled:opacity-60"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={connecting || !connectNumber.trim()}
                    className="flex-1 h-12 rounded-[18px] bg-[var(--success)] hover:bg-[var(--success)]/90 text-white text-xs font-black uppercase tracking-wider transition-colors active:scale-95 disabled:bg-[var(--text-3)]"
                  >
                    {connecting ? 'Connecting...' : 'Connect'}
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
