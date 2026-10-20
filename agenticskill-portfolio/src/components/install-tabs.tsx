"use client";

import { useState } from "react";
import { installCommands } from "@/lib/constants";

const TABS = [
  { id: "npx", label: "npx skills", note: "Works with Claude Code, Codex, Cursor, Gemini CLI and 70+ other agents. Add -g to install globally, -a claude-code to pick an agent." },
  { id: "claude", label: "Claude Code plugin", note: "Run inside Claude Code. Installs every skill in this sub-category as one plugin, with updates." },
  { id: "curl", label: "curl", note: "No Node or git needed. Downloads the skill folder straight into your skills directory." },
] as const;

export function CopyCommand({ command }: { command: string }) {
  return (
    <div className="cmd">
      <pre>{command}</pre>
      <button type="button" className="copy-btn" data-copy={command}>
        Copy
      </button>
    </div>
  );
}

export function InstallTabs({ skill, subcategory }: { skill: string; subcategory: string }) {
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("npx");
  const cmds = installCommands(skill, subcategory);
  const current = TABS.find((t) => t.id === tab)!;
  return (
    <div className="tabs">
      <div className="tablist" role="tablist" aria-label="Install method">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={t.id === tab} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>
      <div className="tabpanel" role="tabpanel">
        <p>{current.note}</p>
        <CopyCommand command={cmds[tab]} />
      </div>
    </div>
  );
}
