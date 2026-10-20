import type { Metadata } from "next";
import Link from "next/link";
import { ContactForm } from "@/components/contact-form";
import { CONTACT_EMAIL, REPO_URL } from "@/lib/site";

export const metadata: Metadata = {
  title: "Contact",
  description: `Contact the Vector Agentic Skills team: request a skill, ask a question or partner with us. Email ${CONTACT_EMAIL}.`,
  alternates: { canonical: "/contact/" },
};

export default function ContactPage() {
  return (
    <>
      <div className="page-head">
        <div className="container">
          <nav className="crumbs" aria-label="Breadcrumb">
            <Link href="/">Home</Link> / <span>Contact</span>
          </nav>
          <h1>
            Get in <span className="hl">touch</span>
          </h1>
          <p className="sub">
            Request a skill, ask a question, report a problem or talk about a partnership. We usually reply within two
            working days.
          </p>
        </div>
      </div>
      <div className="container contact-grid contact-page">
        <div className="contact-panel">
          <h2>
            Vector Agentic Skills
            <span className="serif">Built by Vector AI Lab.</span>
          </h2>
          <ul className="contact-points">
            <li>
              <span>Email</span>
              <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
            </li>
            <li>
              <span>Skill requests and bugs</span>
              <a href={`${REPO_URL}/issues`} target="_blank" rel="noopener">
                GitHub issues
              </a>
            </li>
            <li>
              <span>Contribute a skill</span>
              <a href={`${REPO_URL}/blob/main/README.md#contributing`} target="_blank" rel="noopener">
                Contribution guide
              </a>
            </li>
            <li>
              <span>Company</span>
              <a href="https://vector-ai-lab.com" target="_blank" rel="noopener">
                vector-ai-lab.com
              </a>
            </li>
          </ul>
        </div>
        <div className="contact-card">
          <ContactForm />
        </div>
      </div>
    </>
  );
}
