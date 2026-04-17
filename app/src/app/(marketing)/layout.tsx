import Image from "next/image";
import Link from "next/link";

export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <nav className="sticky top-0 z-50 flex items-center justify-between border-b border-[var(--color-border-light)] bg-white/95 px-5 py-3 backdrop-blur-md md:px-10">
        <Link href="/" className="flex items-center gap-2">
          <Image
            src="/logo.svg"
            alt="EggNest"
            width={160}
            height={32}
            className="block"
            priority
          />
        </Link>
        <div className="flex items-center gap-6">
          <Link
            href="/simulator"
            className="hidden text-sm font-medium text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-text)] sm:block"
          >
            Simulator
          </Link>
          <Link
            href="/employer"
            className="hidden text-sm font-medium text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-text)] sm:block"
          >
            Employer
          </Link>
          <Link
            href="/thesis"
            className="hidden text-sm font-medium text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-text)] sm:block"
          >
            Thesis
          </Link>
          <Link
            href="/simulator"
            className="rounded-full bg-gradient-golden px-5 py-2 text-sm font-semibold text-white shadow-[var(--shadow-md)] transition-all hover:-translate-y-0.5 hover:shadow-[var(--shadow-lg)]"
          >
            Open simulator
          </Link>
        </div>
      </nav>

      {children}

      <footer className="bg-[var(--color-gray-900)] px-6 py-12 text-[var(--color-gray-400)]">
        <div className="mx-auto grid max-w-5xl gap-8 md:grid-cols-[2fr_1fr]">
          <div>
            <span className="text-lg font-semibold text-white">EggNest</span>
            <p className="mt-2 max-w-xs text-sm leading-relaxed">
              Tax-aware scenario calculators for households and employers.
            </p>
          </div>
          <div className="flex gap-12">
            <div className="space-y-3">
              <h4 className="text-xs font-semibold uppercase tracking-widest text-white">
                Product
              </h4>
              <Link
                href="/simulator"
                className="block text-sm transition-colors hover:text-white"
              >
                Simulator
              </Link>
              <Link
                href="/employer"
                className="block text-sm transition-colors hover:text-white"
              >
                Employer
              </Link>
              <Link
                href="/thesis"
                className="block text-sm transition-colors hover:text-white"
              >
                Thesis
              </Link>
            </div>
            <div className="space-y-3">
              <h4 className="text-xs font-semibold uppercase tracking-widest text-white">
                Company
              </h4>
              <a
                href="mailto:hello@eggnest.co"
                className="block text-sm transition-colors hover:text-white"
              >
                Contact
              </a>
            </div>
          </div>
        </div>
        <div className="mx-auto mt-10 max-w-5xl border-t border-[var(--color-gray-700)] pt-6 text-center text-sm">
          <p>
            &copy; {new Date().getFullYear()} EggNest. Tax calculations powered
            by{" "}
            <a
              href="https://policyengine.org"
              target="_blank"
              rel="noopener"
              className="text-[var(--color-gold-light)] transition-colors hover:text-[var(--color-gold)] hover:underline"
            >
              PolicyEngine
            </a>
          </p>
          <p className="mx-auto mt-2 max-w-lg text-xs opacity-60">
            EggNest provides modeled outputs and scenario comparisons only. It
            does not provide financial, tax, legal, or compensation advice.
          </p>
        </div>
      </footer>
    </>
  );
}
