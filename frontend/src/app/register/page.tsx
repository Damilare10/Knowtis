'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';
import { useAppStore } from '@/lib/store';

const RegisterMobile = dynamic(() => import('./mobile-page'), { ssr: false });
const RegisterDesktop = dynamic(() => import('./desktop-page'), { ssr: false });

export default function RegisterPage() {
  const router = useRouter();
  const { isAuthenticated } = useAppStore();
  const [isMobile, setIsMobile] = useState<boolean | null>(null);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 1024);
    };
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      router.replace('/onboarding/research');
    }
  }, [isAuthenticated, router]);

  if (isMobile === null) {
    return <main className="min-h-dvh bg-[#FBFBFA]" />;
  }

  if (isMobile) {
    return <RegisterMobile />;
  }

  return <RegisterDesktop />;
}