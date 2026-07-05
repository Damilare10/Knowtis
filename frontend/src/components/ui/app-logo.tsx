import React from 'react';

export default function AppLogo({ className }: { className?: string }) {
  return (
    <svg 
      viewBox="0 0 100 100" 
      className={className} 
      fill="none" 
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <mask id="k-mask">
          <rect width="100" height="100" fill="white" />
          {/* Main top curve slit */}
          <path 
            d="M 33 60 C 33 42, 50 40, 64 22" 
            stroke="black" 
            strokeWidth="3.5" 
            fill="none" 
            strokeLinecap="round" 
          />
          {/* Lower right branch slit */}
          <path 
            d="M 52 64 L 67 82" 
            stroke="black" 
            strokeWidth="3.5" 
            fill="none" 
            strokeLinecap="round" 
          />
        </mask>
      </defs>

      <g mask="url(#k-mask)" fill="currentColor">
        {/* Circle (Head) */}
        <circle cx="32" cy="26" r="9" />
        
        {/* Main curved stem */}
        <path d="
          M 25 80
          V 60
          C 25 38, 48 36, 62 18
          H 75
          C 60 40, 41 42, 41 60
          V 80
          Z
        " />
        
        {/* Lower right branch */}
        <path d="
          M 44 60
          L 60 80
          H 75
          L 58 56
          C 53 50, 48 48, 48 48
          Z
        " />
      </g>
    </svg>
  );
}
