'use client';

import React from 'react';
import { motion } from 'framer-motion';

const REVEAL_EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

export default function AILayout({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="fixed inset-0 flex flex-col"
      style={{ backgroundColor: '#FBFBFA' }}
    >
      {/* Clean glassmorphic overlay that fades out as the AI page settles */}
      <motion.div
        aria-hidden="true"
        initial={{ opacity: 1 }}
        animate={{ opacity: 0 }}
        transition={{ duration: 0.55, ease: REVEAL_EASE }}
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          background:
            'radial-gradient(circle at 50% 100%, rgba(255,255,255,0.85) 0%, rgba(255,255,255,0.55) 28%, rgba(255,255,255,0.2) 55%, transparent 78%)',
        }}
      />
      <div className="relative flex-1 flex justify-center overflow-hidden">
        <div className="w-full max-w-[860px] flex flex-col px-5 pt-4 pb-4 md:px-8 md:pt-6 md:pb-6">
          {children}
        </div>
      </div>
    </div>
  );
}