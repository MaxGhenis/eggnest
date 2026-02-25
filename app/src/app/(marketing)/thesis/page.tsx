"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import styles from "./thesis.module.css";

type Section =
  | "problem"
  | "vision"
  | "phases"
  | "unlock"
  | "market"
  | "competition"
  | "model"
  | "gtm"
  | "team"
  | "risks";

type CompetitorCategory = "dedicated" | "robo" | "fire" | "advisor";

interface Competitor {
  name: string;
  category: CompetitorCategory;
  pricing: string;
  monteCarlo: boolean;
  realTaxes: boolean;
  benefitsModeling: boolean;
  openSource: boolean;
  strengths: string[];
  gaps: string[];
  url?: string;
}

const sections: Section[] = [
  "problem",
  "vision",
  "phases",
  "unlock",
  "market",
  "competition",
  "model",
  "gtm",
  "team",
  "risks",
];

const competitors: Competitor[] = [
  {
    name: "MaxiFi",
    category: "dedicated",
    pricing: "$109\u2013149/yr",
    monteCarlo: false,
    realTaxes: false,
    benefitsModeling: false,
    openSource: false,
    strengths: [
      "Economist-backed (Laurence Kotlikoff)",
      "Living standard optimization focus",
      "Roth conversion optimizer",
      "Social Security strategies",
    ],
    gaps: [
      "No Monte Carlo (deterministic)",
      "Tax estimates not actual law",
      "Complex, academic UI",
      "Closed source methodology",
    ],
    url: "https://maxifi.com",
  },
  {
    name: "Boldin (NewRetirement)",
    category: "dedicated",
    pricing: "Free\u2013$144/yr",
    monteCarlo: true,
    realTaxes: false,
    benefitsModeling: false,
    openSource: false,
    strengths: [
      "250+ input fields for detailed modeling",
      "Modern, approachable UI",
      "Optional CFP advisor access",
      "Strong community forums",
    ],
    gaps: [
      "Tax estimates, not actual law",
      "No benefit cliff modeling",
      "Premium features paywalled",
    ],
    url: "https://boldin.com",
  },
  {
    name: "ProjectionLab",
    category: "dedicated",
    pricing: "Free\u2013$109/yr",
    monteCarlo: true,
    realTaxes: false,
    benefitsModeling: false,
    openSource: false,
    strengths: [
      "Beautiful, modern visualization",
      "Excellent what-if scenarios",
      "Good for tech-savvy users",
      "Active development",
    ],
    gaps: [
      "State tax modeling is estimates",
      "No benefits integration",
      "Smaller user community",
    ],
    url: "https://projectionlab.com",
  },
  {
    name: "Pralana",
    category: "dedicated",
    pricing: "$99\u2013119/yr",
    monteCarlo: true,
    realTaxes: false,
    benefitsModeling: false,
    openSource: false,
    strengths: [
      "Extremely detailed analysis",
      "Excel-based (power user flexibility)",
      "Historical simulation option",
      "Strong tax bracket optimization",
    ],
    gaps: [
      "Steep learning curve",
      "Excel dependency limits accessibility",
      "No web/mobile app",
      "No real-time tax law updates",
    ],
    url: "https://pralana.com",
  },
  {
    name: "WealthTrace",
    category: "dedicated",
    pricing: "~$250/yr",
    monteCarlo: true,
    realTaxes: false,
    benefitsModeling: false,
    openSource: false,
    strengths: [
      "Account aggregation",
      "100+ customizable assumptions",
      "Tax-loss harvesting modeling",
      "Email support from planners",
    ],
    gaps: [
      "Higher price point",
      "Tax estimates not actual code",
      "No benefit modeling",
      "Closed source",
    ],
    url: "https://wealthtrace.com",
  },
  {
    name: "Empower (Personal Capital)",
    category: "robo",
    pricing: "Free (leads to AUM)",
    monteCarlo: true,
    realTaxes: false,
    benefitsModeling: false,
    openSource: false,
    strengths: [
      "Free planner tool",
      "Excellent account aggregation",
      "Professional-grade Monte Carlo",
      "Large user base, polished UI",
    ],
    gaps: [
      "Primary goal is wealth management sales",
      "Simplified tax model",
      "No state-specific accuracy",
      "Black box methodology",
    ],
    url: "https://empower.com",
  },
  {
    name: "Betterment",
    category: "robo",
    pricing: "0.25\u20130.40% AUM",
    monteCarlo: true,
    realTaxes: false,
    benefitsModeling: false,
    openSource: false,
    strengths: [
      "Integrated investing + planning",
      "Tax-loss harvesting",
      "Clean mobile experience",
      "Goal-based framework",
    ],
    gaps: [
      "Requires moving assets to platform",
      "Planning secondary to investing",
      "Simplified tax projections",
    ],
    url: "https://betterment.com",
  },
  {
    name: "FI Calc",
    category: "fire",
    pricing: "Free",
    monteCarlo: false,
    realTaxes: false,
    benefitsModeling: false,
    openSource: true,
    strengths: [
      "Historical backtesting (not Monte Carlo)",
      "FIRE community favorite",
      "Open source",
      "Simple, focused interface",
    ],
    gaps: [
      "No tax modeling at all",
      "No benefits integration",
      "Historical only (no forward simulation)",
      "Limited scenario complexity",
    ],
    url: "https://ficalc.app",
  },
  {
    name: "cFIREsim",
    category: "fire",
    pricing: "Free",
    monteCarlo: false,
    realTaxes: false,
    benefitsModeling: false,
    openSource: true,
    strengths: [
      "Historical sequence analysis",
      "Configurable withdrawal strategies",
      "Community-maintained",
      "Educational for FIRE concepts",
    ],
    gaps: [
      "No tax calculations",
      "Dated UI/UX",
      "No Monte Carlo option",
      "No benefit cliff modeling",
    ],
    url: "https://cfiresim.com",
  },
  {
    name: "Honest Math",
    category: "fire",
    pricing: "Free",
    monteCarlo: true,
    realTaxes: false,
    benefitsModeling: false,
    openSource: false,
    strengths: [
      "Independent (no product sales)",
      "Monte Carlo simulation",
      "Educational mission",
      "Clean interface",
    ],
    gaps: [
      "Simplified tax estimates",
      "Limited scenario features",
      "No state-specific taxes",
      "No benefits modeling",
    ],
    url: "https://honestmath.com",
  },
  {
    name: "RightCapital",
    category: "advisor",
    pricing: "$125\u2013200/mo (advisor)",
    monteCarlo: true,
    realTaxes: false,
    benefitsModeling: false,
    openSource: false,
    strengths: [
      "Built for financial advisors",
      "Client portal with collaboration",
      "Comprehensive planning modules",
      "Modern cloud-based platform",
    ],
    gaps: [
      "Not available to individuals",
      "Tax modeling is estimates",
      "Black box for clients",
      "Expensive (passed to clients in fees)",
    ],
    url: "https://rightcapital.com",
  },
  {
    name: "eMoney Advisor",
    category: "advisor",
    pricing: "$300+/mo (advisor)",
    monteCarlo: true,
    realTaxes: false,
    benefitsModeling: false,
    openSource: false,
    strengths: [
      "Industry standard for large RIAs",
      "Deep account aggregation",
      "Estate planning modules",
      "Fidelity-backed",
    ],
    gaps: [
      "Advisor-only, enterprise pricing",
      "Clients can't run their own scenarios",
      "Legacy UI in places",
      "Tax estimates not actual law",
    ],
    url: "https://emoneyadvisor.com",
  },
  {
    name: "MoneyGuidePro",
    category: "advisor",
    pricing: "$1,295+/yr (advisor)",
    monteCarlo: true,
    realTaxes: false,
    benefitsModeling: false,
    openSource: false,
    strengths: [
      "Largest market share among advisors",
      "Goal-based planning methodology",
      "Behavioral finance features",
      "Play Zone scenario modeling",
    ],
    gaps: [
      "Not available to individuals",
      "Simplified tax assumptions",
      "Focused on AUM practices",
      "Dated user interface",
    ],
    url: "https://moneyguidepro.com",
  },
];

