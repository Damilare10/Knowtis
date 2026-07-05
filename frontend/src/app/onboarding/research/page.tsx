'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowRight, Check, Loader2 } from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const heardOptions = [
  { value: 'friend_or_classmate', label: 'Friend or classmate' },
  { value: 'whatsapp_group', label: 'WhatsApp group' },
  { value: 'instagram_tiktok_x', label: 'Instagram / TikTok / X' },
  { value: 'google_search', label: 'Google search' },
  { value: 'campaign', label: 'Campaign' },
  { value: 'other', label: 'Other' },
];

const useCaseOptions = [
  { value: 'assignment_deadlines', label: 'Assignment deadlines' },
  { value: 'exam_and_test_reminders', label: 'Exam and test reminders' },
  { value: 'lecture_changes', label: 'Lecture changes' },
  { value: 'daily_academic_briefings', label: 'Daily academic briefings' },
  { value: 'class_reminders', label: 'Class reminders' },
  { value: 'all_of_the_above', label: 'All of the above' },
];

type Step = 'heard' | 'use';

export default function ResearchOnboardingPage() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [step, setStep] = useState<Step>('heard');
  const [heardAbout, setHeardAbout] = useState('');
  const [primaryUseCase, setPrimaryUseCase] = useState('');
  const [otherText, setOtherText] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const storedToken = localStorage.getItem('knowtis_token');
    if (!storedToken) {
      router.replace('/onboarding');
      return;
    }

    setToken(storedToken);
    fetch(`${API_BASE}/api/v1/onboarding/research`, {
      headers: { Authorization: `Bearer ${storedToken}` },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((status) => {
        if (status?.completed) {
          router.replace('/calendar');
          return;
        }
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [router]);

  const canContinue = useMemo(() => {
    if (step === 'heard') return Boolean(heardAbout);
    return Boolean(primaryUseCase);
  }, [heardAbout, primaryUseCase, step]);

  const finish = async (skipped = false) => {
    if (!token || saving) return;
    setSaving(true);
    setError('');

    try {
      const res = await fetch(`${API_BASE}/api/v1/onboarding/research`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(
          skipped
            ? { skipped: true }
            : {
                heard_about: heardAbout,
                primary_use_case: primaryUseCase,
                other_text: heardAbout === 'other' ? otherText : undefined,
                skipped: false,
              },
        ),
      });

      if (!res.ok) throw new Error('Unable to save onboarding answers');
      router.replace('/calendar');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to save onboarding answers');
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <main className="flex min-h-dvh items-center justify-center bg-[#FBFBFA] text-[#171717]">
        <Loader2 className="h-8 w-8 animate-spin text-[#FF5A36]" />
      </main>
    );
  }

  const options = step === 'heard' ? heardOptions : useCaseOptions;
  const selected = step === 'heard' ? heardAbout : primaryUseCase;
  const setSelected = step === 'heard' ? setHeardAbout : setPrimaryUseCase;

  return (
    <main className="min-h-dvh bg-[#FBFBFA] px-5 py-8 text-[#171717]">
      <div className="mx-auto flex min-h-[calc(100dvh-64px)] w-full max-w-[440px] flex-col justify-center">
        <div className="mb-8">
          <p className="text-xs font-black uppercase tracking-[0.18em] text-[#FF5A36]">
            Quick setup · {step === 'heard' ? '1' : '2'} of 2
          </p>
          <h1 className="mt-3 text-[38px] font-black leading-[0.95] tracking-[-0.06em] text-[#171717]">
            Help us tune Knowtis.
          </h1>
          <p className="mt-4 text-sm font-semibold leading-6 text-[#686862]">
            Two quick research questions so we know what to improve first after launch.
          </p>
        </div>

        <section className="rounded-[30px] border border-[#E9E9E6] bg-white p-4 shadow-[0_24px_60px_rgba(30,30,30,0.08)]">
          <h2 className="px-1 text-lg font-black tracking-[-0.03em]">
            {step === 'heard' ? 'How did you hear about us?' : 'What will you use Knowtis for the most?'}
          </h2>

          <div className="mt-4 grid gap-2">
            {options.map((option) => {
              const active = selected === option.value;
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setSelected(option.value)}
                  className={`flex min-h-12 items-center justify-between rounded-2xl border px-4 py-3 text-left text-sm font-black transition ${
                    active
                      ? 'border-[#FF5A36] bg-[#FFF0EB] text-[#171717]'
                      : 'border-[#EFEFEB] bg-[#FBFBFA] text-[#5F5F59] hover:border-[#FFD8CD]'
                  }`}
                >
                  {option.label}
                  {active && <Check className="h-4 w-4 text-[#FF5A36]" />}
                </button>
              );
            })}
          </div>

          {step === 'heard' && heardAbout === 'other' && (
            <input
              value={otherText}
              onChange={(event) => setOtherText(event.target.value)}
              placeholder="Tell us where"
              maxLength={120}
              className="mt-3 h-12 w-full rounded-2xl border border-[#E9E9E6] bg-white px-4 text-sm font-semibold outline-none focus:border-[#FF5A36]"
            />
          )}

          {error && <p className="mt-3 text-sm font-bold text-[#D93618]">{error}</p>}
        </section>

        <div className="mt-5 flex gap-3">
          <button
            type="button"
            onClick={() => finish(true)}
            disabled={saving}
            className="h-12 rounded-full border border-[#E9E9E6] bg-white px-5 text-sm font-black text-[#686862] disabled:opacity-60"
          >
            Skip
          </button>
          <button
            type="button"
            disabled={!canContinue || saving}
            onClick={() => (step === 'heard' ? setStep('use') : finish(false))}
            className="flex h-12 flex-1 items-center justify-center gap-2 rounded-full bg-[#171717] px-5 text-sm font-black text-white shadow-[0_14px_30px_rgba(30,30,30,0.18)] disabled:cursor-not-allowed disabled:opacity-40"
          >
            {saving ? 'Saving...' : step === 'heard' ? 'Continue' : 'Finish setup'}
            {!saving && <ArrowRight className="h-4 w-4" />}
          </button>
        </div>

        <p className="mt-5 text-center text-[11px] font-semibold leading-5 text-[#9A9A94]">
          Your answers only help us understand launch channels and feature priorities.
        </p>
      </div>
    </main>
  );
}
