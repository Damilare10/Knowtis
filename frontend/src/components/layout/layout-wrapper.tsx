'use client';
import React, { useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';
import { useAppStore } from '@/lib/store';
import { initPerformanceMode, usePerformanceMode } from '@/lib/performance-mode';
import Sidebar from './sidebar';
import BottomNav from './bottom-nav';
import { AnimatePresence, motion } from 'framer-motion';
import AppLogo from '@/components/ui/app-logo';
import { Capacitor } from '@capacitor/core';

const PUBLIC_PATHS = ['/', '/landing', '/login', '/register', '/terms', '/privacy', '/onboarding', '/onboarding/research', '/onboarding/performance-mode', '/onboarding/notifications'];
const FULLSCREEN_PATHS = ['/ai'];

export default function LayoutWrapper({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isPublic = PUBLIC_PATHS.some(p => p === '/' ? pathname === '/' : pathname.startsWith(p));
  const isFullscreen = FULLSCREEN_PATHS.some(p => pathname === p || pathname.startsWith(p + '/'));
  const { checkAuth, isAuthenticated, hasHydrated } = useAppStore();
  const isInitializing = !isPublic && !hasHydrated;
  const { performanceMode } = usePerformanceMode();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    if (hasHydrated) return;
    checkAuth();
  }, [checkAuth, hasHydrated]);

  useEffect(() => {
    if (!isPublic && hasHydrated && !isAuthenticated) {
      window.location.replace('/login');
    }
  }, [isPublic, hasHydrated, isAuthenticated]);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  useEffect(() => {
    initPerformanceMode();
  }, []);

  const reduced = performanceMode === 'low';
  const pageTransition: Record<string, unknown> = reduced
    ? { duration: 0.05, ease: [0.25, 0.1, 0.25, 1] }
    : { duration: 0.35, ease: [0.22, 1, 0.36, 1] };

  if (isPublic) {
    return <>{children}</>;
  }

  // In native app: don't show splash overlay if loader is hidden by RootRouter
  if (Capacitor.isNativePlatform()) {
    return (
      <>
        <div className="min-h-dvh flex relative">
          <div className="aurora-bg" aria-hidden="true">
            <div className="aurora-blob b1" />
            <div className="aurora-blob b2" />
            <div className="aurora-blob b3" />
          </div>
          <div className="aurora-grain" aria-hidden="true" />
          <Sidebar />
          <div className="relative z-10 flex-1 flex flex-col lg:pl-[260px] min-w-0 min-h-dvh bg-[#FBFBFA]">
            <AnimatePresence mode="wait">
              <motion.main
                key={pathname}
                initial={mounted ? (reduced ? false : { opacity: 0, y: 12, filter: 'blur(4px)' }) : false}
                animate={{ opacity: 1, y: 0, filter: reduced ? 'none' : 'blur(0px)' }}
                exit={reduced ? undefined : { opacity: 0, y: -12, filter: 'blur(4px)' }}
                transition={pageTransition}
                className="flex-1 px-5 pb-6 md:px-8 md:pt-6 md:pb-10 pb-nav"
                style={{ paddingTop: 'max(4px, env(safe-area-inset-top))' }}
                suppressHydrationWarning
              >
                {children}
              </motion.main>
            </AnimatePresence>
          </div>
          <BottomNav />
        </div>
      </>
    );
  }

  if (isFullscreen) {
    return <>{children}</>;
  }

  return (
    <>
      <AnimatePresence>
        {mounted && !reduced && isInitializing && !isPublic && (
          <motion.div
            key="splash"
            initial={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.1, ease: "easeIn" }}
            className="fixed inset-0 z-[100] flex items-center justify-center bg-white/80 backdrop-blur-lg"
            style={{ backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)' }}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0, filter: 'blur(4px)' }}
              animate={{ scale: 1, opacity: 1, filter: 'blur(0px)' }}
              transition={{ duration: 0.8, ease: "easeOut" }}
            >
              <AppLogo className="w-32 h-32 text-[#171717]" />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="min-h-dvh flex relative">
      <div className="aurora-bg" aria-hidden="true">
        <div className="aurora-blob b1" />
        <div className="aurora-blob b2" />
        <div className="aurora-blob b3" />
      </div>
      <div className="aurora-grain" aria-hidden="true" />

      {/* Desktop sidebar */}
      <Sidebar />

      {/* Main area */}
      <div className="relative z-10 flex-1 flex flex-col lg:pl-[260px] min-w-0 min-h-dvh bg-[#FBFBFA]">
        <AnimatePresence mode="wait">
          <motion.main
            key={pathname}
            initial={mounted ? (reduced ? false : { opacity: 0, y: 12, filter: 'blur(4px)' }) : false}
            animate={{ opacity: 1, y: 0, filter: reduced ? 'none' : 'blur(0px)' }}
            exit={reduced ? undefined : { opacity: 0, y: -12, filter: 'blur(4px)' }}
            transition={pageTransition}
            className="flex-1 px-5 pb-6 md:px-8 md:pt-6 md:pb-10 pb-nav"
            style={{ paddingTop: 'max(4px, env(safe-area-inset-top))' }}
            suppressHydrationWarning
          >
            {children}
          </motion.main>
        </AnimatePresence>
      </div>

      {/* Mobile floating bottom nav */}
      <BottomNav />
    </div>
    </>
  );
}
