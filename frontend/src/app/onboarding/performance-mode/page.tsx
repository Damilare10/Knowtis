'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { 
  Battery, 
  Zap, 
  Cpu, 
  Check,
  BatteryLow
} from 'lucide-react';
import { usePerformanceMode } from '@/lib/performance-mode';

export default function PerformanceModePage() {
  const router = useRouter();
  const { performanceMode, setPerformanceMode } = usePerformanceMode();

  // Onboarding performance-mode page

  const handleSelectMode = (mode: 'high' | 'low') => {
    setPerformanceMode(mode);
    window.localStorage.setItem('knowtis_onboarded', 'true');
    router.replace('/dashboard');
  };

  return (
    <main
      className="min-h-dvh bg-[#FBFBFA] text-[#171717] flex flex-col justify-between overflow-x-hidden overflow-y-auto"
      style={{
        paddingTop: 'max(16px, env(safe-area-inset-top, 16px))',
        paddingBottom: 'max(16px, env(safe-area-inset-bottom, 16px))',
      }}
    >
      <header className="relative px-6 pt-2 pb-2 flex items-center justify-between shrink-0">
        <div className="w-10" />
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="inline-flex items-baseline gap-1 text-[18px] font-extrabold tracking-[-0.05em] lowercase mx-auto"
        >
          <span>know</span>
          <span className="text-[#FF5A36]">tis</span>
        </motion.div>
        <div className="w-10" />
      </header>

      <div className="flex-1 flex flex-col justify-start px-6 pb-20 overflow-y-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="w-full max-w-[380px] mx-auto text-center pt-2"
        >


          <h1 className="text-[22px] font-black leading-[1.1] tracking-tight text-[#171717] mb-2">
            Choose your performance mode
          </h1>
          <p className="text-[13px] font-medium leading-relaxed text-[#686862] max-w-[300px] mx-auto">
            High quality gives you the full visual experience. Low performance mode is for low tier and mid tier phones, reducing motion and blur effects.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="w-full max-w-[380px] mx-auto px-3 space-y-3"
        >
          {/* High Performance Option */}
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => handleSelectMode('high')}
            className={`relative w-full group p-4 rounded-[20px] border-2 transition-all duration-300 flex items-center gap-3 text-left ${
              performanceMode === 'high'
                ? 'border-[#FF5A36] bg-[#FFF5F2] shadow-[0_12px_32px_rgba(255,90,54,0.15)]'
                : 'border-[#E9E9E6] bg-white hover:border-[#FFB29F] hover:shadow-[0_8px_24px_rgba(0,0,0,0.06)]'
            }`}
          >
            <motion.div
              initial={false}
              animate={{ 
                scale: performanceMode === 'high' ? 1 : 0.9,
                boxShadow: performanceMode === 'high' ? '0 0 0 3px #FF5A36, 0 8px 24px rgba(255,90,54,0.2)' : undefined
              }}
              transition={{ type: 'spring', stiffness: 300, damping: 20 }}
              className="relative w-14 h-14 shrink-0 rounded-2xl bg-gradient-to-br from-[#FF5A36] to-[#E54835] flex items-center justify-center shadow-[0_8px_20px_rgba(255,90,54,0.35)]"
            >
              <Zap className="w-7 h-7 text-white fill-white/10" />
              {performanceMode === 'high' && (
                <motion.div
                  initial={{ scale: 0, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ type: 'spring', stiffness: 400, damping: 15 }}
                  className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-white border-2 border-[#FF5A36] flex items-center justify-center"
                >
                  <Check className="w-3 h-3 text-[#FF5A36]" strokeWidth={4} />
                </motion.div>
              )}
            </motion.div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <h3 className="text-[16px] font-black text-[#171717]">High Performance</h3>
                {performanceMode === 'high' && (
                  <motion.span
                    initial={{ opacity: 0, scale: 0.5 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ type: 'spring', stiffness: 400, damping: 20 }}
                    className="px-2 py-0.5 rounded-full text-[10px] font-black bg-[#FF5A36] text-white"
                  >
                    Selected
                  </motion.span>
                )}
              </div>
              <p className="text-[13px] font-medium text-[#686862] leading-relaxed">
                Full motion, blur effects, and smooth animations. Best for modern devices.
              </p>
              <div className="mt-3 flex items-center gap-2 text-[11px] font-bold text-[#74736D]">
                <Zap className="w-3.5 h-3.5 text-[#FF5A36]" />
                <span>Smooth 60fps animations</span>
                <span className="w-px h-4 bg-[#E9E9E6]" />
                <Battery className="w-3.5 h-3.5" />
                <span>Normal battery usage</span>
              </div>
            </div>
          </motion.button>

          {/* Low Performance Option */}
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => handleSelectMode('low')}
            className={`relative w-full group p-4 rounded-[20px] border-2 transition-all duration-300 flex items-center gap-3 text-left ${
              performanceMode === 'low'
                ? 'border-[#32B87B] bg-[#EAF8F0] shadow-[0_12px_32px_rgba(50,184,123,0.15)]'
                : 'border-[#E9E9E6] bg-white hover:border-[#A7F3D0] hover:shadow-[0_8px_24px_rgba(0,0,0,0.06)]'
            }`}
          >
            <motion.div
              initial={false}
              animate={{ 
                scale: performanceMode === 'low' ? 1 : 0.9,
                boxShadow: performanceMode === 'low' ? '0 0 0 3px #32B87B, 0 8px 24px rgba(50,184,123,0.2)' : undefined
              }}
              transition={{ type: 'spring', stiffness: 300, damping: 20 }}
              className="relative w-14 h-14 shrink-0 rounded-2xl bg-gradient-to-br from-[#32B87B] to-[#1C8D5A] flex items-center justify-center shadow-[0_8px_20px_rgba(50,184,123,0.35)]"
            >
              <BatteryLow className="w-7 h-7 text-white fill-white/10" />
              {performanceMode === 'low' && (
                <motion.div
                  initial={{ scale: 0, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ type: 'spring', stiffness: 400, damping: 15 }}
                  className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-white border-2 border-[#32B87B] flex items-center justify-center"
                >
                  <Check className="w-3 h-3 text-[#32B87B]" strokeWidth={4} />
                </motion.div>
              )}
            </motion.div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <h3 className="text-[16px] font-black text-[#171717]">Low Performance Mode</h3>
                {performanceMode === 'low' && (
                  <motion.span
                    initial={{ opacity: 0, scale: 0.5 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ type: 'spring', stiffness: 400, damping: 20 }}
                    className="px-2 py-0.5 rounded-full text-[10px] font-black bg-[#32B87B] text-white"
                  >
                    Selected
                  </motion.span>
                )}
              </div>
              <p className="text-[13px] font-medium text-[#686862] leading-relaxed">
                Reduces motion, disables backdrop blur, and limits animations. Designed for low tier and mid tier phones.
              </p>
              <div className="mt-3 flex items-center gap-2 text-[11px] font-bold text-[#74736D]">
                <BatteryLow className="w-3.5 h-3.5 text-[#32B87B]" />
                <span>For low tier and mid tier phones</span>
                <span className="w-px h-4 bg-[#E9E9E6]" />
                <Zap className="w-3.5 h-3.5 text-[#9A9A94]" />
                <span>Reduced motion effects</span>
              </div>
            </div>
          </motion.button>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.5 }}
          className="w-full max-w-[420px] mx-auto px-4 mt-8 pt-4 border-t border-[#E9E9E6]"
        >
          <p className="text-center text-[12px] font-medium text-[#9A9A94]">
            You can change this anytime in Settings → Performance
          </p>
        </motion.div>
      </div>

      <footer className="shrink-0 px-6 pb-4 pt-2">
        <motion.button
          whileHover={{ scale: 1.02, boxShadow: '0 22px 44px rgba(30,30,30,0.20)' }}
          whileTap={{ scale: 0.97, boxShadow: '0 8px 20px rgba(30,30,30,0.12)' }}
          transition={{ type: 'spring', stiffness: 400, damping: 20 }}
          onClick={() => handleSelectMode(performanceMode)}
          className="w-full h-10 bg-[#171717] hover:bg-[#2c2c2c] text-white font-bold rounded-full flex items-center justify-center gap-2 text-sm shadow-[0_8px_16px_rgba(0,0,0,0.1)] active:scale-[0.98] transition-all"
        >
          <span>Continue with {performanceMode === 'high' ? 'High Performance' : 'Low Performance Mode'}</span>
          <Zap className="w-4 h-4" />
        </motion.button>
      </footer>
    </main>
  );
}