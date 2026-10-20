"use client";

import { usePathname } from "next/navigation";
import { useLayoutEffect, useRef } from "react";

/**
 * The file popup changes the URL when it opens, switches files or closes. It calls
 * markPopupNavigation() first so the page behind it doesn't fade. A short time window
 * is used because the browser's popstate and React's update can arrive in either order.
 */
let popupUntil = 0;
export function markPopupNavigation() {
  popupUntil = performance.now() + 400;
}

/**
 * Fades page content in after a route change. The header and footer stay
 * still, and the new content starts partly visible so there is never a blank
 * frame between pages.
 */
export function PageFade({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const ref = useRef<HTMLDivElement>(null);
  const first = useRef(true);

  useLayoutEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    if (performance.now() < popupUntil) return;
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    ref.current?.animate([{ opacity: 0.35 }, { opacity: 1 }], {
      duration: 240,
      easing: "cubic-bezier(0.2, 0.8, 0.2, 1)",
    });
  }, [pathname]);

  return <div ref={ref}>{children}</div>;
}
