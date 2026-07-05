'use client';
import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  BellRinging, CalendarBlank, Clock, House, SignOut, Stack,
  UserCircle, Sparkle, WhatsappLogo,
} from '@phosphor-icons/react';
import { useAppStore } from '@/lib/store';
import { motion } from 'framer-motion';
import AppLogo from '@/components/ui/app-logo';

const PRIMARY_NAV = [
  { label: 'Home',      href: '/dashboard',     Icon: House         },
  { label: 'Updates',   href: '/updates',       Icon: Stack         },
  { label: 'Knowtis AI', href: '/ai',             Icon: Sparkle       },
  { label: 'Calendar',  href: '/calendar',       Icon: CalendarBlank },
  { label: 'Groups',    href: '/groups',         Icon: WhatsappLogo },
];

const SECONDARY_NAV = [
  { label: 'Alerts',    href: '/notifications',  Icon: BellRinging },
  { label: 'Reminders', href: '/reminders',     Icon: Clock        },
  { label: 'Profile',   href: '/profile',        Icon: UserCircle  },
];

interface NavItemProps {
  href: string;
  Icon: React.ElementType;
  label: string;
  active: boolean;
  onClose?: () => void;
}

function NavItem({ href, Icon, label, active, onClose }: NavItemProps) {
  const setAiPopupOpen = useAppStore((s) => s.setAiPopupOpen);

  const handleClick = (e: React.MouseEvent) => {
    if (href === '/ai') {
      e.preventDefault();
      setAiPopupOpen(true);
      onClose?.();
    } else {
      onClose?.();
    }
  };

  return (
    <Link
      href={href}
      onClick={handleClick}
      scroll={false}
      className={`relative flex items-center gap-3 px-3.5 py-2.5 rounded-[14px] text-sm font-semibold transition-colors duration-150 ${
        active ? 'text-white' : 'text-[var(--text-2)] hover:bg-[#FBFBFA] hover:text-[var(--text-1)]'
      }`}
    >
      {active && (
        <motion.div
          layoutId="sidebar-active"
          className="absolute inset-0 rounded-[14px] bg-[#171717] shadow-[0_4px_12px_rgba(30,30,30,0.1)]"
          transition={{ type: 'spring', stiffness: 600, damping: 40 }}
        />
      )}
      <Icon className={`relative z-10 h-[19px] w-[19px] transition-colors ${active ? 'text-white' : 'text-[var(--text-3)]'}`} weight={active ? 'fill' : 'duotone'} />
      <span className="relative z-10">{label}</span>
    </Link>
  );
}

interface SidebarProps { onClose?: () => void; }

export default function Sidebar({ onClose }: SidebarProps) {
  const pathname = usePathname();
  const { user, logout } = useAppStore();
  const name = user?.full_name ?? 'Student';
  const tier = user?.tier ?? 'free';

  const isActive = (href: string) => pathname === href || pathname.startsWith(href + '/');

  return (
    <aside className="hidden lg:flex fixed top-0 bottom-0 left-0 w-[260px] border-r border-[#E9E9E6] bg-white/80 backdrop-blur-xl z-40 flex-col overflow-hidden">
      {/* Logo */}
      <div className="h-[72px] flex items-center px-6">
        <Link href="/dashboard" onClick={onClose} scroll={false} className="flex items-center gap-3">
          <div className="relative w-8 h-8 rounded-[8px] shadow-sm flex items-center justify-center bg-[#171717] text-[#F0EAD6]">
            <AppLogo className="w-5 h-5" />
          </div>
          <span className="text-[17px] font-black lowercase tracking-[-0.05em] text-[#171717]">knowtis</span>
        </Link>
      </div>

      {/* Nav */}
      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        <p className="label text-[var(--text-3)] px-2 mb-2">Main</p>
        {PRIMARY_NAV.map(item => <NavItem key={item.href} {...item} active={isActive(item.href)} onClose={onClose} />)}

        <div className="my-3 border-t border-[var(--border-soft)]" />

        <p className="label text-[var(--text-3)] px-2 mb-2">More</p>
        {SECONDARY_NAV.map(item => <NavItem key={item.href} {...item} active={isActive(item.href)} onClose={onClose} />)}
      </nav>

      {/* User + logout */}
      <div className="p-4 border-t border-[#E9E9E6]">
        <div className="flex items-center gap-3 px-2 py-2 mb-2">
          <div className="w-9 h-9 rounded-[12px] bg-[#F4F3EF] flex items-center justify-center text-[#171717] text-sm font-black shrink-0 shadow-sm border border-[#E9E9E6]">
            {name.charAt(0)}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-bold text-[#171717] truncate">{name}</p>
            {tier === 'premium' ? (
              <span className="text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full inline-flex items-center gap-1 w-fit bg-[#FF5A36] text-white shadow-[0_4px_12px_rgba(255,90,54,0.25)]">
                <Sparkle className="h-2.5 w-2.5" weight="fill" />
                Premium
              </span>
            ) : (
              <span className="text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full inline-flex items-center gap-1 w-fit bg-[#FFF0EB] text-[#C83C21] border border-[#FFD8CD]">
                Free plan
              </span>
            )}
          </div>
        </div>
        <motion.button
          whileHover={{ scale: 1.02, backgroundColor: 'var(--danger-dim)' }}
          whileTap={{ scale: 0.97 }}
          transition={{ type: 'spring', stiffness: 400, damping: 20 }}
          onClick={() => { logout(); onClose?.(); }}
          className="w-full flex items-center gap-2.5 px-3.5 py-2.5 rounded-[14px] text-sm font-semibold text-[var(--danger)]"
        >
          <SignOut className="h-4 w-4" weight="duotone" />
          Sign Out
        </motion.button>
      </div>
    </aside>
  );
}
