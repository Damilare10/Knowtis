"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAppStore } from "@/lib/store";
import { motion } from "framer-motion";
import AppLogo from "@/components/ui/app-logo";
import { redirectToLanding } from "@/lib/landing";

/**
 * Entry point for both targets, so it only ever decides where to send the visitor.
 *
 * On native (Capacitor) this is the `index.html` the APK boots into, and it routes into the app
 * shell. On the web it sends signed-in users to their dashboard and everyone else to the static
 * marketing landing page. It renders the splash logo throughout, since every branch navigates
 * away.
 */
export default function RootRouter() {
  const router = useRouter();
  const { isAuthenticated, hasHydrated, user } = useAppStore();

  useEffect(() => {
    if (!hasHydrated) return;
    const runningInCapacitor = typeof window !== "undefined" && (
      Boolean((window as any).Capacitor?.isNativePlatform?.()) ||
      process.env.NEXT_PUBLIC_IS_CAPACITOR === "true"
    );

    // Hide native Capacitor plugin splash immediately so the Web 2nd splash (dark logo) takes over seamlessly
    if (runningInCapacitor && typeof window !== "undefined" && (window as any).Capacitor?.isNativePlatform?.()) {
      import("@capacitor/splash-screen").then(m => m.SplashScreen.hide()).catch(() => {});
    }

    const decide = () => {
      const onboarded = typeof window !== "undefined" && window.localStorage.getItem("knowtis_onboarded") === "true";

      if (runningInCapacitor) {
        if (!isAuthenticated) {
          router.replace(onboarded ? "/login" : "/onboarding");
        } else {
          router.replace(onboarded ? "/dashboard" : "/onboarding");
        }
      } else if (isAuthenticated) {
        // `knowtis_onboarded` is only set once onboarding completes, so a signed-in user can
        // still be mid-flow. Keep them in the app: the static landing page has no way back in.
        router.replace(onboarded ? "/dashboard" : "/onboarding");
      } else {
        // Web visitors without a session get the static HTML landing page.
        redirectToLanding();
      }
    };

    // Show 2nd splash screen with dark emblem logo for ~650ms before routing to destination page
    const timerDelay = runningInCapacitor ? 650 : 300;
    const timer = window.setTimeout(decide, timerDelay);

    return () => window.clearTimeout(timer);
  }, [router, isAuthenticated, hasHydrated, user]);

  return (
    <main className="flex min-h-dvh items-center justify-center bg-[#FBFBFA] text-[#171717] relative overflow-hidden">
      <div className="absolute inset-0" aria-hidden="true">
        <div className="aurora-bg">
          <div className="aurora-blob b1" />
          <div className="aurora-blob b2" />
          <div className="aurora-blob b3" />
        </div>
        <div className="aurora-grain" />
      </div>
      <motion.div
        initial={{ opacity: 0, scale: 0.88, filter: "blur(6px)" }}
        animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
        transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10 flex flex-col items-center gap-4"
      >
        <AppLogo className="w-32 h-32 md:w-36 md:h-36 text-[#171717]" />
      </motion.div>
    </main>
  );
}
