'use client';

import { useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAppStore } from '@/lib/store';
import { Loader2 } from 'lucide-react';

function CallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { checkAuth } = useAppStore();

  useEffect(() => {
    const token = searchParams.get('token');
    if (token) {
      localStorage.setItem('knowtis_token', token);
      checkAuth().then(() => {
        router.push('/dashboard');
      });
    } else {
      router.push('/login');
    }
  }, [router, searchParams, checkAuth]);

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center bg-[#FBFBFA] text-[#171717]">
      <Loader2 className="h-10 w-10 animate-spin text-[#FF5A36] mb-4" />
      <h2 className="text-xl font-bold tracking-tight">Authenticating...</h2>
      <p className="text-sm text-[#686862] mt-2">Setting up your Knowtis account.</p>
    </div>
  );
}

export default function CallbackPage() {
  return (
    <Suspense fallback={<div className="flex min-h-dvh items-center justify-center bg-[#FBFBFA]">Loading...</div>}>
      <CallbackContent />
    </Suspense>
  );
}
