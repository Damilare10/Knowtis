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
  Loader2,
  Lock,
  Mail,
  MessageCircle,
  X,
  XCircle,
  ArrowLeft,
  ArrowRight,
} from 'lucide-react';
import { useAppStore } from '@/lib/store';
import { authApi } from '@/lib/api';

import { RollerSpinner } from '@/components/ui/icons';

type UsernameState =
  | { kind: 'idle' }
  | { kind: 'checking' }
  | { kind: 'available'; suggestion?: string }
  | { kind: 'taken'; suggestion?: string }
  | { kind: 'invalid' };

const USERNAME_RE = /^[a-z0-9_]{3,20}$/;

type Step = 'email' | 'password' | 'username' | 'whatsapp';

const STEPS: Step[] = ['email', 'password', 'username', 'whatsapp'];
const TOTAL_STEPS = STEPS.length;

function classifyUsername(raw: string): { normalised: string; clientState: UsernameState } {
  const normalised = raw.trim().toLowerCase();
  if (!normalised) return { normalised, clientState: { kind: 'idle' } };
  if (!USERNAME_RE.test(normalised)) {
    return { normalised, clientState: { kind: 'invalid' } };
  }
  return { normalised, clientState: { kind: 'checking' } };
}

export default function RegisterMobilePage() {
  const router = useRouter();
  const { register, error, clearError, loading } = useAppStore();
  const onboarded = typeof window !== 'undefined' && localStorage.getItem('knowtis_onboarded') === 'true';
  const [isMobile, setIsMobile] = useState<boolean | null>(null);

  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [direction, setDirection] = useState(1);
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [whatsappNumber, setWhatsappNumber] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [privacyAccepted, setPrivacyAccepted] = useState(false);
  const [usernameState, setUsernameState] = useState<UsernameState>({ kind: 'idle' });
  const checkSeqRef = useRef(0);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 1024);
    };
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

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
        if (seq !== checkSeqRef.current) return;
        const data = response.data as { username: string; available: boolean; suggestion?: string | null; reason?: string | null };
        if (typeof data?.available === 'boolean') {
          if (data.available) {
            setUsernameState({ kind: 'available' });
          } else if (data.reason === 'invalid') {
            setUsernameState({ kind: 'invalid' });
          } else {
            setUsernameState({ kind: 'taken', suggestion: data.suggestion ?? undefined });
          }
        } else {
          setUsernameState({ kind: 'idle' });
        }
      } catch {
        if (seq !== checkSeqRef.current) return;
        setUsernameState({ kind: 'idle' });
      }
    }, 350);
    return () => window.clearTimeout(timer);
  }, [username]);

  const currentStep = STEPS[currentStepIndex];
  const isLastStep = currentStepIndex === TOTAL_STEPS - 1;

  const passwordTooShort = password.length > 0 && password.length < 8;
  const passwordsMatch = confirmPassword.length > 0 && confirmPassword === password;
  const passwordsMismatch = confirmPassword.length > 0 && confirmPassword !== password;

  const canProceed = useCallback(() => {
    switch (currentStep) {
      case 'email':
        return email.length > 0 && email.includes('@');
      case 'password':
        return password.length >= 8;
      case 'username':
        return username.trim().length >= 3 && (usernameState.kind === 'available' || usernameState.kind === 'idle');
      case 'whatsapp':
        return privacyAccepted;
      default:
        return false;
    }
  }, [currentStep, email, password, username, usernameState, privacyAccepted]);

  const handleNext = useCallback(() => {
    if (!canProceed()) return;
    if (currentStepIndex < TOTAL_STEPS - 1) {
      setDirection(1);
      setCurrentStepIndex(prev => prev + 1);
    }
  }, [canProceed, currentStepIndex]);

  const handleBack = useCallback(() => {
    if (currentStepIndex > 0) {
      setDirection(-1);
      setCurrentStepIndex(prev => prev - 1);
    }
  }, [currentStepIndex]);

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canProceed()) return;
    const ok = await register({
      email,
      username: username.trim().toLowerCase(),
      password,
      confirm_password: confirmPassword || password,
      whatsapp_number: whatsappNumber.trim() || undefined,
    });
    if (ok) {
      router.replace('/onboarding/research');
    }
  }, [canProceed, register, email, username, password, confirmPassword, whatsappNumber, router]);

  const applySuggestion = useCallback(() => {
    if ('suggestion' in usernameState && usernameState.suggestion) {
      setUsername(usernameState.suggestion);
    }
  }, [usernameState]);

  const slideVariants = {
    enter: (dir: number) => ({ x: dir > 0 ? 160 : -160, opacity: 0 }),
    center: { x: 0, opacity: 1, transition: { x: { type: 'spring' as const, stiffness: 320, damping: 32 }, opacity: { duration: 0.25 } } },
    exit: (dir: number) => ({ x: dir < 0 ? 160 : -160, opacity: 0, transition: { x: { type: 'spring' as const, stiffness: 320, damping: 32 }, opacity: { duration: 0.2 } } }),
  };

  if (isMobile === null) {
    return <main className="min-h-dvh bg-[#FBFBFA]" />;
  }

  if (!isMobile) {
    return null;
  }

  return (
    <main
      className="min-h-dvh bg-[#FBFBFA] text-[#171717] flex flex-col justify-between overflow-x-hidden"
      style={{
        paddingTop: 'max(16px, env(safe-area-inset-top, 16px))',
        paddingBottom: 'max(16px, env(safe-area-inset-bottom, 16px))',
      }}
    >
      {/* Header */}
      <header className="relative px-6 pt-2 pb-3 flex items-center justify-between shrink-0">
        {!onboarded && (
          <button
            type="button"
            onClick={() => router.back()}
            aria-label="Go back"
            className="flex h-10 w-10 items-center justify-center rounded-full border border-[var(--border)] bg-white text-[var(--text-1)] shadow-sm hover:bg-[#F4F3EF] focus:outline-none"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
        )}
        <Link href="/onboarding" className="inline-flex items-baseline gap-1 text-[18px] font-extrabold tracking-[-0.05em] lowercase mx-auto">
          <span>know</span>
          <span className="text-[#FF5A36]">tis</span>
        </Link>
        <div className="w-10" />
      </header>

      {/* Progress indicator */}
      <div className="px-6 pb-4 flex items-center gap-2" role="progressbar" aria-valuenow={currentStepIndex + 1} aria-valuemin={1} aria-valuemax={TOTAL_STEPS}>
        {STEPS.map((_, i) => (
          <div key={i} className="h-1.5 flex-1 rounded-full bg-[#171717]/15 overflow-hidden">
            <motion.div
              initial={false}
              animate={{ scaleX: i <= currentStepIndex ? 1 : 0 }}
              transition={{ type: 'spring', stiffness: 300, damping: 30, delay: i * 0.05 }}
              className="h-full w-full rounded-full bg-[#171717] origin-left"
            />
          </div>
        ))}
      </div>

      {/* Content area - fills remaining space */}
      <div className="flex-1 flex flex-col justify-start px-6 pb-44 overflow-y-auto">
        <AnimatePresence mode="popLayout" initial={false} custom={direction}>
          <motion.div
            key={currentStep}
            custom={direction}
            variants={slideVariants}
            initial="enter"
            animate="center"
            exit="exit"
            className="w-full pt-4"
          >
            {/* Step title */}
            <div className="mb-8">
              <h1 className="text-[28px] font-black leading-[1.1] tracking-[-0.03em] text-[#171717]">
                {currentStep === 'email' && 'Enter your email'}
                {currentStep === 'password' && 'Create a password'}
                {currentStep === 'username' && 'Choose a username'}
                {currentStep === 'whatsapp' && 'WhatsApp (optional)'}
              </h1>
              <p className="mt-2 text-[15px] font-medium text-[#686862]">
                {currentStep === 'email' && "We'll send a verification link to this address."}
                {currentStep === 'password' && 'Use a unique password you don\'t use elsewhere.'}
                {currentStep === 'username' && 'This is your public handle. You can change it later.'}
                {currentStep === 'whatsapp' && 'Used only for class-related reminders. Never shared or spammed.'}
              </p>
            </div>

            {error && (
              <motion.div
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                className="mb-6 flex items-center justify-between gap-3 rounded-[18px] border border-[#FFD8CD] bg-[var(--danger-dim)] p-3.5 text-xs font-semibold text-[var(--danger)]"
              >
                <span>{typeof error === 'string' ? error : typeof error === 'object' && error !== null ? (error as { msg?: string }).msg || JSON.stringify(error) : String(error)}</span>
                <button type="button" onClick={clearError} className="font-bold text-[var(--danger)]">
                  Dismiss
                </button>
              </motion.div>
            )}

            <form id="signup-form" onSubmit={handleSubmit} className="space-y-4" noValidate>
              {/* EMAIL STEP */}
              {currentStep === 'email' && (
                <div className="space-y-2">
                  <label className="block pl-1 text-[12px] font-bold text-[var(--text-2)]">Email address</label>
                  <div className="relative">
                    <Mail className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--text-3)]" />
                    <input
                      type="email"
                      required
                      autoComplete="email"
                      placeholder="student@school.edu"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full rounded-[20px] border border-[var(--border)] bg-white py-3.5 pl-11 pr-4 text-sm font-semibold text-[var(--text-1)] outline-none transition-all placeholder:text-[var(--text-3)] focus:border-[#FFB29F] focus:ring-4 focus:ring-[#FF5A36]/10"
                      autoFocus
                    />
                  </div>
                </div>
              )}

              {/* PASSWORD STEP */}
              {currentStep === 'password' && (
                <div className="space-y-2">
                  <label className="block pl-1 text-[12px] font-bold text-[var(--text-2)]">Password</label>
                  <div className="relative">
                    <Lock className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--text-3)]" />
                    <input
                      type={showPassword ? 'text' : 'password'}
                      required
                      autoComplete="new-password"
                      placeholder="At least 8 characters"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className={`w-full rounded-[20px] border bg-white py-3.5 pl-11 pr-12 text-sm font-semibold text-[var(--text-1)] outline-none transition-all placeholder:text-[var(--text-3)] focus:ring-4 ${
                        passwordTooShort
                          ? 'border-[#FFD8CD] focus:border-[#E54835] focus:ring-[#E54835]/10'
                          : 'border-[var(--border)] focus:border-[#FFB29F] focus:ring-[#FF5A36]/10'
                      }`}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-4 top-1/2 -translate-y-1/2 text-[var(--text-3)] hover:text-[var(--text-1)] focus:outline-none"
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                    >
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  {passwordTooShort && (
                    <p className="pl-1 text-[11px] font-semibold text-[#E54835]">At least 8 characters required.</p>
                  )}
                  {!passwordTooShort && password.length > 0 && (
                    <p className="pl-1 text-[11px] font-semibold text-[#1C8D5A]">Strong password.</p>
                  )}
                </div>
              )}

              {/* USERNAME STEP */}
              {currentStep === 'username' && (
                <div className="space-y-2">
                  <label className="block pl-1 text-[12px] font-bold text-[var(--text-2)]">Username</label>
                  <div className="relative">
                    <AtSign className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--text-3)]" />
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
                      className={`w-full rounded-[20px] border bg-white py-3.5 pl-11 pr-12 text-sm font-semibold text-[var(--text-1)] outline-none transition-all placeholder:text-[var(--text-3)] focus:ring-4 ${
                        usernameState.kind === 'taken' || usernameState.kind === 'invalid'
                          ? 'border-[#E54835] focus:border-[#E54835] focus:ring-[#E54835]/10'
                          : usernameState.kind === 'available'
                            ? 'border-[#A7F3D0] focus:border-[#32B87B] focus:ring-[#32B87B]/15'
                            : 'border-[var(--border)] focus:border-[#FFB29F] focus:ring-[#FF5A36]/10'
                      }`}
                    />
                    <div className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 flex h-4 w-4 items-center justify-center">
                      <AnimatePresence mode="wait" initial={false}>
                        {usernameState.kind === 'checking' && (
                          <motion.span key="checking" initial={{ opacity: 0, scale: 0.7 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.7 }} transition={{ duration: 0.15 }}>
                            <Loader2 className="h-4 w-4 animate-spin text-[var(--text-3)]" />
                          </motion.span>
                        )}
                        {usernameState.kind === 'available' && (
                          <motion.span key="available" initial={{ opacity: 0, scale: 0.5 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.5 }} transition={{ duration: 0.18 }}>
                            <Check className="h-4 w-4 text-[#1C8D5A]" strokeWidth={3} />
                          </motion.span>
                        )}
                        {(usernameState.kind === 'taken' || usernameState.kind === 'invalid') && (
                          <motion.span key="taken" initial={{ opacity: 0, scale: 0.5 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.5 }} transition={{ duration: 0.18 }}>
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
                            <button type="button" onClick={applySuggestion} className="font-bold text-[var(--primary)] underline-offset-2 hover:underline">
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
              )}

              {/* WHATSAPP STEP */}
              {currentStep === 'whatsapp' && (
                <div className="space-y-2">
                  <label className="flex items-baseline gap-1 pl-1 text-[12px] font-bold text-[var(--text-2)]">
                    WhatsApp number
                    <span className="text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--text-3)]">(optional)</span>
                  </label>
                  <div className="relative">
                    <MessageCircle className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--text-3)]" />
                    <input
                      type="tel"
                      autoComplete="tel"
                      placeholder="+234 801 234 5678"
                      value={whatsappNumber}
                      onChange={(e) => setWhatsappNumber(e.target.value)}
                      className="w-full rounded-[20px] border border-[var(--border)] bg-white py-3.5 pl-11 pr-4 text-sm font-semibold text-[var(--text-1)] outline-none transition-all placeholder:text-[var(--text-3)] focus:border-[#FFB29F] focus:ring-4 focus:ring-[#FF5A36]/10"
                    />
                  </div>
                </div>
              )}
            </form>
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Fixed bottom navigation */}
      <div className="fixed bottom-0 left-0 right-0 px-6 pb-6 pt-3 bg-white/95 backdrop-blur-md border-t border-[#E9E9E6]/80 shadow-[0_-8px_24px_rgba(0,0,0,0.04)] shrink-0 z-30">
        <div className="max-w-[430px] mx-auto flex flex-col gap-3">
          
          {/* Terms checkbox - only on last step */}
          {isLastStep && (
            <div className="py-1 px-1">
              <label className="flex items-start gap-3 cursor-pointer select-none group">
                <div className="relative flex items-center justify-center shrink-0 mt-0.5">
                  <input
                    type="checkbox"
                    checked={privacyAccepted}
                    onChange={(e) => setPrivacyAccepted(e.target.checked)}
                    className="peer w-5 h-5 rounded-md border border-[#D1D1CB] appearance-none bg-white checked:bg-[#FF5A36] checked:border-[#FF5A36] focus:outline-none transition-all cursor-pointer shadow-xs checked:shadow-[0_4px_12px_rgba(255,90,54,0.3)]"
                  />
                  <Check className="w-3.5 h-3.5 stroke-[3] text-white absolute pointer-events-none opacity-0 peer-checked:opacity-100 transition-opacity" />
                </div>
                <span className="text-[12px] font-semibold leading-snug text-[#686862]">
                  I agree to the{' '}
                  <a href="/terms" target="_blank" className="font-bold text-[#FF5A36] hover:underline underline-offset-2" onClick={(e) => e.stopPropagation()}>Terms of Use</a>
                  {' '}and{' '}
                  <a href="/privacy" target="_blank" className="font-bold text-[#FF5A36] hover:underline underline-offset-2" onClick={(e) => e.stopPropagation()}>Privacy Policy</a>
                </span>
              </label>
            </div>
          )}

          <div className="flex items-center gap-3 w-full">
            {currentStepIndex > 0 && (
              <button
                type="button"
                onClick={handleBack}
                className="w-12 h-12 rounded-full bg-white border border-[var(--border)] shadow-sm flex items-center justify-center text-[var(--text-1)] active:scale-95 transition-all shrink-0"
                aria-label="Back"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
            )}
            <motion.button
              whileHover={canProceed() ? { scale: 1.02, boxShadow: '0 22px 44px rgba(30,30,30,0.20)' } : undefined}
              whileTap={canProceed() ? { scale: 0.97, boxShadow: '0 8px 20px rgba(30,30,30,0.12)' } : undefined}
              transition={{ type: 'spring', stiffness: 400, damping: 20 }}
              type={isLastStep ? 'submit' : 'button'}
              form={isLastStep ? 'signup-form' : undefined}
              onClick={isLastStep ? undefined : handleNext}
              disabled={!canProceed() || loading}
              className="flex-1 h-12 bg-[#171717] hover:bg-[#2c2c2c] text-white font-bold rounded-full flex items-center justify-center gap-2 text-sm shadow-[0_8px_16px_rgba(0,0,0,0.1)] active:scale-[0.98] transition-all disabled:cursor-not-allowed disabled:bg-[#171717]/30 disabled:shadow-none"
            >
              {loading ? (
                <>
                  <RollerSpinner className="w-4 h-4 text-white" />
                  <span>Creating account...</span>
                </>
              ) : isLastStep ? (
                <>
                  Create account <ArrowRight className="w-4 h-4" />
                </>
              ) : (
                <>
                  Continue <ArrowRight className="w-4 h-4" />
                </>
              )}
            </motion.button>
          </div>

          <p className="text-center text-xs font-medium text-[var(--text-3)]">
            Already have an account?{' '}
            <Link href="/login" className="font-bold text-[var(--primary)]" onClick={clearError}>
              Log in
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}