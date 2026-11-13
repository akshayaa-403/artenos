import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Ask the CRM",
  description: "Plain-English questions over a sales CRM, with measured accuracy, checked numbers and live telemetry.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a className="skip" href="#main">Skip to content</a>
        <header className="top">
          <Link href="/" className="brand">Ask the CRM</Link>
          <nav aria-label="Main">
            <Link href="/">Ask</Link>
            <Link href="/digest">Weekly summary</Link>
            <Link href="/results">Results</Link>
            <Link href="/telemetry">Telemetry</Link>
          </nav>
        </header>
        <main id="main">{children}</main>
        <footer className="foot">
          Public, synthetic data: every company, person and deal here is invented. This reproduces a method
          I used at a previous job; it is not that company&apos;s system, data or results.
        </footer>
      </body>
    </html>
  );
}
