"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import { ADSENSE_CLIENT, ADSENSE_SLOT } from "@/lib/constants";

declare global {
  interface Window {
    adsbygoogle?: unknown[];
  }
}

/**
 * One responsive AdSense display unit, aligned to the page container. It reserves its height so
 * the layout does not jump when the ad loads, hides itself when AdSense has no ad to show
 * (data-ad-status="unfilled", see globals.css), and asks for a fresh ad on every client-side
 * route change. Renders nothing until NEXT_PUBLIC_ADSENSE_SLOT is set at build time.
 */
export function AdSlot() {
  const pathname = usePathname();
  if (!ADSENSE_SLOT) return null;
  // A new <ins> per route: AdSense fills each element once.
  return <AdUnit key={pathname} />;
}

function AdUnit() {
  const ref = useRef<HTMLModElement>(null);

  useEffect(() => {
    // Strict Mode runs effects twice in development; push only for an unfilled element.
    if (!ref.current || ref.current.dataset.adsbygoogleStatus) return;
    try {
      (window.adsbygoogle = window.adsbygoogle || []).push({});
    } catch {
      // Ad blockers or a missing script: leave the reserved space empty (hidden by CSS).
    }
  }, []);

  return (
    <aside className="ad-slot container" aria-label="Advertisement">
      <span className="ad-label">Advertisement</span>
      <ins
        ref={ref}
        className="adsbygoogle"
        style={{ display: "block" }}
        data-ad-client={ADSENSE_CLIENT}
        data-ad-slot={ADSENSE_SLOT}
        data-ad-format="auto"
        data-full-width-responsive="true"
        {...(process.env.NODE_ENV === "development" ? { "data-adtest": "on" } : {})}
      />
    </aside>
  );
}
