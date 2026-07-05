/*
Animated Background Component - soft claymorphism ambience
*/
'use client';

import React from 'react';

export default function AnimatedBackground() {
  return (
    <div className="fixed inset-0 -z-50 overflow-hidden bg-[#FBFBFA] pointer-events-none">
      {/* Subtle grid texture */}
      <div 
        className="absolute inset-0 opacity-[0.025]" 
        style={{
          backgroundImage: 'radial-gradient(#1D1D1F 0.8px, transparent 0.8px)',
          backgroundSize: '20px 20px'
        }}
      />
      
      {/* Ambient orbs - very subtle */}
      <div 
        className="absolute top-[-8%] right-[-5%] w-[40vw] h-[40vw] rounded-full opacity-[0.16] blur-[100px] bg-[#FFE071] animate-float-1"
      />
      
      <div 
        className="absolute bottom-[-12%] left-[-8%] w-[45vw] h-[45vw] rounded-full opacity-[0.24] blur-[110px] bg-[#D9F1EC] animate-float-2"
      />
      
      <div 
        className="absolute top-[40%] left-[30%] w-[25vw] h-[25vw] rounded-full opacity-[0.14] blur-[90px] bg-[#F6B39F] animate-float-3"
      />
    </div>
  );
}
