'use client';
import React, { useEffect } from 'react';
import { usePathname } from 'next/navigation';
import { useAppStore } from '@/lib/store';
import Sidebar from './sidebar';
import BottomNav from './bottom-nav';
import { AnimatePresence, motion } from 'framer-motion';
import AppLogo from '@/components/ui/app-logo';

const PUBLIC_PATHS = ['/', '/login', '/register', '/onboarding'];
const FULLSCREEN_PATHS = ['/ai'];

export default function LayoutWrapper({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isPublic = PUBLIC_PATHS.some(p => p === '/' ? pathname === '/' : pathname.startsWith(p));
  const isFullscreen = FULLSCREEN_PATHS.some(p => pathname === p || pathname.startsWith(p + '/'));
  const { checkAuth, isAuthenticated, hasHydrated } = useAppStore();
  // Splash shows on protected routes until the auth session has hydrated.
  const isInitializing = !isPublic && !hasHydrated;

  useEffect(() => {
    if (isPublic || hasHydrated) return;
    checkAuth();
  }, [checkAuth, isPublic, hasHydrated]);

  // Redirect unauthenticated users away from protected routes after hydration.
  useEffect(() => {
    if (!isPublic && hasHydrated && !isAuthenticated) {
      window.location.replace('/login');
    }
  }, [isPublic, hasHydrated, isAuthenticated]);

  // Reset window scroll position on path change after render (prevents Framer Motion layoutId jump during scroll resets)
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  if (isPublic) {
    return <>{children}</>;
  }

  if (isFullscreen) {
    return <>{children}</>;
  }

  return (
    <>
      <AnimatePresence>
        {isInitializing && !isPublic && (
          <motion.div 
            key="splash"
            initial={{ opacity: 1 }}
            exit={{ opacity: 0, filter: 'blur(10px)', scale: 1.05 }}
            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
            className="fixed inset-0 z-[100] flex items-center justify-center bg-[#171717]"
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0, filter: 'blur(4px)' }}
              animate={{ scale: 1, opacity: 1, filter: 'blur(0px)' }}
              transition={{ duration: 0.8, ease: "easeOut" }}
            >
              <AppLogo className="w-20 h-20 text-[#F0EAD6]" />
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
            initial={{ opacity: 0, y: 12, filter: 'blur(4px)' }}
            animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
            exit={{ opacity: 0, y: -12, filter: 'blur(4px)' }}
            transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
            className="flex-1 px-5 pb-6 md:px-8 md:pt-6 md:pb-10 pb-nav"
            style={{ paddingTop: 'max(4px, env(safe-area-inset-top))' }}
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
