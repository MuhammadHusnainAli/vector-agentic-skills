"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { REPO, SITE_URL } from "@/lib/constants";

type Line = { kind: "cmd" | "out" | "dim" | "ok"; text: string };

/** `category` is the plugin group (sub-category); `count` is how many skills that plugin installs. */
type Demo = { name: string; category: string; count: number };

const REDUCED = "(prefers-reduced-motion: reduce)";
function subscribeReduced(cb: () => void) {
  const mq = matchMedia(REDUCED);
  mq.addEventListener("change", cb);
  return () => mq.removeEventListener("change", cb);
}

function script({ name: skill, category, count }: Demo): Record<string, Line[]> {
  return {
    "npx skills": [
      { kind: "cmd", text: `npx skills add ${SITE_URL} --skill ${skill}` },
      { kind: "dim", text: "Fetching skill index..." },
      { kind: "ok", text: `✓ Installed ${skill}` },
      { kind: "dim", text: "Compatible with Claude Code, Codex, Cursor" },
      { kind: "cmd", text: "npx skills list" },
      { kind: "out", text: skill },
    ],
    "claude code": [
      { kind: "cmd", text: `/plugin marketplace add ${REPO}` },
      { kind: "ok", text: "✓ Marketplace vector-agentic-skills added" },
      { kind: "cmd", text: `/plugin install ${category}-skills@vector-agentic-skills` },
      { kind: "ok", text: `✓ ${count} skills enabled` },
      { kind: "cmd", text: `/${skill}` },
      { kind: "dim", text: "Loading skill instructions..." },
    ],
    curl: [
      { kind: "cmd", text: `curl -fsSL agenticskills.vector-ai-lab.com/dl/${skill}.tar.gz \\` },
      { kind: "out", text: "  | tar -xz -C ~/.claude/skills" },
      { kind: "ok", text: `✓ Extracted to ~/.claude/skills/${skill}` },
      { kind: "dim", text: "Restart your agent to load it" },
    ],
  };
}

export function Terminal({ skills }: { skills: Demo[] }) {
  const [tab, setTab] = useState("npx skills");
  const [skillIdx, setSkillIdx] = useState(0);
  const [typed, setShown] = useState(0); // characters revealed across all lines
  const reduced = useSyncExternalStore(subscribeReduced, () => matchMedia(REDUCED).matches, () => false);
  const skill = skills[skillIdx % skills.length] ?? { name: "sql-query-writer", category: "sql", count: 1 };
  const lines = script(skill)[tab];
  const total = lines.reduce((n, l) => n + l.text.length + 1, 0);
  const shown = reduced ? total : typed;
  const starts = lines.map((_, i) => lines.slice(0, i).reduce((n, l) => n + l.text.length + 1, 0));

  useEffect(() => {
    if (reduced) return;
    if (shown >= total) {
      const t = setTimeout(() => {
        setSkillIdx((i) => i + 1);
        setShown(0);
      }, 3200);
      return () => clearTimeout(t);
    }
    // Commands type out character by character; output lines appear at once.
    let pos = 0;
    let step = 1;
    for (const l of lines) {
      const end = pos + l.text.length + 1;
      if (shown < end) {
        step = l.kind === "cmd" ? 1 : end - shown;
        break;
      }
      pos = end;
    }
    const t = setTimeout(() => setShown((s) => Math.min(s + step, total)), step > 1 ? 260 : 28);
    return () => clearTimeout(t);
  }, [shown, total, lines, reduced]);

  return (
    <div className="terminal" aria-label="Install demo">
      <div className="terminal-head">
        <span>INSTALL DEMO</span>
        <span className="dots">
          <i />
          <i />
          <i />
        </span>
      </div>
      <div className="terminal-tabs" role="tablist">
        {Object.keys(script(skill)).map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={t === tab}
            onClick={() => {
              setTab(t);
              setShown(0);
            }}
          >
            {t}
          </button>
        ))}
      </div>
      <div className="terminal-body" aria-live="off">
        {lines.map((l, i) => {
          const budget = shown - starts[i];
          if (budget <= 0) return null;
          const visible = l.text.slice(0, budget);
          const typing = budget <= l.text.length;
          return (
            <div key={`${tab}-${i}`}>
              {l.kind === "cmd" && <span className="p">$ </span>}
              <span className={l.kind === "dim" ? "dim" : l.kind === "ok" ? "ok" : undefined}>{visible}</span>
              {typing && <span className="cursor" />}
            </div>
          );
        })}
        {shown >= total && (
          <div>
            <span className="p">$ </span>
            <span className="cursor" />
          </div>
        )}
      </div>
    </div>
  );
}
