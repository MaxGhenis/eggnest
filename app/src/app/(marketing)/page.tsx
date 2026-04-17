import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "EggNest - Tax-aware calculators for households and employers",
  description:
    "Tax-aware scenario calculators for household planning and employer package design. Model outcomes under explicit assumptions with real tax and benefit rules.",
};

export default function HomePage() {
  return (
    <div className="w-full overflow-x-hidden">
      {/* Hero */}
      <section className="relative min-h-[85vh] overflow-hidden bg-[radial-gradient(ellipse_80%_60%_at_50%_0%,_#fef3c7_0%,_#fffbf5_50%,_#fef7ed_100%)]">
        {/* Decorative orbs */}
        <div className="pointer-events-none absolute -right-[10%] -top-[20%] h-[600px] w-[600px] rounded-full bg-[radial-gradient(circle,_var(--color-gold-pale)_0%,_transparent_70%)] opacity-60" />
        <div className="pointer-events-none absolute -bottom-[30%] -left-[15%] h-[800px] w-[800px] rounded-full bg-[radial-gradient(circle,_var(--color-primary-100)_0%,_transparent_70%)] opacity-40" />

        <div className="relative z-10 mx-auto max-w-7xl px-6 pb-16 pt-16 md:px-10 lg:flex lg:items-center lg:gap-12 lg:pt-20">
          {/* Text */}
          <div className="max-w-xl lg:flex-1">
            <h1
              className="text-[clamp(2.75rem,6vw,4.5rem)] font-medium leading-[1.08] text-[var(--color-text)]"
              style={{ letterSpacing: "-0.03em" }}
            >
              Model the numbers
              <br />
              before you decide.
            </h1>
            <p className="mt-6 max-w-md text-xl leading-relaxed text-[var(--color-text-muted)]">
              EggNest has two tax-aware product surfaces: the Simulator for
              household scenarios and the Employer calculator for package
              design. Both use explicit assumptions and real tax and benefit
              rules.
            </p>
            <div className="mt-8 flex flex-wrap gap-4">
              <Link
                href="/simulator"
                className="inline-flex items-center gap-2 rounded-full bg-gradient-golden px-8 py-4 text-base font-semibold text-white shadow-[var(--shadow-md),0_4px_20px_var(--color-primary-glow)] transition-all hover:-translate-y-0.5 hover:shadow-[var(--shadow-lg),0_8px_30px_rgba(234,88,12,0.3)]"
              >
                Open simulator
              </Link>
              <Link
                href="/employer"
                className="inline-flex items-center gap-2 rounded-full border-[1.5px] border-[var(--color-border)] bg-white px-8 py-4 text-base font-semibold text-[var(--color-text)] shadow-[var(--shadow-sm)] transition-all hover:border-[var(--color-primary-200)] hover:bg-[var(--color-primary-50)]"
              >
                Employer calculator
              </Link>
            </div>
          </div>

          {/* Chart preview */}
          <div className="mx-auto mt-12 w-full max-w-xl lg:mt-0 lg:flex-1">
            <div className="rounded-[var(--radius-xl)] border border-[var(--color-border-light)] bg-white p-6 shadow-[var(--shadow-xl),var(--shadow-glow)] md:p-8">
              <svg viewBox="0 0 420 240" className="w-full">
                <line x1="50" y1="20" x2="50" y2="200" stroke="#e5e7eb" strokeWidth="1" />
                <line x1="50" y1="200" x2="400" y2="200" stroke="#e5e7eb" strokeWidth="1" />
                <text x="15" y="110" fontSize="11" fill="#6b7280" transform="rotate(-90, 15, 110)">Net resources</text>
                <text x="225" y="230" fontSize="11" fill="#6b7280" textAnchor="middle">Future years</text>
                <text x="50" y="215" fontSize="10" fill="#9ca3af" textAnchor="middle">0</text>
                <text x="165" y="215" fontSize="10" fill="#9ca3af" textAnchor="middle">10</text>
                <text x="280" y="215" fontSize="10" fill="#9ca3af" textAnchor="middle">20</text>
                <text x="395" y="215" fontSize="10" fill="#9ca3af" textAnchor="middle">30</text>
                <path d="M 50 100 Q 120 90, 200 60 T 395 25 L 395 195 Q 280 180, 200 170 T 50 140 Z" fill="rgba(217, 119, 6, 0.1)" />
                <path d="M 50 115 Q 120 105, 200 80 T 395 50 L 395 175 Q 280 165, 200 155 T 50 130 Z" fill="rgba(217, 119, 6, 0.15)" />
                <path d="M 50 120 Q 150 110, 250 100 T 395 95" fill="none" stroke="#d97706" strokeWidth="3" strokeLinecap="round" />
                <g transform="translate(260, 50)">
                  <rect x="0" y="0" width="130" height="70" fill="white" rx="4" opacity="0.9" />
                  <rect x="10" y="12" width="20" height="3" fill="#d97706" />
                  <text x="35" y="16" fontSize="10" fill="#374151">Median outcome</text>
                  <rect x="10" y="30" width="20" height="8" fill="rgba(217, 119, 6, 0.25)" />
                  <text x="35" y="36" fontSize="10" fill="#374151">Likely range</text>
                  <rect x="10" y="48" width="20" height="8" fill="rgba(217, 119, 6, 0.1)" />
                  <text x="35" y="54" fontSize="10" fill="#374151">Possible range</text>
                </g>
                <text x="85" y="55" fontSize="10" fill="#d97706" fontWeight="500">10,000 simulations</text>
                <path d="M 130 60 L 150 80" stroke="#d97706" strokeWidth="1" fill="none" />
              </svg>
              <p className="mt-4 text-center text-sm italic text-[var(--color-text-muted)]">
                Each line is a possible future. Compare the tradeoffs before you choose.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Problem */}
      <section id="why" className="mx-auto max-w-[56rem] px-6 py-24 text-center md:py-28">
        <h2
          className="text-[clamp(2rem,4vw,2.75rem)] font-medium text-[var(--color-text)]"
          style={{ letterSpacing: "-0.02em" }}
        >
          Go beyond one-number calculators.
        </h2>
        <p className="mx-auto mt-6 max-w-[42rem] text-lg leading-relaxed text-[var(--color-text-muted)]">
          Most tools collapse everything into one answer. EggNest keeps the
          assumptions visible, models taxes and benefits explicitly, and lets
          you compare scenarios instead of treating the output like advice.
        </p>
        <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-2">
          {[
            {
              value: "Taxes + benefits",
              label:
                "A raise, move, or new child can change what you actually keep, not just your gross income.",
            },
            {
              value: "Scenarios, not guesses",
              label:
                "See the range of outcomes before you decide, instead of relying on a single projection.",
            },
          ].map(({ value, label }) => (
            <div
              key={value}
              className="rounded-[var(--radius-lg)] border border-[var(--color-border-light)] bg-white p-8 shadow-[var(--shadow-md)] transition-all hover:-translate-y-1 hover:shadow-[var(--shadow-lg)]"
            >
              <span className="block bg-gradient-golden bg-clip-text font-[var(--font-display)] text-[3.5rem] font-medium text-transparent" style={{ letterSpacing: "-0.02em" }}>
                {value}
              </span>
              <span className="mt-3 block text-base text-[var(--color-text-muted)]">
                {label}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-[72rem] px-6 py-8 md:py-12">
        <div className="grid gap-5 lg:grid-cols-[1.1fr_1.1fr_0.8fr]">
          {[
            {
              title: "Simulator",
              body: "Household simulator for retirement, life events, taxes, and historical or Monte Carlo comparisons.",
              href: "/simulator",
              cta: "Open simulator",
            },
            {
              title: "Employer surface",
              body: "Compensation package calculator for loaded employer cost, market position, and employee after-tax value.",
              href: "/employer",
              cta: "Open employer calculator",
            },
            {
              title: "Shared engine",
              body: "One tax-aware modeling stack underneath both surfaces, with explicit assumptions and reproducible outputs.",
            },
          ].map((item) => (
            <div
              key={item.title}
              className="rounded-[var(--radius-lg)] border border-[var(--color-border-light)] bg-white p-6 shadow-[var(--shadow-sm)]"
            >
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--color-primary)]">
                {item.title}
              </div>
              <p className="mt-3 text-base leading-relaxed text-[var(--color-text-muted)]">
                {item.body}
              </p>
              {"href" in item && item.href && item.cta ? (
                <Link
                  href={item.href}
                  className="mt-5 inline-flex items-center text-sm font-semibold text-[var(--color-primary)] transition-colors hover:text-[var(--color-primary-dark)]"
                >
                  {item.cta}
                </Link>
              ) : null}
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section
        id="features"
        className="relative bg-[var(--color-bg-alt)] px-6 py-24 md:py-28"
      >
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[var(--color-border)] to-transparent" />
        <h2
          className="text-center text-[clamp(2rem,4vw,2.75rem)] font-medium text-[var(--color-text)]"
          style={{ letterSpacing: "-0.02em" }}
        >
          What makes EggNest different
        </h2>
        <div className="mx-auto mt-12 grid max-w-[75rem] grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {[
            {
              icon: (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-6 w-6 text-[var(--color-primary)]">
                  <path d="M3 3v18h18" />
                  <path d="M7 16l4-4 4 4 5-6" />
                </svg>
              ),
              title: "10,000 simulations",
              desc: "Not one projection\u2014thousands. See the full range of what could happen across your household's financial future.",
            },
            {
              icon: (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-6 w-6 text-[var(--color-primary)]">
                  <rect x="3" y="3" width="18" height="18" rx="2" />
                  <path d="M3 9h18M9 21V9" />
                </svg>
              ),
              title: "Real tax calculations",
              desc: "Powered by PolicyEngine. Actual federal and state tax law\u2014not estimates. See your true after-tax position.",
            },
            {
              icon: (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-6 w-6 text-[var(--color-primary)]">
                  <circle cx="12" cy="12" r="9" />
                  <path d="M12 6v6l4 2" />
                </svg>
              ),
              title: "Life-event planning",
              desc: "Explore raises, marriage, children, relocation, and retirement with before-and-after scenario comparisons.",
            },
            {
              icon: (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-6 w-6 text-[var(--color-primary)]">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
              ),
              title: "Household planning",
              desc: "Model couples, dependents, and multiple decision-makers together\u2014different ages, incomes, and household rules included.",
            },
            {
              icon: (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-6 w-6 text-[var(--color-primary)]">
                  <path d="M12 2L2 7l10 5 10-5-10-5z" />
                  <path d="M2 17l10 5 10-5M2 12l10 5 10-5" />
                </svg>
              ),
              title: "Multiple income sources",
              desc: "Employment income, Social Security, pensions, portfolio drawdowns, and more. See how they interact with taxes over time.",
            },
            {
              icon: (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-6 w-6 text-[var(--color-primary)]">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
              ),
              title: "Retirement workflow",
              desc: "When retirement is the question, compare claiming ages, annuities, and drawdown paths with real numbers.",
            },
          ].map(({ icon, title, desc }) => (
            <div
              key={title}
              className="rounded-[var(--radius-lg)] border border-[var(--color-border-light)] bg-white p-6 shadow-[var(--shadow-sm)] transition-all hover:-translate-y-1 hover:border-[var(--color-primary-200)] hover:shadow-[var(--shadow-lg)]"
            >
              <div className="mb-4 flex h-[52px] w-[52px] items-center justify-center rounded-[var(--radius-md)] bg-gradient-sunrise shadow-[var(--shadow-sm)]">
                {icon}
              </div>
              <h3 className="mb-2 font-[var(--font-body)] text-lg font-semibold text-[var(--color-text)]">
                {title}
              </h3>
              <p className="text-[0.95rem] leading-relaxed text-[var(--color-text-muted)]">
                {desc}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="mx-auto max-w-[68rem] px-6 py-24 md:py-28">
        <h2
          className="text-center text-[clamp(2rem,4vw,2.75rem)] font-medium text-[var(--color-text)]"
          style={{ letterSpacing: "-0.02em" }}
        >
          How it works
        </h2>
        <div className="relative mt-14 grid grid-cols-1 gap-10 md:grid-cols-3 md:gap-12">
          {/* Connecting line (desktop) */}
          <div className="pointer-events-none absolute left-[calc(16.67%+24px)] right-[calc(16.67%+24px)] top-7 hidden h-0.5 bg-gradient-to-r from-[var(--color-primary-200)] via-[var(--color-gold-light)] to-[var(--color-primary-200)] md:block" />
          {[
            {
              num: "1",
              title: "Enter your household",
              desc: "Income, state, assets, and the scenario you want to test. Takes about 2 minutes.",
            },
            {
              num: "2",
              title: "We simulate 10,000 futures",
              desc: "Using historical market data plus actual tax and benefit rules to model your trajectory.",
            },
            {
              num: "3",
              title: "Compare the tradeoffs",
              desc: "See the distribution of outcomes, not just a single answer, before you make a decision.",
            },
          ].map(({ num, title, desc }) => (
            <div key={num} className="relative z-10 text-center">
              <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full bg-gradient-golden font-[var(--font-display)] text-2xl font-medium text-white shadow-[var(--shadow-md),0_4px_16px_var(--color-primary-glow)]">
                {num}
              </div>
              <h3 className="mb-2 font-[var(--font-body)] text-xl font-semibold text-[var(--color-text)]">
                {title}
              </h3>
              <p className="mx-auto max-w-[280px] text-base text-[var(--color-text-muted)]">
                {desc}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="relative overflow-hidden bg-gradient-golden px-6 py-20 text-center text-white md:py-24">
        <div className="pointer-events-none absolute -left-[20%] -top-[50%] h-[200%] w-[60%] bg-[radial-gradient(circle,rgba(255,255,255,0.1)_0%,transparent_60%)]" />
        <div className="pointer-events-none absolute -bottom-[50%] -right-[20%] h-[200%] w-[60%] bg-[radial-gradient(circle,rgba(255,255,255,0.08)_0%,transparent_60%)]" />
        <h2
          className="relative z-10 text-[clamp(2rem,4vw,2.75rem)] font-medium"
          style={{ letterSpacing: "-0.02em" }}
        >
          See the full picture before you decide.
        </h2>
        <p className="relative z-10 mt-4 text-lg opacity-90">
          Start with the simulator, or jump to the employer surface
          for package design and offer analysis.
        </p>
        <Link
          href="/simulator"
          className="relative z-10 mt-8 inline-block rounded-full bg-white px-10 py-4 text-lg font-semibold text-[var(--color-primary)] shadow-[var(--shadow-lg)] transition-all hover:bg-[var(--color-primary-50)] hover:shadow-[var(--shadow-xl)]"
        >
          Open simulator
        </Link>
      </section>
    </div>
  );
}
