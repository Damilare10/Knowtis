import React, { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface YTPullToRefreshProps {
  onRefresh: () => Promise<void>;
  isRefreshing: boolean;
  children: React.ReactNode;
  className?: string;
}

export function YTPullToRefresh({
  onRefresh,
  isRefreshing,
  children,
  className = '',
}: YTPullToRefreshProps) {
  const [pullY, setPullY] = useState(0);
  const [touchStartY, setTouchStartY] = useState(0);
  const isDragging = useRef(false);

  const PULL_THRESHOLD = 65;

  const handleTouchStart = (e: React.TouchEvent) => {
    if (window.scrollY <= 0 && !isRefreshing) {
      setTouchStartY(e.touches[0].clientY);
      isDragging.current = true;
    }
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    if (!isDragging.current || isRefreshing || window.scrollY > 0) return;
    const currentY = e.touches[0].clientY;
    const diff = currentY - touchStartY;
    if (diff > 0) {
      const damped = Math.min(diff * 0.45, 90);
      setPullY(damped);
    }
  };

  const handleTouchEnd = () => {
    if (!isDragging.current) return;
    isDragging.current = false;

    if (pullY >= PULL_THRESHOLD && !isRefreshing) {
      onRefresh();
    }
    setPullY(0);
    setTouchStartY(0);
  };

  const visible = isRefreshing || pullY > 5;
  const progress = Math.min(pullY / PULL_THRESHOLD, 1);

  const translateY = isRefreshing
    ? 16
    : pullY > 0
    ? Math.min(pullY - 50, 24)
    : -70;

  return (
    <div
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
      className={`relative ${className}`}
    >
      {/* Floating YT-Music Style Refresh Indicator */}
      <AnimatePresence>
        {visible && (
          <motion.div
            initial={{ y: -70, opacity: 0, scale: 0.8 }}
            animate={{
              y: translateY,
              opacity: isRefreshing ? 1 : Math.min(pullY / 20, 1),
              scale: isRefreshing ? 1 : 0.6 + progress * 0.4,
            }}
            exit={{ y: -70, opacity: 0, scale: 0.8 }}
            transition={{
              type: 'spring',
              stiffness: 400,
              damping: 30,
              mass: 0.8,
            }}
            className="fixed top-[max(12px,env(safe-area-inset-top))] left-1/2 -translate-x-1/2 z-50 pointer-events-none"
          >
            <div className="flex items-center justify-center h-11 w-11 rounded-full bg-white dark:bg-[#1C1C1E] shadow-[0_8px_25px_rgba(0,0,0,0.18)] ring-1 ring-black/5 dark:ring-white/10">
              {isRefreshing ? (
                /* Vibrant Spinning Orange Indicator */
                <svg
                  className="animate-spin h-5 w-5 text-[#FF5A36]"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="3"
                  />
                  <path
                    className="opacity-90"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
              ) : (
                /* Pull Progress Orange Arc / Arrow */
                <div
                  className="flex items-center justify-center transition-transform duration-75"
                  style={{ transform: `rotate(${pullY * 4}deg)` }}
                >
                  <svg
                    className="h-5 w-5 text-[#FF5A36]"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M21.5 2v6h-6" />
                    <path d="M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
                  </svg>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Page Content (Remains Fixed) */}
      {children}
    </div>
  );
}
