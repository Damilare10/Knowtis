'use client';

import { useEffect } from 'react';
import { openAdminDashboard } from '@/lib/api';

export default function AdminRedirectPage() {
  useEffect(() => {
    openAdminDashboard();
  }, []);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-[#FBFBFA] p-6 text-center">
      <h1 className="text-2xl font-black text-[#171717] mb-2">Redirecting to Admin Dashboard...</h1>
      <p className="text-sm text-[#5F5F59] mb-4">If you are not redirected automatically, click the button below.</p>
      <button
        type="button"
        onClick={() => openAdminDashboard()}
        className="px-5 py-2.5 rounded-full bg-[#FF5A36] text-white font-bold text-sm shadow-md"
      >
        Open Standalone Admin Dashboard
      </button>
    </div>
  );
}
