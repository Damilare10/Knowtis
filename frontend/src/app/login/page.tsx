'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAppStore } from '@/lib/store';
import { User, Lock, Eye, EyeOff, ArrowLeft } from 'lucide-react';
import { motion } from 'framer-motion';
import { GOOGLE_OAUTH_URL } from '@/lib/api';

import { RollerSpinner, GoogleIcon, AppleIcon } from '@/components/ui/icons';

export default function LoginPage() {
  const router = useRouter();
  const { login, error, clearError, loading, isAuthenticated, hasHydrated } = useAppStore();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [onboarded, setOnboarded] = useState(false);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setOnboarded(localStorage.getItem('knowtis_onboarded') === 'true');
    }
  }, []);

  useEffect(() => {
    if (hasHydrated && isAuthenticated) {
      const isDoneOnboarding = typeof window !== 'undefined' && localStorage.getItem('knowtis_onboarded') === 'true';
      router.replace(isDoneOnboarding ? '/dashboard' : '/onboarding');
    }
  }, [hasHydrated, isAuthenticated, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !password) return;
    const ok = await login({ username: username.trim().toLowerCase(), password });
    if (ok) {
      const onboarded = localStorage.getItem('knowtis_onboarded') === 'true';
      router.replace(onboarded ? '/dashboard' : '/onboarding');
    }
  };

  return (
    <main
      className="min-h-dvh bg-[#FBFBFA] text-[#171717] flex items-center justify-center overflow-x-hidden overflow-y-auto px-5"
      style={{
        paddingTop: 'max(16px, env(safe-area-inset-top, 16px))',
        paddingBottom: 'max(16px, env(safe-area-inset-bottom, 16px))',
      }}
    >
      <section className="relative w-full max-w-[430px] flex flex-col">

        <header className="relative pb-6 flex items-center justify-center">
          {!onboarded && (
            <button
              type="button"
              onClick={() => router.back()}
              aria-label="Go back"
              className="absolute left-0 top-1/2 -translate-y-1/2 flex h-10 w-10 items-center justify-center rounded-full border border-[var(--border)] bg-white text-[var(--text-1)] shadow-sm hover:bg-[#F4F3EF] focus:outline-none"
            >
              <ArrowLeft className="h-4 w-4" />
            </button>
          )}
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
          <div className="mb-7 flex items-center gap-4">
            <div className="relative h-16 w-16 shrink-0 rounded-[24px] bg-[#D9F1EC] shadow-[inset_0_8px_14px_rgba(255,255,255,0.8),0_18px_34px_rgba(31,71,68,0.13)]">
              <span className="absolute left-4 top-5 h-7 w-9 rounded-[12px] bg-[#FF5A36] rotate-[-10deg] shadow-[inset_0_5px_9px_rgba(255,255,255,0.36),0_12px_22px_rgba(255,90,54,0.22)]" />
              <span className="absolute right-3 top-3 h-6 w-6 rounded-full bg-[#FFE071] shadow-[inset_0_5px_8px_rgba(255,255,255,0.55)]" />
            </div>
            <div>
              <h1 className="text-[30px] font-black leading-none tracking-[-0.055em] text-[#171717]">Welcome back</h1>
              <p className="mt-2 text-sm font-medium text-[var(--text-3)]">Sign in to continue filtering class updates.</p>
            </div>
          </div>

        {error && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-5 p-3.5 bg-[var(--danger-dim)] border border-[#FFD8CD] rounded-[18px] text-xs font-semibold text-[var(--danger)]"
          >
            {error}
          </motion.div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label className="block text-[12px] font-bold text-[var(--text-2)] pl-1">
              Username
            </label>
            <div className="relative">
              <User className="absolute left-4 top-4 w-4 h-4 text-[var(--text-3)]" />
              <input
                type="text"
                required
                placeholder="Enter your username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full pl-11 pr-4 py-3.5 rounded-[20px] border border-[var(--border)] outline-none text-sm bg-[#FBFBFA] focus:border-[#FFB29F] focus:ring-4 focus:ring-[#FF5A36]/10 transition-all text-[var(--text-1)] font-semibold placeholder:text-[var(--text-3)]"
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="block text-[12px] font-bold text-[var(--text-2)] pl-1">
              Password
            </label>
            <div className="relative">
              <Lock className="absolute left-4 top-4 w-4 h-4 text-[var(--text-3)]" />
              <input
                type={showPassword ? 'text' : 'password'}
                required
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-11 pr-12 py-3.5 rounded-[20px] border border-[var(--border)] outline-none text-sm bg-[#FBFBFA] focus:border-[#FFB29F] focus:ring-4 focus:ring-[#FF5A36]/10 transition-all text-[var(--text-1)] font-semibold placeholder:text-[var(--text-3)]"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-4 top-4 text-[var(--text-3)] hover:text-[var(--text-1)] focus:outline-none"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <motion.button
            whileHover={!loading ? { scale: 1.02, boxShadow: '0 22px 44px rgba(30,30,30,0.20)' } : undefined}
            whileTap={!loading ? { scale: 0.97, boxShadow: '0 8px 20px rgba(30,30,30,0.12)' } : undefined}
            transition={{ type: 'spring', stiffness: 400, damping: 20 }}
            type="submit"
            disabled={loading}
            className="w-full h-[56px] rounded-full bg-[#1E1E1E] text-white hover:bg-[#292929] font-black text-sm tracking-[-0.01em] disabled:opacity-80 flex items-center justify-center gap-2 shadow-[0_18px_36px_rgba(30,30,30,0.16)]"
          >
            {loading ? (
              <>
                <RollerSpinner className="w-5 h-5 text-white" />
                <span>Signing in...</span>
              </>
            ) : (
              <>
                Sign in
              </>
            )}
          </motion.button>
        </form>
        </motion.div>

        <p className="pt-6 text-center text-xs font-medium text-[var(--text-3)]">
          Don&apos;t have an account?{' '}
          <Link href="/register" className="text-[var(--primary)] font-bold" onClick={clearError}>
            Create one
          </Link>
        </p>

        {/* Social login buttons */}
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
