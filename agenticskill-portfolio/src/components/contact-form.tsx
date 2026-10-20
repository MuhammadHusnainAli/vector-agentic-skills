"use client";

import { useState } from "react";
import { CONTACT_EMAIL, CONTACT_FORM_KEY } from "@/lib/constants";
import { ArrowRight } from "./icons";

const TOPICS = ["General question", "Request a skill", "Submit a skill", "Report a problem", "Partnership"];

type Status = { kind: "idle" | "sending" | "sent" | "error"; title?: string; message?: string };

function mailtoHref(f: { name: string; email: string; topic: string; message: string }) {
  const subject = `[Vector Agentic Skills] ${f.topic}`;
  const body = `${f.message}\n\n— ${f.name} <${f.email}>`;
  return `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}

export function ContactForm() {
  const [form, setForm] = useState({ name: "", email: "", topic: TOPICS[0], message: "" });
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    if (data.get("botcheck")) return; // honeypot filled: silently ignore bots

    if (!CONTACT_FORM_KEY) {
      window.location.href = mailtoHref(form);
      setStatus({ kind: "sent", title: "Almost there", message: "Your email app should open with the message ready to send." });
      return;
    }

    setStatus({ kind: "sending" });
    try {
      const res = await fetch("https://api.web3forms.com/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          access_key: CONTACT_FORM_KEY,
          subject: `[Vector Agentic Skills] ${form.topic}`,
          from_name: "Vector Agentic Skills website",
          name: form.name,
          email: form.email,
          replyto: form.email,
          topic: form.topic,
          message: form.message,
        }),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok || !json.success) throw new Error(json.message || `HTTP ${res.status}`);
      setStatus({
        kind: "sent",
        title: "Message sent",
        message: "Thanks! Your message is on its way. We usually reply within two working days.",
      });
      setForm({ name: "", email: "", topic: TOPICS[0], message: "" });
    } catch {
      setStatus({ kind: "error", message: "We couldn't send that right now." });
    }
  };

  if (status.kind === "sent") {
    return (
      <div className="contact-done" role="status">
        <b>{status.title}</b>
        <p>{status.message}</p>
        <button type="button" className="btn btn-line btn-sm" onClick={() => setStatus({ kind: "idle" })}>
          Send another
        </button>
      </div>
    );
  }

  return (
    <form className="contact-form" onSubmit={submit}>
      <div className="field-row">
        <label className="field">
          <span>Name</span>
          <input name="name" required autoComplete="name" value={form.name} onChange={set("name")} placeholder="Your name" />
        </label>
        <label className="field">
          <span>Email</span>
          <input
            name="email"
            type="email"
            required
            autoComplete="email"
            value={form.email}
            onChange={set("email")}
            placeholder="you@company.com"
          />
        </label>
      </div>
      <label className="field">
        <span>Topic</span>
        <select name="topic" value={form.topic} onChange={set("topic")}>
          {TOPICS.map((t) => (
            <option key={t}>{t}</option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>Message</span>
        <textarea
          name="message"
          required
          minLength={10}
          rows={5}
          value={form.message}
          onChange={set("message")}
          placeholder="Tell us what you need: a skill idea, a question, or feedback."
        />
      </label>
      <input type="checkbox" name="botcheck" className="sr-only" tabIndex={-1} autoComplete="off" aria-hidden="true" />
      {status.kind === "error" && (
        <p className="form-error" role="alert">
          {status.message}{" "}
          <a href={mailtoHref(form)}>Email us directly instead</a>.
        </p>
      )}
      <div className="form-foot">
        <button type="submit" className="btn btn-brand" disabled={status.kind === "sending"}>
          {status.kind === "sending" ? "Sending…" : "Send message"} <ArrowRight />
        </button>
        <span>
          Or email <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
        </span>
      </div>
    </form>
  );
}
