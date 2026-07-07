'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  AtSign,
  Check,
  CheckCircle2,
  Eye,
  EyeOff,
  FileText,
  Loader2,
  Lock,
  Mail,
  MessageCircle,
  ShieldCheck,
  X,
  XCircle,
  ArrowLeft,
} from 'lucide-react';
import { useAppStore } from '@/lib/store';
import { authApi, GOOGLE_OAUTH_URL } from '@/lib/api';

type UsernameState =
  | { kind: 'idle' }
  | { kind: 'checking' }
  | { kind: 'available'; suggestion?: string }
  | { kind: 'taken'; suggestion?: string }
  | { kind: 'invalid' };

const USERNAME_RE = /^[a-z0-9_]{3,20}$/;

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
    </svg>
  );
}

function AppleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
      <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.81-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M15.97 4.17c.66-.81 1.11-1.93.99-3.06-.96.04-2.13.64-2.82 1.45-.6.69-1.12 1.84-.98 2.94.1.08.2.1.29.1 1 .01 2.2-.62 2.52-1.43z"/>
    </svg>
  );
}

function classifyUsername(raw: string): { normalised: string; clientState: UsernameState } {
  const normalised = raw.trim().toLowerCase();
  if (!normalised) return { normalised, clientState: { kind: 'idle' } };
  if (!USERNAME_RE.test(normalised)) {
    return { normalised, clientState: { kind: 'invalid' } };
  }
  return { normalised, clientState: { kind: 'checking' } };
}

