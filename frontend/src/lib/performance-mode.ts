/*
Performance Mode System
Switches between high-res (full effects) and low-res (reduced backdrop-blur)
for mid-tier phones. Stored in localStorage.
*/
import { create } from 'zustand';

export type PerformanceMode = 'high' | 'low';

const PERF_MODE_KEY = 'knowtis_perf_mode';

interface PerformanceState {
  performanceMode: PerformanceMode;
  setPerformanceMode: (mode: PerformanceMode) => void;
}

export const usePerformanceMode = create<PerformanceState>((set) => ({
  performanceMode: (typeof window !== 'undefined' ? localStorage.getItem(PERF_MODE_KEY) as PerformanceMode : 'high') || 'high',
  setPerformanceMode: (mode: PerformanceMode) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(PERF_MODE_KEY, mode);
    }
    set({ performanceMode: mode });
    applyPerformanceMode(mode);
  },
}));

export function applyPerformanceMode(mode: PerformanceMode): void {
  if (typeof window === 'undefined') return;
  const html = document.documentElement;
  if (mode === 'low') {
    html.classList.add('perf-low');
  } else {
    html.classList.remove('perf-low');
  }
}

export function initPerformanceMode(): void {
  if (typeof window === 'undefined') return;
  const stored = localStorage.getItem(PERF_MODE_KEY) as PerformanceMode | null;
  applyPerformanceMode(stored || 'high');
}