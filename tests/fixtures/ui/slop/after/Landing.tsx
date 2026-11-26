// Redesign of ../Landing.tsx: one point of view (editorial, warm, precise), real claims, restrained system.
export default function Landing() {
  return (
    <main className="bg-paper text-ink font-sans">
      <header className="mx-auto max-w-6xl px-6 py-5 flex items-baseline justify-between border-b border-rule">
        <a href="/" className="font-display text-xl tracking-tight">Ledgerly</a>
        <a href="/login" className="text-sm underline underline-offset-4">Sign in</a>
      </header>
      <section className="mx-auto max-w-6xl px-6 pt-20 pb-16 grid gap-10 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <p className="text-sm font-medium text-accent">For finance teams of 5 to 50</p>
          <h1 className="mt-4 font-display text-5xl leading-[1.05] tracking-tight">
            Close the month in three days, with every number traced to its source.
          </h1>
          <p className="mt-6 max-w-[60ch] text-lg text-ink-subtle">
            Ledgerly matches bank lines to invoices overnight and flags the 3% that need a person. Your team reviews exceptions, not spreadsheets.
          </p>
          <div className="mt-8 flex gap-4">
            <a href="/demo" className="rounded-md bg-accent px-5 py-3 text-white hover:bg-accent-strong focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2">Book a 20-minute demo</a>
            <a href="/pricing" className="px-1 py-3 underline underline-offset-4">See pricing</a>
          </div>
        </div>
        <figure className="lg:col-span-5 border border-rule rounded-md bg-surface p-6">
          <img src="/product/exceptions-queue.png" alt="Exceptions queue showing 14 unmatched bank lines with suggested invoices" width="960" height="720" />
          <figcaption className="mt-3 text-sm text-ink-subtle">The exceptions queue: what's left after automatic matching.</figcaption>
        </figure>
      </section>
      <section className="mx-auto max-w-6xl px-6 py-16 border-t border-rule">
        <h2 className="font-display text-3xl">What changes in your close</h2>
        <dl className="mt-8 grid gap-x-12 gap-y-8 md:grid-cols-2">
          <div><dt className="font-medium">Matching runs every night</dt><dd className="mt-2 text-ink-subtle">Bank feeds from 30 banks, invoices from Xero or NetSuite.</dd></div>
          <div><dt className="font-medium">Every adjustment has an audit trail</dt><dd className="mt-2 text-ink-subtle">Who changed what, when, and the evidence attached.</dd></div>
          <div><dt className="font-medium">Exceptions come with a suggestion</dt><dd className="mt-2 text-ink-subtle">Likely invoice, confidence, and the reason it didn't auto-match.</dd></div>
          <div><dt className="font-medium">Your auditor gets read-only access</dt><dd className="mt-2 text-ink-subtle">No exporting folders of PDFs at year end.</dd></div>
        </dl>
      </section>
      <section className="mx-auto max-w-6xl px-6 py-16 border-t border-rule">
        <blockquote className="max-w-[60ch] font-display text-2xl leading-snug">
          "Our March close took 2.5 days. In January it took 9."
        </blockquote>
        <p className="mt-4 text-sm text-ink-subtle">Priya Raman, Financial Controller, Northwind Logistics (34-person finance team)</p>
      </section>
    </main>
  );
}
