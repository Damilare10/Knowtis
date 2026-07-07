'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAppStore } from '@/lib/store';
import { User, Lock, Eye, EyeOff, ArrowLeft } from 'lucide-react';
import { motion } from 'framer-motion';
import { GOOGLE_OAUTH_URL } from '@/lib/api';

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

export default function LoginPage() {
  const router = useRouter();
  const { login, error, clearError, loading } = useAppStore();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !password) return;
    const ok = await login({ username: username.trim().toLowerCase(), password });
    if (ok) router.replace('/dashboard');
  };

  return (
    <main className="min-h-dvh bg-[#FBFBFA] text-[#171717] flex items-center justify-center overflow-hidden px-5">
      <section className="relative w-full max-w-[430px] flex flex-col">

        <header className="relative pb-8 flex items-center justify-center">
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
            whileHover={{ scale: 1.02, boxShadow: '0 22px 44px rgba(30,30,30,0.20)' }}
            whileTap={{ scale: 0.97, boxShadow: '0 8px 20px rgba(30,30,30,0.12)' }}
            transition={{ type: 'spring', stiffness: 400, damping: 20 }}
            type="submit"
            disabled={loading}
            className="w-full h-[56px] rounded-full bg-[#1E1E1E] text-white hover:bg-[#292929] font-black text-sm tracking-[-0.01em] disabled:opacity-50 flex items-center justify-center gap-2 shadow-[0_18px_36px_rgba(30,30,30,0.16)]"
          >
            {loading ? (
              <span className="skeleton-soft h-3 w-20 rounded-full" />
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
