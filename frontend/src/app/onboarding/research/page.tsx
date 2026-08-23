'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Check, 
  Sparkles, 
  BookOpen, 
  Calendar, 
  Bell, 
  Megaphone, 
  Users, 
  Search, 
  MessageSquare,
  Edit2
} from 'lucide-react';
import { authApi, onboardingApi } from '@/lib/api';

const HEARD_OPTIONS = [
  { value: 'friend', label: 'Friend or classmate', icon: Users },
  { value: 'social', label: 'Social media (TikTok, Twitter, Instagram)', icon: MessageSquare },
  { value: 'search', label: 'Search engine / App Store', icon: Search },
  { value: 'campus', label: 'Campus poster or flyer', icon: Megaphone },
  { value: 'other', label: 'Other', icon: Sparkles },
];

const USE_CASE_OPTIONS = [
  { value: 'assignments', label: 'Track assignments & deadlines', icon: BookOpen },
  { value: 'exams', label: 'Exam & quiz reminders', icon: Calendar },
  { value: 'schedule', label: 'Class schedule & timetable', icon: Bell },
  { value: 'announcements', label: 'Lecturer announcements', icon: Megaphone },
  { value: 'other', label: 'Other', icon: Sparkles },
];

export default function ResearchPage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState<'heard' | 'useCase'>('heard');
  const [heardAbout, setHeardAbout] = useState<string>('');
  const [heardOther, setHeardOther] = useState('');
  const [useCase, setUseCase] = useState<string>('');
  const [useCaseOther, setUseCaseOther] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSkipped, setIsSkipped] = useState(false);

  // Onboarding research state setup

  const handleNext = async () => {
    if (currentStep === 'heard' && !heardAbout) return;
    if (currentStep === 'useCase' && !useCase) return;
    
    if (currentStep === 'heard') {
      setCurrentStep('useCase');
    } else {
      await submitResearch();
    }
  };

  const handleSkip = async () => {
    setIsSkipped(true);
    await submitResearch();
  };

  const submitResearch = async () => {
    setIsSubmitting(true);
    try {
      const heardValue = heardAbout === 'other' ? heardOther : heardAbout;
      const useCaseValue = useCase === 'other' ? useCaseOther : useCase;
      
      await onboardingApi.saveResearch({
        heard_about: heardValue,
        primary_use_case: useCaseValue,
        skipped: isSkipped,
        other_text: (heardAbout === 'other' ? heardOther : '') + ' | ' + (useCase === 'other' ? useCaseOther : ''),
      });
      
      router.replace('/onboarding/notifications');
    } catch (error) {
      console.error('Failed to save research:', error);
      router.replace('/onboarding/notifications');
    } finally {
      setIsSubmitting(false);
    }
  };

  const isHeardSelected = (value: string) => heardAbout === value;
  const isUseCaseSelected = (value: string) => useCase === value;

  const canProceed = currentStep === 'heard' ? heardAbout.length > 0 : useCase.length > 0;

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

      <div className="flex-1 flex flex-col justify-start px-6 pb-8 overflow-y-auto">
        <div className="w-full max-w-[380px] mx-auto text-center pt-1">
          <AnimatePresence mode="wait">
            <motion.div
              key={currentStep}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2 }}
            >
              <h1 className="text-[22px] font-black leading-[1.1] tracking-tight text-[#171717] mb-2">
                {currentStep === 'heard' ? 'Where did you hear about Knowtis?' : 'What will you use Knowtis for?'}
              </h1>
              <p className="text-[13px] font-medium leading-relaxed text-[#686862] max-w-[300px] mx-auto">
                {currentStep === 'heard' 
                  ? 'Helps us understand how students find us.' 
                  : 'So we can prioritize the features you need most.'
                }
              </p>
            </motion.div>
          </AnimatePresence>
        </div>

        <AnimatePresence mode="popLayout">
          <motion.div
            key={currentStep}
            initial={{ opacity: 0, x: 30 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -30 }}
            transition={{ 
              x: { type: 'spring', stiffness: 300, damping: 30 }, 
              opacity: { duration: 0.3 }
            }}
            className="w-full max-w-[380px] mx-auto px-3 space-y-2"
          >
            {currentStep === 'heard' && (
              <>
                {HEARD_OPTIONS.map((option) => (
                  <motion.div
                    key={option.value}
                    whileHover={{ scale: 1.01 }}
                    whileTap={{ scale: 0.99 }}
                    onClick={(e) => { e.stopPropagation(); e.preventDefault(); setHeardAbout(option.value); }}
                    className={`relative w-full group p-3 rounded-[16px] border-2 transition-all duration-300 flex items-center gap-3 text-left cursor-pointer ${
                      isHeardSelected(option.value)
                        ? 'border-[#FF5A36] bg-[#FFF5F2] shadow-[0_8px_24px_rgba(255,90,54,0.15)]'
                        : 'border-[#E9E9E6] bg-white hover:border-[#FFB29F] hover:shadow-[0_4px_16px_rgba(0,0,0,0.04)]'
                    }`}
                  >
                    <motion.div
                      initial={false}
                      animate={{ 
                        scale: isHeardSelected(option.value) ? 1 : 0.9,
                        boxShadow: isHeardSelected(option.value) ? '0 0 0 3px #FF5A36, 0 8px 24px rgba(255,90,54,0.2)' : undefined
                      }}
                      transition={{ type: 'spring', stiffness: 300, damping: 20 }}
                      className="relative w-10 h-10 shrink-0 rounded-xl bg-gradient-to-br from-[#FF5A36] to-[#E54835] flex items-center justify-center shadow-[0_6px_16px_rgba(255,90,54,0.35)]"
                    >
                      <option.icon className="w-5 h-5 text-white fill-white/10" />
                      {isHeardSelected(option.value) && (
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
                      <h3 className="text-[14px] font-black text-[#171717]">{option.label}</h3>
                    </div>

                    {option.value === 'other' && isHeardSelected('other') && (
                      <input
                        type="text"
                        value={heardOther}
                        onClick={(e) => e.stopPropagation()}
                        onChange={(e) => setHeardOther(e.target.value)}
                        placeholder="Tell us more..."
                        className="ml-2 w-40 rounded-xl border border-[#FFB29F] bg-white py-2 px-3 text-sm font-semibold text-[#171717] outline-none focus:border-[#FF5A36] focus:ring-2 focus:ring-[#FF5A36]/10"
                        autoFocus
                      />
                    )}
                  </motion.div>
                ))}
              </>
            )}

            {currentStep === 'useCase' && (
              <>
                {USE_CASE_OPTIONS.map((option) => (
                  <motion.div
                    key={option.value}
                    whileHover={{ scale: 1.01 }}
                    whileTap={{ scale: 0.99 }}
                    onClick={(e) => { e.stopPropagation(); e.preventDefault(); setUseCase(option.value); }}
                    className={`relative w-full group p-3 rounded-[16px] border-2 transition-all duration-300 flex items-center gap-3 text-left cursor-pointer ${
                      isUseCaseSelected(option.value)
                        ? 'border-[#32B87B] bg-[#EAF8F0] shadow-[0_8px_24px_rgba(50,184,123,0.15)]'
                        : 'border-[#E9E9E6] bg-white hover:border-[#A7F3D0] hover:shadow-[0_4px_16px_rgba(0,0,0,0.04)]'
                    }`}
                  >
                    <motion.div
                      initial={false}
                      animate={{ 
                        scale: isUseCaseSelected(option.value) ? 1 : 0.9,
                        boxShadow: isUseCaseSelected(option.value) ? '0 0 0 3px #32B87B, 0 8px 24px rgba(50,184,123,0.2)' : undefined
                      }}
                      transition={{ type: 'spring', stiffness: 300, damping: 20 }}
                      className="relative w-12 h-12 shrink-0 rounded-xl bg-gradient-to-br from-[#32B87B] to-[#1C8D5A] flex items-center justify-center shadow-[0_6px_16px_rgba(50,184,123,0.35)]"
                    >
                      <option.icon className="w-5 h-5 text-white fill-white/10" />
                      {isUseCaseSelected(option.value) && (
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
                      <h3 className="text-[14px] font-black text-[#171717]">{option.label}</h3>
                    </div>

                    {option.value === 'other' && isUseCaseSelected('other') && (
                      <input
                        type="text"
                        value={useCaseOther}
                        onClick={(e) => e.stopPropagation()}
                        onChange={(e) => setUseCaseOther(e.target.value)}
                        placeholder="Tell us more..."
                        className="ml-2 w-40 rounded-xl border border-[#A7F3D0] bg-white py-2 px-3 text-sm font-semibold text-[#171717] outline-none focus:border-[#32B87B] focus:ring-2 focus:ring-[#32B87B]/10"
                        autoFocus
                      />
                    )}
                  </motion.div>
                ))}
              </>
            )}
          </motion.div>
        </AnimatePresence>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.2 }}
          className="w-full max-w-[420px] mx-auto px-4 mt-2 pt-2 border-t border-[#E9E9E6]"
        >
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={handleSkip}
            disabled={isSubmitting}
            className="w-full h-12 text-sm font-bold text-[#9A9A94] hover:text-[#686862] transition-colors"
          >
            Skip for now
          </motion.button>
        </motion.div>
      </div>

      <footer className="shrink-0 px-6 pb-2 pt-1">
        <motion.button
          whileHover={{ scale: 1.02, boxShadow: '0 22px 44px rgba(30,30,30,0.20)' }}
          whileTap={{ scale: 0.97, boxShadow: '0 8px 20px rgba(30,30,30,0.12)' }}
          transition={{ type: 'spring', stiffness: 400, damping: 20 }}
          onClick={handleNext}
          disabled={!canProceed || isSubmitting}
          className={`w-full h-12 rounded-full flex items-center justify-center gap-2 text-sm shadow-[0_8px_16px_rgba(0,0,0,0.1)] active:scale-[0.98] transition-all ${
            canProceed && !isSubmitting
              ? 'bg-[#171717] hover:bg-[#2c2c2c] text-white font-bold'
              : 'bg-[#171717]/30 text-white/50 font-bold cursor-not-allowed'
          }`}
        >
          {isSubmitting ? (
            <span className="skeleton-soft h-3 w-24 rounded-full" />
          ) : currentStep === 'heard' ? (
            <>Continue</>
          ) : (
            <>Continue</>
          )}
        </motion.button>
      </footer>
    </main>
  );
}