const categoryLabels: Record<CompetitorCategory, string> = {
  dedicated: "Dedicated planners",
  robo: "Robo-advisors",
  fire: "FIRE community",
  advisor: "Advisor platforms",
};

export default function ThesisPage() {
  const [activeSection, setActiveSection] = useState<Section>("problem");
  const [selectedCategories, setSelectedCategories] = useState<
    Set<CompetitorCategory>
  >(new Set(["dedicated", "robo", "fire", "advisor"]));
  const [expandedCompetitor, setExpandedCompetitor] = useState<string | null>(
    null,
  );

  const sectionRefs = useRef<Record<Section, HTMLElement | null>>(
    Object.fromEntries(sections.map((s) => [s, null])) as Record<
      Section,
      HTMLElement | null
    >,
  );

  const toggleCategory = (category: CompetitorCategory) => {
    setSelectedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(category)) next.delete(category);
      else next.add(category);
      return next;
    });
  };

  const filteredCompetitors = competitors.filter((c) =>
    selectedCategories.has(c.category),
  );

  useEffect(() => {
    const handleScroll = () => {
      for (const section of sections) {
        const el = sectionRefs.current[section];
        if (el) {
          const rect = el.getBoundingClientRect();
          if (rect.top <= 200 && rect.bottom >= 200) {
            setActiveSection(section);
            break;
          }
        }
      }
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollTo = (section: Section) => {
    sectionRefs.current[section]?.scrollIntoView({ behavior: "smooth" });
  };

  const setRef =
    (section: Section) =>
    (el: HTMLElement | null) => {
      sectionRefs.current[section] = el;
    };

  const Check = ({ ok }: { ok: boolean }) => (
    <span className={ok ? "font-semibold text-[var(--color-success)]" : "text-[var(--color-gray-400)]"}>
      {ok ? "\u2713" : "\u2717"}
    </span>
  );

  return (
    <div className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text)]">
      {/* Scroll-spy nav */}
      <nav className={styles.scrollNav}>
        {sections.map((s) => (
          <button
            key={s}
            className={`${styles.scrollNavBtn} ${activeSection === s ? styles.scrollNavBtnActive : ""}`}
            onClick={() => scrollTo(s)}
          >
            {s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}
      </nav>

      {/* Hero */}
      <section className="flex min-h-[50vh] flex-col items-center justify-center bg-gradient-to-b from-[var(--color-primary-50)] to-[var(--color-bg)] px-6 pb-20 pt-36 text-center">
        <p className="mb-4 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--color-primary)]">
          Investment thesis
        </p>
        <h1
          className="text-[clamp(2.5rem,6vw,4rem)] font-bold text-[var(--color-gray-900)]"
          style={{ letterSpacing: "-0.03em" }}
        >
          The simulation engine for life decisions
        </h1>
        <p className="mt-6 max-w-lg text-xl text-[var(--color-text-muted)]">
          Starting with retirement. Expanding to every major financial choice.
        </p>
      </section>

      {/* === 1. Problem === */}
      <section
        className="flex min-h-screen flex-col items-center px-6 py-24"
        ref={setRef("problem")}
      >
        <div className="w-full max-w-3xl">
          <h2 className="mb-6 text-3xl font-bold text-[var(--color-gray-900)]">
            1. The problem
          </h2>
          <p className="mb-8 text-2xl font-medium leading-snug text-[var(--color-text)]">
            Personal finances are opaque&mdash;not just in retirement, but right
            now.
          </p>

          <div className="overflow-x-auto rounded-[var(--radius-md)] border border-[var(--color-border)]">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-[var(--color-gray-100)] text-left text-xs font-semibold text-[var(--color-gray-700)]">
                  <th className="px-4 py-3">Question</th>
                  <th className="px-4 py-3">Why it&rsquo;s hard</th>
                </tr>
              </thead>
              <tbody className="text-[var(--color-text-muted)]">
                {[
                  [
                    "\u201cWhat\u2019s my actual marginal tax rate?\u201d",
                    "Federal + state + FICA + phase-outs of credits",
                  ],
                  [
                    "\u201cIf I earn $5K more, how much do I keep?\u201d",
                    "Might lose ACA subsidies, EITC, SNAP\u2014could be negative",
                  ],
                  [
                    "\u201cShould I take this job offer?\u201d",
                    "Different state taxes, benefits, 401k match, health insurance",
                  ],
                  [
                    "\u201cCan I afford to move?\u201d",
                    "Property taxes, SALT cap, state income tax, cost of living",
                  ],
                  [
                    "\u201cWhat happens if we have a baby?\u201d",
                    "CTC, CDCTC, EITC changes, Medicaid eligibility, childcare costs",
                  ],
                ].map(([q, a]) => (
                  <tr key={q} className="border-t border-[var(--color-border)]">
                    <td className="px-4 py-3 font-medium text-[var(--color-text)]">
                      {q}
                    </td>
                    <td className="px-4 py-3">{a}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Cliff callout */}
          <div className="mt-8 rounded-r-[var(--radius-sm)] border-l-4 border-[var(--color-warning)] bg-[var(--color-warning-light)] p-6">
            <h3 className="mb-3 text-lg font-semibold text-[var(--color-gray-800)]">
              The benefits cliff problem
            </h3>
            <p className="mb-4 text-[var(--color-text-muted)]">
              For low and middle-income households, the interaction of taxes AND
              benefits creates perverse incentives:
            </p>
            <div className="rounded-[var(--radius-sm)] bg-white p-4">
              <p className="mb-3 font-mono text-lg font-semibold text-[var(--color-danger)]">
                Earn $1 more &rarr; Lose $3 in benefits &rarr; Net: -$2
              </p>
              <p className="text-sm text-[var(--color-text-muted)]">
                This happens at SNAP eligibility cliffs, Medicaid &rarr; ACA
                transition, EITC phase-out, CTC phase-out, ACA subsidy cliffs,
                housing assistance limits, childcare subsidy cliffs.
              </p>
            </div>
            <p className="mt-4 text-lg font-bold text-[var(--color-gray-800)]">
              Nobody shows people these cliffs before they fall off them.
            </p>
          </div>

          {/* Advisor callout */}
          <div className="mt-8 rounded-r-[var(--radius-sm)] border-l-4 border-[var(--color-danger)] bg-[var(--color-danger-light)] p-6">
            <h3 className="mb-3 text-lg font-semibold text-[var(--color-danger)]">
              The advisor problem
            </h3>
            <p className="mb-4 text-[var(--color-text-muted)]">
              Financial advisors charge $5-10K/year to answer these
              questions&mdash;but their answers are often wrong:
            </p>
            <ul className="space-y-2 text-sm text-[var(--color-text-muted)]">
              {[
                [
                  "Single-point estimates:",
                  "\u201cYou\u2019ll have $2M at retirement\u201d ignores uncertainty entirely",
                ],
                [
                  "Product incentives:",
                  "Advisors profit from selling annuities, insurance, AUM\u2014whether you need them or not",
                ],
                [
                  "False confidence:",
                  "A \u201cfinancial plan\u201d that doesn\u2019t show the range of outcomes is marketing, not math",
                ],
                [
                  "Black box methodology:",
                  "You can\u2019t verify their assumptions or calculations",
                ],
              ].map(([bold, rest]) => (
                <li key={bold} className="flex gap-2">
                  <span className="font-semibold text-[var(--color-danger)]">
                    &#10007;
                  </span>
                  <span>
                    <strong className="text-[var(--color-text)]">{bold}</strong>{" "}
                    {rest}
                  </span>
                </li>
              ))}
            </ul>
            <p className="mt-4 text-lg font-bold text-[var(--color-gray-800)]">
              People deserve probabilistic tools, not confident guesses from
              conflicted salespeople.
            </p>
          </div>

          {/* Generation callout */}
          <div className="mt-8 rounded-r-[var(--radius-sm)] border-l-4 border-[var(--color-primary)] bg-[var(--color-primary-50)] p-6">
            <h3 className="mb-3 text-lg font-semibold text-[var(--color-primary-dark)]">
              The generational shift
            </h3>
            <p className="mb-4 text-[var(--color-text-muted)]">
              Millennials and Gen Z are{" "}
              <strong className="text-[var(--color-text)]">
                42% of the population but only 14% of advisory clients
              </strong>
              . They&rsquo;re not avoiding financial planning&mdash;they&rsquo;re
              avoiding the traditional model:
            </p>
            <ul className="space-y-2 text-sm text-[var(--color-text-muted)]">
              {[
                [
                  "DIY preference:",
                  "79% turn to social media and online tools for financial advice",
                ],
                [
                  "Lower trust:",
                  "Only 27-28% view advisors as their most trusted source (vs 39% of Boomers)",
                ],
                [
                  "Digital-first:",
                  "73% prefer digital engagement; YouTube, TikTok, Instagram are their channels",
                ],
                [
                  "Still want help:",
                  "65% believe an advisor is important\u2014they just want tools, not salespeople",
                ],
              ].map(([bold, rest]) => (
                <li key={bold} className="flex gap-2">
                  <span className="text-[var(--color-primary)]">&rarr;</span>
                  <span>
                    <strong className="text-[var(--color-text)]">{bold}</strong>{" "}
                    {rest}
                  </span>
                </li>
              ))}
            </ul>
            <p className="mt-4 text-lg font-bold text-[var(--color-gray-800)]">
              This generation wants to see the numbers themselves. Think
              Robinhood for financial planning.
            </p>
          </div>
        </div>
      </section>

      {/* === 2. Vision === */}
      <section
        className="flex min-h-screen flex-col items-center bg-[var(--color-bg-alt)] px-6 py-24"
        ref={setRef("vision")}
      >
        <div className="w-full max-w-3xl">
          <h2 className="mb-6 text-3xl font-bold text-[var(--color-gray-900)]">
            2. The vision
          </h2>
          <p className="mb-8 text-lg leading-relaxed text-[var(--color-text-muted)]">
            EggNest answers &ldquo;what if?&rdquo; for major financial decisions
            with{" "}
            <strong className="text-[var(--color-text)]">
              real tax and benefit math
            </strong>
            &mdash;not estimates. We start with retirement simulation, but the
            real opportunity is immediate decisions: job offers, relocations, and
            benefit cliff navigation.
          </p>

          <div className="space-y-0.5">
            {[
              {
                color: "border-l-[var(--color-success)]",
                label: "Model",
                value:
                  "B2B2C via HR/relocation platforms, freemium consumer tier",
              },
              {
                color: "border-l-[var(--color-primary)]",
                label: "Wedge",
                value: "Job offer comparison with real after-tax math",
              },
              {
                color: "border-l-[var(--color-primary-dark)]",
                label: "Vision",
                value:
                  "The tax/benefit calculation layer for life decisions",
              },
            ].map(({ color, label, value }) => (
              <div
                key={label}
                className={`flex items-center justify-between border-l-4 ${color} bg-white px-5 py-4`}
              >
                <span className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
                  {label}
                </span>
                <span className="text-[var(--color-text)]">{value}</span>
              </div>
            ))}
          </div>

          <div className="mt-8 rounded-r-[var(--radius-sm)] border-l-4 border-[var(--color-primary)] bg-[var(--color-primary-50)] p-6">
            <h3 className="mb-3 text-lg font-semibold text-[var(--color-primary-dark)]">
              The honest thesis
            </h3>
            <p className="text-[var(--color-text-muted)]">
              <strong className="text-[var(--color-text)]">
                People don&rsquo;t think about uncertainty properly.
              </strong>{" "}
              They want a single number&mdash;&ldquo;will I have
              enough?&rdquo;&mdash;when the honest answer is a distribution.
              Financial advisors charge $5-10K/year to give people false
              confidence. Meanwhile, 42% of the population (Millennials + Gen Z)
              is underserved&mdash;they want to see the numbers themselves, like
              Robinhood showed with investing. We&rsquo;re building the
              Robinhood for financial planning: real probabilistic tools, real
              tax math, no salespeople.
            </p>
          </div>
        </div>
      </section>

      {/* === 3. Phases === */}
      <section
        className="flex min-h-screen flex-col items-center px-6 py-24"
        ref={setRef("phases")}
      >
        <div className="w-full max-w-3xl">
          <h2 className="mb-8 text-3xl font-bold text-[var(--color-gray-900)]">
            3. Product roadmap
          </h2>
          <div className="grid gap-5 md:grid-cols-2">
            {[
              {
                badge: "Now",
                highlight: true,
                title: "Phase 1: Retirement simulator",
                desc: "Build credibility with FIRE community. Prove the tax engine works.",
                items: [
                  "Monte Carlo simulation",
                  "Real federal + state taxes via PolicyEngine",
                  "Social Security optimization",
                  "Learn: Do users value tax accuracy?",
                ],
              },
              {
                badge: "6 months",
                title: "Phase 2: Job offer comparison",
                desc: "Higher urgency, less competition, clearer value prop.",
                items: [
                  'Compare offers: "TX vs CA, which pays more after taxes?"',
                  "Total comp: Salary + bonus + equity + benefits",
                  "B2B2C: Partner with Levels.fyi, recruiters, HR platforms",
                ],
              },
              {
                badge: "Year 1-2",
                title: "Phase 3: Open source ecosystem",
                desc: "Python package + CLI. Let users own their financial data.",
                items: [
                  "Package: pip install eggnest\u2014Monte Carlo, tax engine, projections",
                  "CLI: eggnest sync, eggnest simulate\u2014local files AI agents can explore",
                  "Filesystem-first: Your scenarios in YAML, models you can inspect",
                  "2026 paradigm: AI agents work with files, not black-box APIs",
                ],
              },
              {
                badge: "Year 2-3",
                title: "Phase 4: International + scale",
                desc: "Expand geographically and deepen advisor relationships.",
                items: [
                  "UK: Already supported via PolicyEngine-UK",
                  "Canada: In progress, pension/benefit complexity",
                  "Advisor network: Build referral flywheel among RIAs",
                  "Benefit cliffs: Partner with nonprofits, state agencies",
                ],
              },
            ].map(({ badge, highlight, title, desc, items }) => (
              <div
                key={title}
                className={`relative rounded-[var(--radius-md)] border bg-white p-6 ${highlight ? "border-[var(--color-primary)] shadow-[0_0_0_1px_var(--color-primary)]" : "border-[var(--color-border)]"}`}
              >
                <span
                  className={`absolute -top-2.5 right-5 rounded-full px-3 py-1 text-xs font-semibold ${highlight ? "bg-[var(--color-primary)] text-white" : "bg-[var(--color-gray-100)] text-[var(--color-text-muted)]"}`}
                >
                  {badge}
                </span>
                <h3 className="mb-2 text-lg font-semibold">{title}</h3>
                <p className="mb-4 text-sm text-[var(--color-text-muted)]">
                  {desc}
                </p>
                <ul className="space-y-2 text-sm text-[var(--color-text-muted)]">
                  {items.map((item) => (
                    <li key={item} className="flex gap-2">
                      <span className="text-[var(--color-primary)]">
                        &rarr;
                      </span>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* === 4. Unlock === */}
      <section
        className="flex min-h-screen flex-col items-center bg-[var(--color-bg-alt)] px-6 py-24"
        ref={setRef("unlock")}
      >
        <div className="w-full max-w-3xl">
          <h2 className="mb-8 text-3xl font-bold text-[var(--color-gray-900)]">
            4. The tax engine advantage
          </h2>
          <div className="space-y-5">
            {[
              {
                title: "Cosilico: AI-encoded tax rules",
                desc: "Our tax engine (transitioning from PolicyEngine to Cosilico) uses AI to encode legislation:",
                items: [
                  "Speed: New countries in weeks, not years",
                  "Accuracy: Actual law, not simplified estimates",
                  "Coverage: US (50 states), UK, Canada (in progress)",
                  "Updates: Law changes encoded as they pass",
                ],
                conclusion:
                  "This is our moat. Competitors would need years to replicate.",
              },
              {
                title: "Taxes + benefits together",
                desc: "The full picture, not just income tax:",
                items: [
                  "Taxes: Federal, state, local, FICA, credits, deductions",
                  "Benefits: SNAP, Medicaid, ACA subsidies, EITC, CTC, housing, childcare",
                  "Cliffs: Where $1 more income costs $3 in benefits",
                ],
                conclusion:
                  "True marginal rate\u2014including benefit loss\u2014for any family\u2019s decisions.",
              },
              {
                title: "Filesystem-first: AI-native architecture",
                desc: "2026 is the year of the filesystem. AI agents work with local files, not black-box APIs.",
                items: [
                  "CLI sync: Your scenarios as local YAML files you own",
                  "AI-explorable: Claude/Cursor/Copilot can read, edit, run simulations",
                  "Verify everything: Inspect the models, check the assumptions",
                  "Git-native: Version control your financial plans like code",
                ],
                highlight: true,
              },
            ].map(({ title, desc, items, conclusion, highlight }) => (
              <div
                key={title}
                className={`rounded-[var(--radius-md)] border p-6 ${highlight ? "border-[var(--color-success)] bg-[var(--color-success-light)]" : "border-[var(--color-border)] bg-white"}`}
              >
                <h3 className="mb-2 text-lg font-semibold">{title}</h3>
                <p className="mb-4 text-sm text-[var(--color-text-muted)]">
                  {desc}
                </p>
                <ul className="space-y-2 text-sm text-[var(--color-text-muted)]">
                  {items.map((item) => (
                    <li key={item} className="flex gap-2">
                      <span className="text-[var(--color-primary)]">
                        &#8226;
                      </span>
                      {item}
                    </li>
                  ))}
                </ul>
                {conclusion && (
                  <p className="mt-4 rounded-[var(--radius-sm)] bg-[var(--color-primary-50)] px-4 py-3 text-sm font-semibold text-[var(--color-text)]">
                    {conclusion}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* === 5. Market === */}
      <section
        className="flex min-h-screen flex-col items-center px-6 py-24"
        ref={setRef("market")}
      >
        <div className="w-full max-w-3xl">
          <h2 className="mb-6 text-3xl font-bold text-[var(--color-gray-900)]">
            5. Market opportunity
          </h2>
          <p className="mb-8 text-lg text-[var(--color-text-muted)]">
            <strong className="text-[var(--color-text)]">
              140M Americans (Millennials + Gen Z) are underserved by
              traditional advisors.
            </strong>{" "}
            They&rsquo;re 42% of the population but only 14% of advisory
            clients. They don&rsquo;t want to pay $5K/year for a black
            box&mdash;they want transparent tools they control.
          </p>

          {/* US Market table */}
          <div className="overflow-x-auto rounded-[var(--radius-md)] border border-[var(--color-border)]">
            <h3 className="bg-[var(--color-gray-100)] px-4 py-3 text-lg font-semibold">
              US market (Year 1-2)
            </h3>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)] bg-[var(--color-gray-100)] text-left text-xs font-semibold text-[var(--color-gray-700)]">
                  <th className="px-4 py-3">Decision</th>
                  <th className="px-4 py-3">Annual volume</th>
                  <th className="px-4 py-3">Realistic WTP</th>
                  <th className="px-4 py-3">Accessible TAM</th>
                </tr>
              </thead>
              <tbody className="text-[var(--color-text-muted)]">
                {[
                  ["Job offers (multi-state)", "~5M/year", "$20-50", "$100M"],
                  [
                    "Benefit cliff navigation",
                    "~10M affected",
                    "$0-20 (B2B funded)",
                    "$50M (B2B)",
                  ],
                  [
                    "Retirement planning",
                    "4M retiring/year",
                    "$50-100",
                    "$200M",
                  ],
                ].map(([d, v, w, t]) => (
                  <tr
                    key={d}
                    className="border-t border-[var(--color-border)]"
                  >
                    <td className="px-4 py-3">{d}</td>
                    <td className="px-4 py-3">{v}</td>
                    <td className="px-4 py-3">{w}</td>
                    <td className="px-4 py-3 font-semibold text-[var(--color-primary)]">
                      {t}
                    </td>
                  </tr>
                ))}
                <tr className="border-t border-[var(--color-border)] bg-[var(--color-primary-50)]">
                  <td className="px-4 py-3 font-bold" colSpan={3}>
                    US addressable
                  </td>
                  <td className="px-4 py-3 font-bold text-[var(--color-primary)]">
                    $350M
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Pricing tiers */}
          <h3 className="mb-4 mt-12 text-lg font-semibold">
            Pricing strategy
          </h3>
          <div className="grid gap-4 sm:grid-cols-3">
            {[
              {
                name: "Free",
                price: "$0",
                desc: "Single scenario, build awareness",
              },
              {
                name: "Pro",
                price: "$8/mo or $60/yr",
                desc: "Save scenarios, PDF export, priority support",
                featured: true,
              },
              {
                name: "B2B embed",
                price: "$1-5/user",
                desc: "White-label for HR platforms, benefits sites",
              },
            ].map(({ name, price, desc, featured }) => (
              <div
                key={name}
                className={`rounded-[var(--radius-md)] border p-6 text-center ${featured ? "border-[var(--color-primary)] shadow-[0_0_0_1px_var(--color-primary)]" : "border-[var(--color-border)]"} bg-white`}
              >
                <div className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
                  {name}
                </div>
                <div className="mt-2 text-2xl font-bold text-[var(--color-primary)]">
                  {price}
                </div>
                <p className="mt-3 text-sm text-[var(--color-text-muted)]">
                  {desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* === 6. Competition === */}
      <section
        className="flex flex-col items-center bg-[var(--color-bg-alt)] px-6 py-24"
        ref={setRef("competition")}
      >
        <div className="w-full max-w-4xl">
          <h2 className="mb-6 text-3xl font-bold text-[var(--color-gray-900)]">
            6. Competitive landscape
          </h2>
          <p className="mb-8 text-lg text-[var(--color-text-muted)]">
            We&rsquo;ve analyzed 13+ competitors across 4 categories. Despite
            billions in cumulative funding and millions of users,{" "}
            <strong className="text-[var(--color-text)]">
              none combine Monte Carlo simulation with real tax calculations
            </strong>
            .
          </p>

          {/* Feature matrix */}
          <div className="overflow-hidden rounded-[var(--radius-md)] border border-[var(--color-border)] bg-white p-6">
            <h3 className="mb-4 text-lg font-semibold">
              The gap in the market
            </h3>
            <div className="grid grid-cols-[minmax(100px,180px)_repeat(4,1fr)] gap-2 text-center text-sm">
              <span />
              <span className="text-xs font-semibold text-[var(--color-text-muted)]">
                Monte Carlo
              </span>
              <span className="text-xs font-semibold text-[var(--color-text-muted)]">
                Real taxes
              </span>
              <span className="text-xs font-semibold text-[var(--color-text-muted)]">
                Benefits
              </span>
              <span className="text-xs font-semibold text-[var(--color-text-muted)]">
                Open source
              </span>

              {/* EggNest row */}
              <span className="rounded-l-[var(--radius-sm)] bg-[var(--color-primary-50)] px-3 py-2 text-left font-semibold text-[var(--color-primary-dark)]">
                EggNest
              </span>
              {[true, true, true, true].map((_, i) => (
                <span
                  key={i}
                  className="bg-[var(--color-primary-50)] py-2 font-semibold text-[var(--color-success)]"
                >
                  &#10003;
                </span>
              ))}

              {/* Competitors row */}
              <span className="px-3 py-2 text-left font-medium text-[var(--color-text)]">
                All 13 competitors
              </span>
              <span className="py-2 font-medium text-[var(--color-warning)]">
                9/13
              </span>
              <span className="py-2 font-semibold text-[var(--color-danger)]">
                0/13
              </span>
              <span className="py-2 font-semibold text-[var(--color-danger)]">
                0/13
              </span>
              <span className="py-2 font-medium text-[var(--color-warning)]">
                2/13
              </span>
            </div>
            <p className="mt-4 rounded-r-[var(--radius-sm)] border-l-4 border-[var(--color-primary)] bg-[var(--color-primary-50)] p-4 text-sm text-[var(--color-text-muted)]">
              <strong className="text-[var(--color-text)]">Key insight:</strong>{" "}
              Every competitor uses tax estimates or ignores taxes entirely. None
              model benefit cliffs. This is because accurate tax law is genuinely
              hard&mdash;PolicyEngine represents years of work to encode actual
              legislation.
            </p>
          </div>

          {/* Category filters */}
          <div className="mt-8">
            <h3 className="mb-4 text-lg font-semibold">
              Explore by category
            </h3>
            <div className="flex flex-wrap gap-2">
              {(
                Object.keys(categoryLabels) as CompetitorCategory[]
              ).map((cat) => (
                <button
                  key={cat}
                  className={`flex items-center gap-2 rounded-full border px-4 py-2.5 text-sm font-medium transition-all ${
                    selectedCategories.has(cat)
                      ? "border-[var(--color-primary)] bg-[var(--color-primary)] text-white"
                      : "border-[var(--color-border)] bg-white text-[var(--color-text-muted)] hover:border-[var(--color-primary)] hover:text-[var(--color-text)]"
                  }`}
                  onClick={() => toggleCategory(cat)}
                >
                  {categoryLabels[cat]}
                  <span
                    className={`flex h-5 w-5 items-center justify-center rounded-full text-xs ${selectedCategories.has(cat) ? "bg-white/25" : "bg-black/10"}`}
                  >
                    {competitors.filter((c) => c.category === cat).length}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Competitor cards */}
          <div className="mt-4 space-y-3">
            {filteredCompetitors.map((comp) => (
              <div
                key={comp.name}
                className={`overflow-hidden rounded-[var(--radius-md)] border bg-white transition-all ${expandedCompetitor === comp.name ? "border-[var(--color-primary)] shadow-[0_4px_12px_rgba(0,0,0,0.08)]" : "border-[var(--color-border)] hover:border-[var(--color-gray-300)]"}`}
              >
                <div
                  className="flex cursor-pointer items-center justify-between px-5 py-4 transition-colors hover:bg-[var(--color-gray-50)]"
                  onClick={() =>
                    setExpandedCompetitor(
                      expandedCompetitor === comp.name ? null : comp.name,
                    )
                  }
                >
                  <div className="flex flex-wrap items-center gap-3">
                    <strong>{comp.name}</strong>
                    <span className="rounded-full bg-[var(--color-gray-100)] px-2.5 py-1 text-[0.7rem] font-medium text-[var(--color-text-muted)]">
                      {categoryLabels[comp.category]}
                    </span>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-sm font-medium text-[var(--color-text-muted)]">
                      {comp.pricing}
                    </span>
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--color-gray-100)] text-sm text-[var(--color-text-muted)]">
                      {expandedCompetitor === comp.name ? "\u2212" : "+"}
                    </span>
                  </div>
                </div>
                <div className="flex flex-wrap gap-4 px-5 pb-4">
                  <span className="text-xs font-medium">
                    <Check ok={comp.monteCarlo} /> Monte Carlo
                  </span>
                  <span className="text-xs font-medium">
                    <Check ok={comp.realTaxes} /> Real taxes
                  </span>
                  <span className="text-xs font-medium">
                    <Check ok={comp.benefitsModeling} /> Benefits
                  </span>
                  <span className="text-xs font-medium">
                    <Check ok={comp.openSource} /> Open source
                  </span>
                </div>
                {expandedCompetitor === comp.name && (
                  <div className="border-t border-[var(--color-border)] bg-[var(--color-gray-50)] px-5 py-4">
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div>
                        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
                          Strengths
                        </h4>
                        <ul className="space-y-1 text-sm text-[var(--color-text-muted)]">
                          {comp.strengths.map((s) => (
                            <li key={s} className="flex gap-2">
                              <span className="text-[var(--color-success)]">
                                &rarr;
                              </span>
                              {s}
                            </li>
                          ))}
                        </ul>
                      </div>
                      <div>
                        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
                          Gaps (our opportunity)
                        </h4>
                        <ul className="space-y-1 text-sm text-[var(--color-text-muted)]">
                          {comp.gaps.map((g) => (
                            <li key={g} className="flex gap-2">
                              <span className="text-[var(--color-primary)]">
                                &rarr;
                              </span>
                              {g}
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                    {comp.url && (
                      <a
                        href={comp.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-3 inline-block text-sm font-medium text-[var(--color-primary)] hover:underline"
                      >
                        Visit {comp.name} &rarr;
                      </a>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* === 7. Model === */}
      <section
        className="flex min-h-screen flex-col items-center px-6 py-24"
        ref={setRef("model")}
      >
        <div className="w-full max-w-3xl">
          <h2 className="mb-8 text-3xl font-bold text-[var(--color-gray-900)]">
            7. Business model
          </h2>
          <div className="space-y-4">
            {[
              {
                title: "Consumer direct (primary)",
                desc: "Free tier democratizes access to probabilistic planning. Pro tier for power users who want saved scenarios, comparisons, and exports.",
                metric:
                  "Goal: Replace the $5K/year advisor with a $60/year tool",
                primary: true,
              },
              {
                title: "B2B2C partnerships",
                desc: "Embed in HR platforms, salary sites, benefits navigators. Reach people at decision moments.",
                metric:
                  "Target: $1-5/user or $10K-50K/year enterprise",
              },
              {
                title: "Open source ecosystem",
                desc: "EggNest Python package (MIT license) lets developers build on our engine. Drives adoption and trust, not direct revenue.",
                metric: "Strategic: Adoption over monetization",
              },
            ].map(({ title, desc, metric, primary }) => (
              <div
                key={title}
                className={`rounded-[var(--radius-md)] border p-6 ${primary ? "border-[var(--color-primary)] bg-[var(--color-primary-50)]" : "border-[var(--color-border)] bg-white"}`}
              >
                <h3 className="mb-2 text-lg font-semibold">{title}</h3>
                <p className="mb-3 text-sm text-[var(--color-text-muted)]">
                  {desc}
                </p>
                <p className="text-sm font-semibold text-[var(--color-primary)]">
                  {metric}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* === 8. GTM === */}
      <section
        className="flex min-h-screen flex-col items-center bg-[var(--color-bg-alt)] px-6 py-24"
        ref={setRef("gtm")}
      >
        <div className="w-full max-w-3xl">
          <h2 className="mb-8 text-3xl font-bold text-[var(--color-gray-900)]">
            8. Go-to-market
          </h2>
          <div className="space-y-4">
            {[
              {
                title: "Phase 1: FIRE community (now)",
                items: [
                  "Launch on Reddit r/financialindependence, r/Fire, r/Bogleheads",
                  "These people already distrust advisors\u2014they\u2019re our early adopters",
                  'Goal: 5K users who spread the "you don\u2019t need an advisor" message',
                ],
                highlight: true,
              },
              {
                title: "Phase 2: Millennial/Gen Z channels (6 months)",
                items: [
                  "YouTube, TikTok, Instagram\u2014where 79% of young people get financial info",
                  'Content: "What your advisor isn\u2019t telling you about uncertainty"',
                  "Target the 42% who are underserved by traditional advisors",
                ],
              },
              {
                title: "Phase 3: B2B partnerships (year 2)",
                items: [
                  "Embed in HR platforms, benefits navigators\u2014reach people at decision moments",
                  "Partner with fee-only advisor directories (as alternative, not tool for advisors)",
                  "Target nonprofits helping low-income navigate benefit cliffs",
                ],
              },
              {
                title: "Phase 4: International (year 2-3)",
                items: [
                  "UK launch\u2014same advisor distrust, same need for probabilistic tools",
                  "Canada as Cosilico coverage expands",
                  "Localized content for each market\u2019s advisory fee structure",
                ],
              },
            ].map(({ title, items, highlight }) => (
              <div
                key={title}
                className={`rounded-[var(--radius-md)] border p-6 ${highlight ? "border-[var(--color-primary)] bg-[var(--color-primary-50)]" : "border-[var(--color-border)] bg-white"}`}
              >
                <h3 className="mb-3 text-lg font-semibold">{title}</h3>
                <ul className="space-y-2 text-sm text-[var(--color-text-muted)]">
                  {items.map((item) => (
                    <li key={item} className="flex gap-2">
                      <span className="text-[var(--color-primary)]">
                        &rarr;
                      </span>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* === 9. Team === */}
      <section
        className="flex flex-col items-center px-6 py-24"
        ref={setRef("team")}
      >
        <div className="w-full max-w-3xl">
          <h2 className="mb-8 text-3xl font-bold text-[var(--color-gray-900)]">
            9. Team
          </h2>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            {[
              {
                period: "Now",
                content: "Technical founder",
                highlight: true,
              },
              {
                period: "Year 1",
                list: ["Growth marketer", "Part-time designer"],
              },
              {
                period: "Year 2",
                list: [
                  "2 engineers (simulation engine, API)",
                  "Data scientist (model improvement)",
                  "Content marketer",
                ],
              },
              {
                period: "Year 3+",
                list: [
                  "Sales (API/partnerships)",
                  "Customer success",
                  "Additional engineers",
                ],
              },
            ].map(({ period, content, list, highlight }) => (
              <div
                key={period}
                className={`rounded-[var(--radius-md)] border p-5 ${highlight ? "border-[var(--color-primary)] bg-[var(--color-primary-50)]" : "border-[var(--color-border)] bg-white"}`}
              >
                <h3 className="mb-2 text-base font-semibold">{period}</h3>
                {content && (
                  <p className="text-sm text-[var(--color-text-muted)]">
                    {content}
                  </p>
                )}
                {list && (
                  <ul className="space-y-1 text-sm text-[var(--color-text-muted)]">
                    {list.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* === 10. Risks === */}
      <section
        className="flex flex-col items-center bg-[var(--color-bg-alt)] px-6 py-24"
        ref={setRef("risks")}
      >
        <div className="w-full max-w-3xl">
          <h2 className="mb-8 text-3xl font-bold text-[var(--color-gray-900)]">
            10. Risks &amp; hard questions
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {[
              {
                q: "Do people actually care about tax accuracy?",
                a: 'Unknown. "Close enough" may be good enough for most users. Must validate early.',
                level: "high",
              },
              {
                q: "Consumer fintech conversion is brutal",
                a: "Boldin/ProjectionLab struggle to convert. B2B may be required path to revenue.",
                level: "high",
              },
              {
                q: "Cosilico execution risk",
                a: "Transitioning from PolicyEngine to AI-encoded rules. Timeline and accuracy TBD.",
                level: "medium",
              },
              {
                q: "International expansion complexity",
                a: "Each country has unique tax/benefit systems. UK ready, others need validation.",
                level: "medium",
              },
              {
                q: "FIRE community may not pay",
                a: "They love spreadsheets and free tools. May drive awareness but not revenue.",
              },
              {
                q: "B2B sales cycle is long",
                a: "HR platforms move slowly. Need consumer traction to prove value first.",
              },
            ].map(({ q, a, level }) => (
              <div
                key={q}
                className={`rounded-[var(--radius-md)] border bg-white p-5 ${level === "high" ? "border-l-4 border-l-[var(--color-danger)] border-t-[var(--color-border)] border-r-[var(--color-border)] border-b-[var(--color-border)]" : level === "medium" ? "border-l-4 border-l-[var(--color-warning)] border-t-[var(--color-border)] border-r-[var(--color-border)] border-b-[var(--color-border)]" : "border-[var(--color-border)]"}`}
              >
                <h4
                  className={`mb-2 text-base font-semibold ${level === "high" ? "text-[var(--color-danger)]" : level === "medium" ? "text-[#b45309]" : "text-[var(--color-text)]"}`}
                >
                  {q}
                </h4>
                <p className="text-sm text-[var(--color-text-muted)]">{a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Summary */}
      <section className="flex justify-center bg-[var(--color-primary-50)] px-6 py-20">
        <div className="w-full max-w-3xl text-lg">
          <h2 className="mb-6 text-3xl font-bold text-[var(--color-gray-900)]">
            Summary
          </h2>
          <div className="space-y-5 text-[var(--color-text-muted)]">
            <p>
              <strong className="text-[var(--color-text)]">
                The problem:
              </strong>{" "}
              People don&rsquo;t think about uncertainty properly. Advisors
              exploit this with confident single-point estimates and product
              sales.
            </p>
            <p>
              <strong className="text-[var(--color-text)]">
                The opportunity:
              </strong>{" "}
              140M Millennials and Gen Z want DIY tools, not $5K/year advisors.
              They&rsquo;re 42% of the population, 14% of advisory clients.
            </p>
            <p>
              <strong className="text-[var(--color-text)]">
                The solution:
              </strong>{" "}
              Robinhood for financial planning&mdash;real probabilistic tools
              with real tax math. Open source, transparent, no salespeople.
            </p>
            <p>
              <strong className="text-[var(--color-text)]">The plan:</strong>
            </p>
            <ul className="ml-6 list-disc space-y-2">
              <li>
                Launch with FIRE community who already distrust advisors
              </li>
              <li>
                Expand to YouTube/TikTok/Instagram where young people actually
                are
              </li>
              <li>
                International expansion via Cosilico&rsquo;s AI-encoded tax
                rules
              </li>
              <li>Stay honest about what works and what doesn&rsquo;t</li>
            </ul>
          </div>
          <p className="mt-10 text-center text-xl font-medium italic text-[var(--color-primary-dark)]">
            Financial planning for people who want to see the numbers themselves.
          </p>
        </div>
      </section>

      {/* CTA */}
      <section className="bg-[var(--color-gray-900)] px-6 py-24 text-center text-white">
        <h2 className="text-3xl font-bold">Try the simulator</h2>
        <p className="mt-3 text-lg text-[var(--color-gray-400)]">
          See your retirement projections in 30 seconds.
        </p>
        <div className="mt-8 flex justify-center gap-4">
          <Link
            href="/simulator"
            className="rounded-[var(--radius-sm)] bg-[var(--color-primary)] px-7 py-3.5 text-sm font-medium text-white transition-colors hover:bg-[var(--color-primary-light)]"
          >
            Launch app
          </Link>
          <Link
            href="/"
            className="rounded-[var(--radius-sm)] border border-[var(--color-gray-600)] px-7 py-3.5 text-sm font-medium text-white transition-colors hover:border-[var(--color-gray-400)]"
          >
            Back to home
          </Link>
        </div>
      </section>
    </div>
  );
}
