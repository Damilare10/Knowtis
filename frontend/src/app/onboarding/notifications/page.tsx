'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { 
  Bell, 
  BellOff, 
  Check, 
  Sparkles, 
  Shield,
  AlertTriangle
} from 'lucide-react';
import { Capacitor } from '@capacitor/core';
import { LocalNotifications } from '@capacitor/local-notifications';

export default function NotificationsPage() {
  const router = useRouter();
  const [permissionState, setPermissionState] = useState<'granted' | 'denied' | 'default'>('default');
  const [isRequesting, setIsRequesting] = useState(false);

  useEffect(() => {
    async function checkPerm() {
      if (Capacitor.isNativePlatform()) {
        try {
          const perm = await LocalNotifications.checkPermissions();
          if (perm.display === 'granted') setPermissionState('granted');
          else if (perm.display === 'denied') setPermissionState('denied');
          else setPermissionState('default');
          return;
        } catch (e) {
          console.warn('Native notification check error:', e);
        }
      }
    }
    checkPerm();
  }, []);

  const handleEnableNotifications = async () => {
    setIsRequesting(true);
    let finalState: 'granted' | 'denied' | 'default' = 'default';

    try {
      if (Capacitor.isNativePlatform()) {
        const perm = await LocalNotifications.requestPermissions();
        if (perm.display === 'granted') {
          finalState = 'granted';
        } else if (perm.display === 'denied') {
          finalState = 'denied';
        }
      }
      
      setPermissionState(finalState);
      if (finalState === 'granted') {
        localStorage.setItem('knowtis_notifications_enabled', 'true');
      }
    } catch (error) {
      console.error('Notification permission error:', error);
    } finally {
      setIsRequesting(false);
      
      setTimeout(() => {
        router.replace('/onboarding/performance-mode');
      }, 800);
    }
  };

  const handleSkip = () => {
    router.replace('/onboarding/performance-mode');
  };

  const isGranted = permissionState === 'granted';
  const isDenied = permissionState === 'denied';

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
          <div className="mb-8">
            <motion.div
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: 'spring', stiffness: 150, damping: 15, delay: 0.2 }}
              className={`inline-flex items-center justify-center w-14 h-14 rounded-2xl flex items-center justify-center shadow-[inset_0_4px_8px_rgba(255,255,255,0.6),0_12px_24px_rgba(57,63,102,0.08)] ${
                isGranted ? 'bg-[#EAF8F0]' : 'bg-[#E7ECFF]'
              }`}
            >
              {isGranted ? (
                <Bell className="w-7 h-7 text-[#32B87B]" />
              ) : (
                <Bell className="w-7 h-7 text-[#3A4AA3]" />
              )}
            </motion.div>
          </div>

          <motion.h1
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="text-[22px] font-black leading-[1.1] tracking-tight text-[#171717] mb-2"
          >
            {isGranted ? 'Notifications enabled!' : 'Get deadline alerts on your terms'}
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.1 }}
            className="text-[13px] font-medium leading-relaxed text-[#686862] max-w-[300px] mx-auto"
          >
            {isGranted 
              ? "You'll receive urgent deadline changes and your Night Brief summary." 
              : "Allow notifications to get priority WhatsApp alerts when deadlines change, plus a consolidated Night Brief every evening."
            }
          </motion.p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="w-full max-w-[420px] mx-auto px-4 space-y-4"
        >
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.1 }}
            className="p-4 rounded-[16px] bg-white border border-[#E9E9E6] shadow-sm"
          >
            <div className="flex items-start gap-3">
              <div className="w-9 h-9 shrink-0 rounded-xl bg-[#FFF5E1] flex items-center justify-center text-[#F2A53C]">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div className="flex-1">
                <h3 className="text-[13px] font-black text-[#171717] mb-1">What you'll receive</h3>
                  <ul className="space-y-1.5 text-[12px] font-medium text-[#686862]">
                  <li className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#FF5A36] shrink-0" />
                    <span>Urgent deadline changes (instant WhatsApp alert)</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#F2A53C] shrink-0" />
                    <span>Night Brief summary (daily evening digest)</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#32B87B] shrink-0" />
                    <span>Class schedule changes</span>
                  </li>
                </ul>
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.2 }}
            className="p-4 rounded-[16px] bg-white border border-[#E9E9E6] shadow-sm"
          >
            <div className="flex items-start gap-3">
              <div className="w-9 h-9 shrink-0 rounded-xl bg-[#EAF8F0] flex items-center justify-center text-[#32B87B]">
                <Shield className="w-5 h-5" />
              </div>
              <div className="flex-1">
                <h3 className="text-[13px] font-black text-[#171717] mb-1">Privacy first</h3>
                <p className="text-[12px] font-medium text-[#686862] leading-relaxed">
                  No spam, no marketing. Only academic alerts you explicitly opted into. 
                  Manage preferences anytime in Settings → Notifications.
                </p>
              </div>
            </div>
          </motion.div>
        </motion.div>

        {isDenied && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.3 }}
            className="w-full max-w-[420px] mx-auto px-4 p-4 rounded-[16px] bg-[#FFF0EB] border border-[#FFD8CD]"
          >
            <div className="flex items-center gap-3 text-[13px] font-medium text-[#FF5A36]">
              <BellOff className="w-5 h-5 shrink-0" />
              <span>
                Notifications blocked. Enable in device settings to receive alerts.
              </span>
            </div>
          </motion.div>
        )}

        {isGranted && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ type: 'spring', stiffness: 300, damping: 20, delay: 0.4 }}
            className="w-full max-w-[420px] mx-auto px-4 p-5 rounded-[20px] bg-[#EAF8F0] border border-[#A7F3D0] text-center"
          >
            <div className="flex items-center justify-center gap-2 mb-2">
              <Check className="w-5 h-5 text-[#32B87B]" strokeWidth={3} />
              <span className="text-[16px] font-black text-[#1C8D5A]">All set!</span>
            </div>
            <p className="text-[13px] font-medium text-[#686862]">
              You'll now receive important deadline alerts.
            </p>
          </motion.div>
        )}
      </div>

      <footer className="shrink-0 px-6 pb-4 pt-2">
        {!isGranted ? (
          <motion.button
            whileHover={{ scale: 1.02, boxShadow: '0 22px 44px rgba(30,30,30,0.20)' }}
            whileTap={{ scale: 0.97, boxShadow: '0 8px 20px rgba(30,30,30,0.12)' }}
            transition={{ type: 'spring', stiffness: 400, damping: 20 }}
            onClick={handleEnableNotifications}
            disabled={isRequesting}
            className="w-full h-10 bg-[#171717] hover:bg-[#2c2c2c] text-white font-bold rounded-full flex items-center justify-center gap-2 text-sm shadow-[0_8px_16px_rgba(0,0,0,0.1)] active:scale-[0.98] transition-all disabled:cursor-not-allowed disabled:bg-[#171717]/30 disabled:shadow-none"
          >
            {isRequesting ? (
              <>
                <motion.span
                  animate={{ rotate: 360 }}
                  transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                  className="w-5 h-5 border-2 border-white border-t-transparent rounded-full"
                />
                <span>Allowing...</span>
              </>
            ) : (
              <>
                <Bell className="w-4 h-4" />
                <span>Allow Notifications</span>
              </>
            )}
          </motion.button>
        ) : (
          <motion.button
            whileHover={{ scale: 1.02, boxShadow: '0 22px 44px rgba(30,30,30,0.20)' }}
            whileTap={{ scale: 0.97, boxShadow: '0 8px 20px rgba(30,30,30,0.12)' }}
            transition={{ type: 'spring', stiffness: 400, damping: 20 }}
            onClick={handleSkip}
            className="w-full h-12 bg-[#171717] hover:bg-[#2c2c2c] text-white font-bold rounded-full flex items-center justify-center gap-2 text-sm shadow-[0_8px_16px_rgba(0,0,0,0.1)] active:scale-[0.98] transition-all"
          >
            <span>Continue</span>
          </motion.button>
        )}

        {!isGranted && (
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={handleSkip}
            className="w-full mt-2 h-9 text-[12px] font-bold text-[#9A9A94] hover:text-[#686862] transition-colors"
          >
            Skip for now
          </motion.button>
        )}
      </footer>
    </main>
  );
}