export default function RegisterPage() {
  const router = useRouter();
  const { register, error, clearError, loading } = useAppStore();

  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [whatsappNumber, setWhatsappNumber] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [privacyAccepted, setPrivacyAccepted] = useState(false);

  const [usernameState, setUsernameState] = useState<UsernameState>({ kind: 'idle' });
  const checkSeqRef = useRef(0);

  // ── Debounced username availability lookup. ─────────────────────────────
  useEffect(() => {
    const { normalised, clientState } = classifyUsername(username);
    if (clientState.kind !== 'checking') {
      setUsernameState(clientState);
      return;
    }
    setUsernameState({ kind: 'checking' });
    const seq = ++checkSeqRef.current;
    const timer = window.setTimeout(async () => {
      try {
        const response = await authApi.checkUsername(normalised);
        // Drop stale responses (the user has kept typing).
        if (seq !== checkSeqRef.current) return;
        const data = response.data as {
          username: string;
          available: boolean;
          suggestion?: string | null;
        };
        setUsernameState({
          kind: data.available ? 'available' : 'taken',
          suggestion: data.suggestion ?? undefined,
        });
      } catch (err) {
        if (seq !== checkSeqRef.current) return;
        console.error('Username availability check failed:', err);
        // On network error: let the server-side validator handle it on submit.
        setUsernameState({ kind: 'idle' });
      }
    }, 350);
    return () => window.clearTimeout(timer);
  }, [username]);

  // ── Live password match + strength signals. ─────────────────────────────
  const passwordTooShort = password.length > 0 && password.length < 8;
  const passwordsMatch =
    confirmPassword.length > 0 && confirmPassword === password;
  const passwordsMismatch =
    confirmPassword.length > 0 && confirmPassword !== password;

  const canSubmit =
    email.length > 0 &&
    username.trim().length >= 3 &&
    (usernameState.kind === 'available' || usernameState.kind === 'idle') &&
    password.length >= 8 &&
    passwordsMatch &&
    privacyAccepted &&
    !loading;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    const ok = await register({
      email,
      username: username.trim().toLowerCase(),
      password,
      confirm_password: confirmPassword,
      whatsapp_number: whatsappNumber.trim() || undefined,
    });
    if (ok) router.replace('/onboarding/research');
  };

  const applySuggestion = useCallback(() => {
    if ('suggestion' in usernameState && usernameState.suggestion) {
      setUsername(usernameState.suggestion);
    }
  }, [usernameState]);

  return (
    <main className="min-h-dvh bg-[#FBFBFA] text-[#171717] flex items-center justify-center overflow-y-auto overflow-x-hidden px-5 py-7">
      <section className="relative w-full max-w-[430px] flex flex-col">

        <header className="relative pb-6 flex items-center justify-center">
          <button
            type="button"
            onClick={() => router.back()}
            aria-label="Go back"
            className="absolute left-0 top-1/2 -translate-y-1/2 flex h-10 w-10 items-center justify-center rounded-full border border-[var(--border)] bg-white text-[var(--text-1)] shadow-sm hover:bg-[#F4F3EF] focus:outline-none"
          >
            <ArrowLeft className="h-4 w-4" />
        </button>
          <Link href="/onboarding" className="inline-flex items-baseline gap-1 text-[18px] font-extrabold tracking-[-0.05em] lowercase">
            <span>know</span>
            <span className="text-[#FF5A36]">tis</span>
        </Link>
      </header>

        <motion.div
          initial={{ opacity: 0, y: 18, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ type: 'spring', stiffness: 80, damping: 18 }}
          className="relative rounded-[30px] bg-white p-6 shadow-[0_28px_70px_rgba(30,30,30,0.08)]"
        >
          <div className="mb-6 flex items-center gap-4">
            <div className="relative h-16 w-16 shrink-0 rounded-[24px] bg-[#E7ECFF] shadow-[inset_0_8px_14px_rgba(255,255,255,0.84),0_18px_34px_rgba(57,63,102,0.12)]">
              <span className="absolute left-3.5 top-5 h-8 w-10 rounded-[14px] bg-[#FF5A36] rotate-[-8deg] shadow-[inset_0_6px_10px_rgba(255,255,255,0.36),0_12px_22px_rgba(255,90,54,0.22)]" />
              <span className="absolute right-2.5 top-2.5 h-7 w-7 rounded-full bg-[#FFE071] shadow-[inset_0_6px_9px_rgba(255,255,255,0.58)]" />
              <span className="absolute bottom-3 right-4 h-4 w-9 rounded-full bg-[#D9F1EC] shadow-[inset_0_4px_7px_rgba(255,255,255,0.72)]" />
            </div>
            <div>
              <h1 className="text-[30px] font-black leading-none tracking-[-0.055em] text-[var(--text-1)]">Create account</h1>
              <p className="mt-2 text-sm font-medium text-[var(--text-3)]">Start catching important class updates.</p>
            </div>
          </div>

          {error && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-5 flex items-center justify-between gap-3 rounded-[18px] border border-[#FFD8CD] bg-[var(--danger-dim)] p-3.5 text-xs font-semibold text-[var(--danger)]"
            >
              <span>{error}</span>
              <button type="button" onClick={clearError} className="font-bold text-[var(--danger)]">
                Dismiss
              </button>
            </motion.div>
          )}

          <form onSubmit={handleSubmit} className="space-y-3.5" noValidate>
            {/* Email */}
            <div className="space-y-2">
              <label className="block pl-1 text-[12px] font-bold text-[var(--text-2)]">Email address</label>
              <div className="relative">
                <Mail className="absolute left-4 top-4 h-4 w-4 text-[var(--text-3)]" />
                <input
                  type="email"
                  required
                  autoComplete="email"
                  placeholder="student@school.edu"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-[20px] border border-[var(--border)] bg-[#FBFBFA] py-3.5 pl-11 pr-4 text-sm font-semibold text-[var(--text-1)] outline-none transition-all placeholder:text-[var(--text-3)] focus:border-[#FFB29F] focus:ring-4 focus:ring-[#FF5A36]/10"
                />
              </div>
            </div>

            {/* Username (live availability) */}
            <div className="space-y-2">
              <label className="block pl-1 text-[12px] font-bold text-[var(--text-2)]">Username</label>
              <div className="relative">
                <AtSign className="absolute left-4 top-4 h-4 w-4 text-[var(--text-3)]" />
                <input
                  type="text"
                  required
                  autoComplete="username"
                  placeholder="Choose a username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  inputMode="text"
                  spellCheck={false}
                  aria-invalid={usernameState.kind === 'taken' || usernameState.kind === 'invalid'}
                  aria-describedby="username-status"
                  className={`w-full rounded-[20px] border bg-[#FBFBFA] py-3.5 pl-11 pr-12 text-sm font-semibold text-[var(--text-1)] outline-none transition-all placeholder:text-[var(--text-3)] focus:ring-4 ${
                    usernameState.kind === 'taken' || usernameState.kind === 'invalid'
                      ? 'border-[#E54835] focus:border-[#E54835] focus:ring-[#E54835]/10'
                      : usernameState.kind === 'available'
                        ? 'border-[#A7F3D0] focus:border-[#32B87B] focus:ring-[#32B87B]/15'
                        : 'border-[var(--border)] focus:border-[#FFB29F] focus:ring-[#FF5A36]/10'
                  }`}
                />
                <div className="pointer-events-none absolute right-4 top-4 flex h-4 w-4 items-center justify-center">
                  <AnimatePresence mode="wait" initial={false}>
                    {usernameState.kind === 'checking' && (
                      <motion.span
                        key="checking"
                        initial={{ opacity: 0, scale: 0.7 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.7 }}
                        transition={{ duration: 0.15 }}
                      >
                        <Loader2 className="h-4 w-4 animate-spin text-[var(--text-3)]" />
                      </motion.span>
                    )}
                    {usernameState.kind === 'available' && (
                      <motion.span
                        key="available"
                        initial={{ opacity: 0, scale: 0.5 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.5 }}
                        transition={{ duration: 0.18 }}
                      >
                        <Check className="h-4 w-4 text-[#1C8D5A]" strokeWidth={3} />
                      </motion.span>
                    )}
                    {(usernameState.kind === 'taken' || usernameState.kind === 'invalid') && (
                      <motion.span
                        key="taken"
                        initial={{ opacity: 0, scale: 0.5 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.5 }}
                        transition={{ duration: 0.18 }}
                      >
                        <X className="h-4 w-4 text-[#E54835]" strokeWidth={3} />
                      </motion.span>
                    )}
                  </AnimatePresence>
                </div>
              </div>
              <div id="username-status" className="min-h-[18px] pl-1 text-[11px] font-semibold">
                <AnimatePresence mode="wait" initial={false}>
                  {usernameState.kind === 'idle' && (
                    <motion.span key="hint" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="text-[var(--text-3)]">
                      3-20 chars · letters, numbers, underscores.
                    </motion.span>
                  )}
                  {usernameState.kind === 'checking' && (
                    <motion.span key="checking" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="text-[var(--text-3)]">
                      Checking…
                    </motion.span>
                  )}
                  {usernameState.kind === 'available' && (
                    <motion.span key="available" initial={{ opacity: 0, y: -2 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="text-[#1C8D5A]">
                      Available — nice pick!
                    </motion.span>
                  )}
                  {usernameState.kind === 'taken' && (
                    <motion.span key="taken" initial={{ opacity: 0, y: -2 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="text-[#E54835]">
                      That username is taken.{' '}
                      {usernameState.suggestion && (
                        <button
                          type="button"
                          onClick={applySuggestion}
                          className="font-bold text-[var(--primary)] underline-offset-2 hover:underline"
                        >
                          Use {usernameState.suggestion}?
                        </button>
                      )}
                    </motion.span>
                  )}
                  {usernameState.kind === 'invalid' && (
                    <motion.span key="invalid" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="text-[#E54835]">
                      3-20 chars · lowercase letters, numbers, and underscores only.
                    </motion.span>
                  )}
                </AnimatePresence>
              </div>
            </div>

            {/* Password */}
            <div className="space-y-2">
              <label className="block pl-1 text-[12px] font-bold text-[var(--text-2)]">Password</label>
              <div className="relative">
                <Lock className="absolute left-4 top-4 h-4 w-4 text-[var(--text-3)]" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  autoComplete="new-password"
                  placeholder="At least 8 characters"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={`w-full rounded-[20px] border bg-[#FBFBFA] py-3.5 pl-11 pr-12 text-sm font-semibold text-[var(--text-1)] outline-none transition-all placeholder:text-[var(--text-3)] focus:ring-4 ${
                    passwordTooShort
                      ? 'border-[#FFD8CD] focus:border-[#E54835] focus:ring-[#E54835]/10'
                      : 'border-[var(--border)] focus:border-[#FFB29F] focus:ring-[#FF5A36]/10'
                  }`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-4 top-4 text-[var(--text-3)] hover:text-[var(--text-1)] focus:outline-none"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {passwordTooShort && (
                <p className="pl-1 text-[11px] font-semibold text-[#E54835]">
                  At least 8 characters required.
                </p>
              )}
            </div>

            {/* Confirm password */}
            <div className="space-y-2">
              <label className="block pl-1 text-[12px] font-bold text-[var(--text-2)]">Confirm password</label>
              <div className="relative">
                <Lock className="absolute left-4 top-4 h-4 w-4 text-[var(--text-3)]" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  autoComplete="new-password"
                  placeholder="Re-enter your password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className={`w-full rounded-[20px] border bg-[#FBFBFA] py-3.5 pl-11 pr-12 text-sm font-semibold text-[var(--text-1)] outline-none transition-all placeholder:text-[var(--text-3)] focus:ring-4 ${
                    passwordsMismatch
                      ? 'border-[#E54835] focus:border-[#E54835] focus:ring-[#E54835]/10'
                      : passwordsMatch
                        ? 'border-[#A7F3D0] focus:border-[#32B87B] focus:ring-[#32B87B]/15'
                        : 'border-[var(--border)] focus:border-[#FFB29F] focus:ring-[#FF5A36]/10'
                  }`}
                />
                <div className="pointer-events-none absolute right-4 top-4 flex h-4 w-4 items-center justify-center">
                  <AnimatePresence mode="wait" initial={false}>
                    {passwordsMatch && (
                      <motion.span
                        key="match"
                        initial={{ opacity: 0, scale: 0.5 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.5 }}
                        transition={{ duration: 0.18 }}
                      >
                        <CheckCircle2 className="h-4 w-4 text-[#1C8D5A]" strokeWidth={2.4} />
                      </motion.span>
                    )}
                    {passwordsMismatch && (
                      <motion.span
                        key="mismatch"
                        initial={{ opacity: 0, scale: 0.5 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.5 }}
                        transition={{ duration: 0.18 }}
                      >
                        <XCircle className="h-4 w-4 text-[#E54835]" strokeWidth={2.4} />
                      </motion.span>
                    )}
                  </AnimatePresence>
                </div>
              </div>
              {passwordsMismatch && (
                <p className="pl-1 text-[11px] font-semibold text-[#E54835]">
                  Passwords don’t match — please re-check.
                </p>
              )}
              {passwordsMatch && (
                <p className="pl-1 text-[11px] font-semibold text-[#1C8D5A]">
                  Looks good.
                </p>
              )}
            </div>

            {/* Optional WhatsApp */}
            <div className="space-y-2">
              <label className="flex items-baseline gap-1 pl-1 text-[12px] font-bold text-[var(--text-2)]">
                WhatsApp number
                <span className="text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--text-3)]">(optional)</span>
              </label>
              <div className="relative">
                <MessageCircle className="absolute left-4 top-4 h-4 w-4 text-[var(--text-3)]" />
                <input
                  type="tel"
                  autoComplete="tel"
                  placeholder="+234 801 234 5678"
                  value={whatsappNumber}
                  onChange={(e) => setWhatsappNumber(e.target.value)}
                  className="w-full rounded-[20px] border border-[var(--border)] bg-[#FBFBFA] py-3.5 pl-11 pr-4 text-sm font-semibold text-[var(--text-1)] outline-none transition-all placeholder:text-[var(--text-3)] focus:border-[#FFB29F] focus:ring-4 focus:ring-[#FF5A36]/10"
                />
              </div>
              <p className="pl-1 text-[11px] font-medium text-[var(--text-3)]">
                Used only for class-related reminders. Never shared or spammed.
              </p>
            </div>

            <div className="rounded-[24px] border border-[var(--border)] bg-[#FBFBFA] p-4">
              <div className="flex items-start gap-3">
                <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-[#E7ECFF] text-[#3A4AA3]">
                  <ShieldCheck className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2 text-[13px] font-bold text-[var(--text-1)]">
                    <FileText className="h-4 w-4" />
                    Privacy Policy
                  </div>
                  <p className="mt-1 text-[11px] font-medium leading-5 text-[var(--text-3)]">
                    Please read this before creating your Knowtis account.
                  </p>
                </div>
              </div>

              <div className="mt-4 max-h-64 space-y-3 overflow-y-auto rounded-[18px] border border-[#E9E6E1] bg-white p-4 text-[11px] leading-5 text-[var(--text-2)]">
                <div>
                  <p className="font-bold text-[var(--text-1)]">Knowtis Privacy Policy</p>
                  <p className="mt-1">
                    Effective date: June 30, 2026. Knowtis helps students filter noisy university WhatsApp groups and surface relevant academic updates.
                  </p>
                </div>

                <div>
                  <p className="font-bold text-[var(--text-1)]">1. Information we collect</p>
                  <p className="mt-1">
                    When you register, we collect your email address, username, password, and any optional WhatsApp number you choose to add.
                    We also process data connected to your use of the service, including linked WhatsApp group references, academic events,
                    reminders, notification activity, subscription status, and messages you send through Knowtis AI features.
                  </p>
                </div>

                <div>
                  <p className="font-bold text-[var(--text-1)]">2. How we use your information</p>
                  <p className="mt-1">
                    We use your data to create and secure your account, personalize your dashboard, identify relevant class updates, send reminders
                    and notifications, support WhatsApp-related features, provide AI summaries or chat responses, process billing where applicable,
                    and maintain or improve the service.
                  </p>
                </div>

                <div>
                  <p className="font-bold text-[var(--text-1)]">3. How your information is stored and shared</p>
                  <p className="mt-1">
                    Your information is stored on systems used to operate Knowtis. We do not sell your personal information. We may share data
                    only with service providers needed to run the app, such as hosting, authentication, notifications, analytics, payments,
                    and AI processing tools, or when disclosure is required by law or necessary to protect the service and its users.
                  </p>
                </div>

                <div>
                  <p className="font-bold text-[var(--text-1)]">4. WhatsApp and academic content</p>
                  <p className="mt-1">
                    If you connect WhatsApp-related features, Knowtis may process group metadata, invite links, and academic messages or updates
                    needed to detect deadlines, tests, class changes, or other relevant school information. You should only connect groups you
                    are authorized to use.
                  </p>
                </div>

                <div>
                  <p className="font-bold text-[var(--text-1)]">5. Your choices</p>
                  <p className="mt-1">
                    You can update profile details, remove your optional WhatsApp number, or delete your account from the app when those features
                    are available. You may also choose not to use optional features such as AI chat, reminders, billing, or WhatsApp integrations.
                  </p>
                </div>

                <div>
                  <p className="font-bold text-[var(--text-1)]">6. Security and retention</p>
                  <p className="mt-1">
                    We use reasonable technical and organizational measures to protect your information, but no system is completely secure. We
                    keep information for as long as needed to provide Knowtis, comply with legal obligations, resolve disputes, and enforce our
                    agreements.
                  </p>
                </div>

                <div>
                  <p className="font-bold text-[var(--text-1)]">7. Contact</p>
                  <p className="mt-1">
                    If you have privacy questions or requests, contact the Knowtis team through the official support channel listed in the app or
                    on the project website.
                  </p>
                </div>
              </div>

              <label className="mt-4 flex items-start gap-3 rounded-[18px] border border-transparent px-1 py-1 text-[12px] font-semibold text-[var(--text-2)]">
                <input
                  type="checkbox"
                  checked={privacyAccepted}
                  onChange={(e) => setPrivacyAccepted(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-[var(--border)] text-[#FF5A36] focus:ring-2 focus:ring-[#FF5A36]/20"
                />
                <span>
                  I have read this privacy policy and understand how Knowtis collects and uses my information.
                </span>
              </label>
            </div>

            <motion.button
              whileHover={canSubmit ? { scale: 1.02, boxShadow: '0 22px 44px rgba(30,30,30,0.20)' } : undefined}
              whileTap={canSubmit ? { scale: 0.97, boxShadow: '0 8px 20px rgba(30,30,30,0.12)' } : undefined}
              transition={{ type: 'spring', stiffness: 400, damping: 20 }}
              type="submit"
              disabled={!canSubmit}
              className="flex h-[56px] w-full items-center justify-center rounded-full bg-[#1E1E1E] text-sm font-black tracking-[-0.01em] text-white shadow-[0_18px_36px_rgba(30,30,30,0.16)] hover:bg-[#292929] disabled:cursor-not-allowed disabled:bg-[#171717]/30 disabled:shadow-none"
            >
              {loading ? <span className="skeleton-soft h-3 w-24 rounded-full" /> : 'Create account'}
            </motion.button>
          </form>
        </motion.div>

        <p className="pt-6 text-center text-xs font-medium text-[var(--text-3)]">
          Already have an account?{' '}
          <Link href="/login" className="font-bold text-[var(--primary)]" onClick={clearError}>
            Log in
          </Link>
        </p>

        {/* Social sign up buttons */}
        <div className="mt-5 flex items-center gap-3">
          <div className="flex-1 h-px bg-[#E9E9E6]" />
          <span className="text-[11px] font-bold text-[#9A9A94] uppercase tracking-wider">or</span>
          <div className="flex-1 h-px bg-[#E9E9E6]" />
        </div>
        <div className="mt-5 flex items-center justify-center gap-3">
          <a 
            href={GOOGLE_OAUTH_URL} 
            className="flex items-center justify-center h-11 w-[56px] rounded-full bg-white border border-[#E9E9E6] hover:bg-[#FBFBFA] shadow-sm active:scale-[0.98] transition-all"
          >
            <GoogleIcon />
          </a>
          <button 
            className="flex items-center justify-center h-11 w-[56px] rounded-full bg-white border border-[#E9E9E6] hover:bg-[#FBFBFA] shadow-sm active:scale-[0.98] transition-all"
          >
            <AppleIcon />
          </button>
        </div>
      </section>
    </main>
  );
}
