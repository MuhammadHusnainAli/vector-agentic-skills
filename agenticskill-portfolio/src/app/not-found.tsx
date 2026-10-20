import Link from "next/link";
import { ArrowRight } from "@/components/icons";

export default function NotFound() {
  return (
    <section className="hero hero-compact">
      <div className="container hero-inner">
        <span className="hero-badge">Error 404</span>
        <h1 className="hero-title">
          This page isn&apos;t in the index.
          <span className="serif">Let&apos;s find the right skill.</span>
        </h1>
        <div className="hero-cta">
          <Link href="/skills/" className="btn btn-cream">
            Browse skills <ArrowRight />
          </Link>
          <Link href="/" className="btn btn-ghost">
            Home
          </Link>
        </div>
      </div>
    </section>
  );
}
