"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { redirectToLanding } from "@/lib/landing";

/**
 * `/landing` is kept only so the historical URL stays valid. The landing page itself is the
 * static `public/landing.html` document, so this route immediately hands off to it.
 *
 * This route is also bundled into the native app, where the static landing page is deliberately
 * absent. There, fall through to the root router so the visitor ends up in the app shell.
 */
export default function DedicatedLandingPage() {
  const router = useRouter();

  useEffect(() => {
    if (!redirectToLanding()) {
      router.replace("/");
    }
  }, [router]);

  return null;
}
