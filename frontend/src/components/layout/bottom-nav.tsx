'use client';
import React, { useRef } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { CalendarBlank, House, Sparkle, Stack, UserCircle } from '@phosphor-icons/react';
import { motion } from 'framer-motion';
import { useAppStore } from '@/lib/store';

const TABS = [
  { label: 'Home',     href: '/dashboard', Icon: House          },
  { label: 'Updates',  href: '/updates',   Icon: Stack          },
  { label: 'Knowtis AI', href: '/ai',        Icon: Sparkle        },
  { label: 'Calendar', href: '/calendar',  Icon: CalendarBlank  },
  { label: 'Profile',  href: '/profile',   Icon: UserCircle     },
];

const NAVIGATE_DELAY_MS = 560;

export default function BottomNav() {
  const path = usePathname();
  const aiButtonRef = useRef<HTMLAnchorElement | null>(null);
  const setAiPopupOpen = useAppStore((s) => s.setAiPopupOpen);

  const handleAiClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    setAiPopupOpen(true);
  };

  return (
    <nav
      aria-label="Primary navigation"
      className="lg:hidden fixed left-0 right-0 z-50 flex justify-center bottom-nav-offset pointer-events-none"
    >
      <div
        className="pointer-events-auto flex items-end justify-between gap-1 mx-4 px-2.5 py-1.5
          bg-white/70 backdrop-blur-xl
          rounded-[32px]
          border border-white/80
          shadow-[0_24px_54px_rgba(0,0,0,0.1),inset_0_1px_1px_rgba(255,255,255,1)]"
        style={{ maxWidth: 410 }}
      >
        {TABS.map(({ label, href, Icon }, index) => {
          const active = path === href || path.startsWith(href + '/');
          const isCenter = index === 2;

          if (isCenter) {
            return (
              <div key={href} className="relative flex flex-col items-center justify-end px-1.5 pb-1 pt-1 min-w-[52px]">
                {/* 72px Cutout Background */}
                <div className="absolute bottom-[16px] left-1/2 -translate-x-1/2 w-[64px] h-[64px] rounded-full bg-[#FBFBFA]/50 backdrop-blur-md" />

                {/* 52px Central Action Button */}
                <motion.div
                  whileHover={{ scale: 1.06 }}
                  whileTap={{ scale: 0.9 }}
                  transition={{ type: 'spring', stiffness: 500, damping: 18 }}
                  className="absolute bottom-[24px] left-1/2 -translate-x-1/2"
                >
                  <Link
                    ref={aiButtonRef}
                    href={href}
                    onClick={handleAiClick}
                    aria-label={label}
                    scroll={false}
                    className="flex items-center justify-center w-[46px] h-[46px] rounded-full bg-[#171717] text-white shadow-[0_16px_32px_rgba(23,23,23,0.3),inset_0_1px_1px_rgba(255,255,255,0.2)]"
                  >
                    <Icon className="h-5 w-5" weight="fill" />
                  </Link>
                </motion.div>
              </div>
            );
          }

          return (
            <Link
              key={href}
              href={href}
              aria-label={label}
              scroll={false}
              className="relative flex flex-col items-center justify-center gap-0.5 px-2 py-2 rounded-[22px] min-w-[52px] transition-colors duration-150"
            >
              {active && (
                <motion.div
                  layoutId="nav-pill"
                  className="absolute inset-0 rounded-[22px] bg-[var(--text-1)]"
                  transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                />
              )}
              <Icon
                className={`relative z-10 h-5 w-5 transition-colors ${active ? 'text-white' : 'text-[var(--text-3)]'}`}
                weight={active ? 'fill' : 'duotone'}
              />
              <span className={`relative z-10 text-[10px] font-extrabold tracking-wide transition-colors ${active ? 'text-white' : 'text-[var(--text-3)]'}`}>
                {label}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}