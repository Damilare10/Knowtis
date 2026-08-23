import React from 'react';
import Image from 'next/image';

export default function AppLogo({ className = 'h-8 w-8' }: { className?: string }) {
  return (
    <div className={`relative inline-block shrink-0 ${className}`}>
      <Image
        src="/knowtis-emblem.png"
        alt="Knowtis Logo"
        width={364}
        height={364}
        className="h-full w-full object-contain"
        priority
      />
    </div>
  );
}
