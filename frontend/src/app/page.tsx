"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

export default function RootRouter() {
  const router = useRouter();
  const [phase, setPhase] = useState<"checking" | "ready">("checking");

  useEffect(() => {
    const decide = () => {
      const token =
        typeof window !== "undefined"
          ? window.localStorage.getItem("knowtis_token")
          : null;
      const onboarded =
        typeof window !== "undefined"
          ? window.localStorage.getItem("knowtis_onboarded") === "true"
          : false;

      const next = token ? (onboarded ? "/dashboard" : "/onboarding/research") : "/onboarding";
      router.replace(next);
    };

    const timer = window.setTimeout(() => {
      setPhase("ready");
      decide();
    }, 50);

    return () => window.clearTimeout(timer);
  }, [router]);

  return (
    <main className="flex min-h-dvh items-center justify-center bg-[#FBFBFA] text-[#171717]">
      <div className="flex flex-col items-center gap-3">
        <Loader2 className="h-7 w-7 animate-spin text-[#FF5A36]" />
        {phase === "ready" && (
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#9A9A93]">
            Loading Knowtis
         </p>
        )}
     </div>
   </main>
  );
}
