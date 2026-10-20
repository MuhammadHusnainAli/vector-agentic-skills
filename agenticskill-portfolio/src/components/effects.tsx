"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

/**
 * Page-wide behaviour that works on server-rendered HTML:
 * copy buttons inside rendered Markdown and table-of-contents highlighting.
 */
export function Effects() {
  const pathname = usePathname();

  useEffect(() => {
    const toc = document.querySelectorAll<HTMLAnchorElement>(".toc a");
    const heads = [...toc]
      .map((a) => document.getElementById(decodeURIComponent(a.hash.slice(1))))
      .filter(Boolean) as HTMLElement[];
    const io = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting);
        if (!visible.length) return;
        const id = visible[0].target.id;
        toc.forEach((a) => a.classList.toggle("active", a.hash === `#${id}`));
      },
      { rootMargin: "-90px 0px -70% 0px" },
    );
    heads.forEach((h) => io.observe(h));
    return () => io.disconnect();
  }, [pathname]);

  useEffect(() => {
    const onClick = async (e: MouseEvent) => {
      const btn = (e.target as HTMLElement).closest<HTMLButtonElement>("[data-copy]");
      if (!btn) return;
      const text = btn.dataset.copy || btn.closest("figure")?.querySelector("pre")?.innerText || "";
      try {
        await navigator.clipboard.writeText(text.replace(/\n$/, ""));
        const label = btn.textContent;
        btn.dataset.copied = "true";
        btn.textContent = "Copied";
        setTimeout(() => {
          btn.dataset.copied = "false";
          btn.textContent = label;
        }, 1600);
      } catch {
        // clipboard unavailable (insecure context); leave the button as is
      }
    };
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, []);

  return null;
}
