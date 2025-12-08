import { useState, useEffect, useRef } from "react";
import "../styles/Thesis.css";

type Section = "problem" | "vision" | "phases" | "unlock" | "market" | "competition" | "model" | "gtm" | "team" | "risks";

// Competitor data for interactive display
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

const sections: Section[] = ["problem", "vision", "phases", "unlock", "market", "competition", "model", "gtm", "team", "risks"];

const competitors: Competitor[] = [
  // Dedicated Retirement Planners
  {
    name: "MaxiFi",
    category: "dedicated",
    pricing: "$109–149/yr",
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
    pricing: "Free–$144/yr",
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
    pricing: "Free–$109/yr",
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
    pricing: "$99–119/yr",
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
  // Robo-advisors / Aggregators
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
    pricing: "0.25–0.40% AUM",
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
  // FIRE Community Tools
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
  // Professional Advisor Tools
  {
    name: "RightCapital",
    category: "advisor",
    pricing: "$125–200/mo (advisor)",
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
  dedicated: "Dedicated Planners",
  robo: "Robo-Advisors",
  fire: "FIRE Community",
  advisor: "Advisor Platforms",
};

export function ThesisPage() {
  const [activeSection, setActiveSection] = useState<Section>("problem");
  const [selectedCategories, setSelectedCategories] = useState<Set<CompetitorCategory>>(
    new Set(["dedicated", "robo", "fire", "advisor"])
  );
  const [expandedCompetitor, setExpandedCompetitor] = useState<string | null>(null);

  const sectionRefs = useRef<Record<Section, HTMLElement | null>>(
    Object.fromEntries(sections.map(s => [s, null])) as Record<Section, HTMLElement | null>
  );

  const toggleCategory = (category: CompetitorCategory) => {
    setSelectedCategories(prev => {
      const next = new Set(prev);
      if (next.has(category)) {
        next.delete(category);
      } else {
        next.add(category);
      }
      return next;
    });
  };

  const filteredCompetitors = competitors.filter(c => selectedCategories.has(c.category));

  // Scroll spy
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

  const setRef = (section: Section) => (el: HTMLElement | null) => {
    sectionRefs.current[section] = el;
  };

  return (
    <div className="thesis">
      {/* Top nav */}
      <nav className="thesis-top-nav">
        <a href="/" className="thesis-logo">
          <img src="/favicon.svg" alt="" className="thesis-logo-icon" />
          EggNest
        </a>
      </nav>

      {/* Progress nav */}
      <nav className="thesis-nav">
        {sections.map(s => (
          <button
            key={s}
            className={activeSection === s ? "active" : ""}
            onClick={() => scrollTo(s)}
          >
            {s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}
      </nav>

      {/* Hero */}
      <section className="thesis-hero">
        <p className="thesis-label">Investment Thesis</p>
        <h1>The Simulation Engine for Life Decisions</h1>
        <p className="thesis-subtitle">
          Starting with retirement. Expanding to every major financial choice.
        </p>
      </section>

      {/* Problem */}
      <section className="thesis-section" ref={setRef("problem")}>
        <div className="thesis-content">
          <h2>1. The Problem</h2>
          <p className="problem-lead">
            Personal finances are opaque—not just in retirement, but right now.
          </p>

          <div className="problem-table">
            <table>
              <thead>
                <tr>
                  <th>Question</th>
                  <th>Why It's Hard</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>"What's my actual marginal tax rate?"</td>
                  <td>Federal + state + FICA + phase-outs of credits</td>
                </tr>
                <tr>
                  <td>"If I earn $5K more, how much do I keep?"</td>
                  <td>Might lose ACA subsidies, EITC, SNAP—could be negative</td>
                </tr>
                <tr>
                  <td>"Should I take this job offer?"</td>
                  <td>Different state taxes, benefits, 401k match, health insurance</td>
                </tr>
                <tr>
                  <td>"Can I afford to move?"</td>
                  <td>Property taxes, SALT cap, state income tax, cost of living</td>
                </tr>
                <tr>
                  <td>"What happens if we have a baby?"</td>
                  <td>CTC, CDCTC, EITC changes, Medicaid eligibility, childcare costs</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="cliff-callout">
            <h3>The Benefits Cliff Problem</h3>
            <p>
              For low and middle-income households, the interaction of taxes AND benefits creates perverse incentives:
            </p>
            <div className="cliff-example">
              <div className="cliff-formula">
                Earn $1 more → Lose $3 in benefits → Net: -$2
              </div>
              <p>This happens at SNAP eligibility cliffs, Medicaid → ACA transition, EITC phase-out, CTC phase-out, ACA subsidy cliffs, housing assistance limits, childcare subsidy cliffs.</p>
            </div>
            <p className="cliff-key"><strong>Nobody shows people these cliffs before they fall off them.</strong></p>
          </div>

          <div className="advisor-callout">
            <h3>The Advisor Problem</h3>
            <p>
              Financial advisors charge $5-10K/year to answer these questions—but their answers are often wrong:
            </p>
            <ul>
              <li><strong>Single-point estimates:</strong> "You'll have $2M at retirement" ignores uncertainty entirely</li>
              <li><strong>Product incentives:</strong> Advisors profit from selling annuities, insurance, AUM—whether you need them or not</li>
              <li><strong>False confidence:</strong> A "financial plan" that doesn't show the range of outcomes is marketing, not math</li>
              <li><strong>Black box methodology:</strong> You can't verify their assumptions or calculations</li>
            </ul>
            <p className="cliff-key"><strong>People deserve probabilistic tools, not confident guesses from conflicted salespeople.</strong></p>
          </div>

          <div className="generation-callout">
            <h3>The Generational Shift</h3>
            <p>
              Millennials and Gen Z are <strong>42% of the population but only 14% of advisory clients</strong>.
              They're not avoiding financial planning—they're avoiding the traditional model:
            </p>
            <ul>
              <li><strong>DIY preference:</strong> 79% turn to social media and online tools for financial advice</li>
              <li><strong>Lower trust:</strong> Only 27-28% view advisors as their most trusted source (vs 39% of Boomers)</li>
              <li><strong>Digital-first:</strong> 73% prefer digital engagement; YouTube, TikTok, Instagram are their channels</li>
              <li><strong>Still want help:</strong> 65% believe an advisor is important—they just want tools, not salespeople</li>
            </ul>
            <p className="cliff-key"><strong>This generation wants to see the numbers themselves. Think Robinhood for financial planning.</strong></p>
          </div>
        </div>
      </section>

      {/* Vision */}
      <section className="thesis-section" ref={setRef("vision")}>
        <div className="thesis-content">
          <h2>2. The Vision</h2>
          <p>
            EggNest answers "what if?" for major financial decisions with <strong>real tax and benefit math</strong>—not estimates. We start with retirement simulation, but the real opportunity is immediate decisions: job offers, relocations, and benefit cliff navigation.
          </p>

          <div className="vision-stack">
            <div className="stack-item stack-model">
              <span className="stack-label">Model</span>
              <span className="stack-value">B2B2C via HR/relocation platforms, freemium consumer tier</span>
            </div>
            <div className="stack-item stack-wedge">
              <span className="stack-label">Wedge</span>
              <span className="stack-value">Job offer comparison with real after-tax math</span>
            </div>
            <div className="stack-item stack-vision">
              <span className="stack-label">Vision</span>
              <span className="stack-value">The tax/benefit calculation layer for life decisions</span>
            </div>
          </div>

          <div className="vision-insight">
            <h3>The Honest Thesis</h3>
            <p>
              <strong>People don't think about uncertainty properly.</strong> They want a single number—"will I have enough?"—when the honest answer is a distribution. Financial advisors charge $5-10K/year to give people false confidence. Meanwhile, 42% of the population (Millennials + Gen Z) is underserved—they want to see the numbers themselves, like Robinhood showed with investing. We're building the Robinhood for financial planning: real probabilistic tools, real tax math, no salespeople.
            </p>
          </div>
        </div>
      </section>

      {/* Phases */}
      <section className="thesis-section" ref={setRef("phases")}>
        <div className="thesis-content">
          <h2>3. Product Roadmap</h2>

          <div className="phase-grid">
            <div className="phase-card phase-now">
              <div className="phase-badge">Now</div>
              <h3>Phase 1: Retirement Simulator</h3>
              <p>Build credibility with FIRE community. Prove the tax engine works.</p>
              <ul>
                <li>Monte Carlo simulation</li>
                <li>Real federal + state taxes via PolicyEngine</li>
                <li>Social Security optimization</li>
                <li>Learn: Do users value tax accuracy?</li>
              </ul>
            </div>

            <div className="phase-card">
              <div className="phase-badge">6 months</div>
              <h3>Phase 2: Job Offer Comparison</h3>
              <p>Higher urgency, less competition, clearer value prop.</p>
              <ul>
                <li><strong>Compare offers:</strong> "TX vs CA, which pays more after taxes?"</li>
                <li><strong>Total comp:</strong> Salary + bonus + equity + benefits</li>
                <li><strong>B2B2C:</strong> Partner with Levels.fyi, recruiters, HR platforms</li>
              </ul>
            </div>

            <div className="phase-card">
              <div className="phase-badge">Year 1-2</div>
              <h3>Phase 3: Open Source Ecosystem</h3>
              <p>Python package + CLI. Let users own their financial data.</p>
              <ul>
                <li><strong>Package:</strong> pip install eggnest—Monte Carlo, tax engine, projections</li>
                <li><strong>CLI:</strong> eggnest sync, eggnest simulate—local files AI agents can explore</li>
                <li><strong>Filesystem-first:</strong> Your scenarios in YAML, models you can inspect and verify</li>
                <li><strong>2026 paradigm:</strong> AI agents work with files, not black-box APIs</li>
              </ul>
            </div>

            <div className="phase-card">
              <div className="phase-badge">Year 2-3</div>
              <h3>Phase 4: International + Scale</h3>
              <p>Expand geographically and deepen advisor relationships.</p>
              <ul>
                <li><strong>UK:</strong> Already supported via PolicyEngine-UK</li>
                <li><strong>Canada:</strong> In progress, pension/benefit complexity</li>
                <li><strong>Advisor network:</strong> Build referral flywheel among RIAs</li>
                <li><strong>Benefit cliffs:</strong> Partner with nonprofits, state agencies</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Unlock */}
      <section className="thesis-section" ref={setRef("unlock")}>
        <div className="thesis-content">
          <h2>4. The Tax Engine Advantage</h2>

          <div className="unlock-grid">
            <div className="unlock-card">
              <h3>Cosilico: AI-Encoded Tax Rules</h3>
              <p>Our tax engine (transitioning from PolicyEngine to Cosilico) uses AI to encode legislation:</p>
              <ul>
                <li><strong>Speed:</strong> New countries in weeks, not years</li>
                <li><strong>Accuracy:</strong> Actual law, not simplified estimates</li>
                <li><strong>Coverage:</strong> US (50 states), UK, Canada (in progress)</li>
                <li><strong>Updates:</strong> Law changes encoded as they pass</li>
              </ul>
              <p className="unlock-conclusion">
                <strong>This is our moat.</strong> Competitors would need years to replicate.
              </p>
            </div>

            <div className="unlock-card">
              <h3>Taxes + Benefits Together</h3>
              <p>The full picture, not just income tax:</p>
              <ul>
                <li><strong>Taxes:</strong> Federal, state, local, FICA, credits, deductions</li>
                <li><strong>Benefits:</strong> SNAP, Medicaid, ACA subsidies, EITC, CTC, housing, childcare</li>
                <li><strong>Cliffs:</strong> Where $1 more income costs $3 in benefits</li>
              </ul>
              <p className="unlock-conclusion">
                <strong>True marginal rate</strong>—including benefit loss—for any family's decisions.
              </p>
            </div>

            <div className="unlock-card unlock-trust">
              <h3>Filesystem-First: AI-Native Architecture</h3>
              <p>2026 is the year of the filesystem. AI agents work with local files, not black-box APIs.</p>
              <ul>
                <li><strong>CLI sync:</strong> Your scenarios as local YAML files you own</li>
                <li><strong>AI-explorable:</strong> Claude/Cursor/Copilot can read, edit, run simulations</li>
                <li><strong>Verify everything:</strong> Inspect the models, check the assumptions</li>
                <li><strong>Git-native:</strong> Version control your financial plans like code</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Market */}
      <section className="thesis-section" ref={setRef("market")}>
        <div className="thesis-content">
          <h2>5. Market Opportunity</h2>

          <p>
            <strong>140M Americans (Millennials + Gen Z) are underserved by traditional advisors.</strong> They're
            42% of the population but only 14% of advisory clients. They don't want to pay $5K/year for a
            black box—they want transparent tools they control. That's our market.
          </p>

          <div className="market-table">
            <h3>US Market (Year 1-2)</h3>
            <table>
              <thead>
                <tr>
                  <th>Decision</th>
                  <th>Annual Volume</th>
                  <th>Realistic WTP</th>
                  <th>Accessible TAM</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Job offers (multi-state)</td>
                  <td>~5M/year</td>
                  <td>$20-50</td>
                  <td>$100M</td>
                </tr>
                <tr>
                  <td>Benefit cliff navigation</td>
                  <td>~10M affected</td>
                  <td>$0-20 (B2B funded)</td>
                  <td>$50M (B2B)</td>
                </tr>
                <tr>
                  <td>Retirement planning</td>
                  <td>4M retiring/year</td>
                  <td>$50-100</td>
                  <td>$200M</td>
                </tr>
                <tr className="total-row">
                  <td colSpan={3}><strong>US addressable</strong></td>
                  <td><strong>$350M</strong></td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="market-table">
            <h3>International Expansion (Year 2-3)</h3>
            <table>
              <thead>
                <tr>
                  <th>Market</th>
                  <th>Status</th>
                  <th>Key Use Cases</th>
                  <th>TAM Multiplier</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>UK</td>
                  <td>Ready (PolicyEngine-UK)</td>
                  <td>Pension, benefits, tax credits</td>
                  <td>+30%</td>
                </tr>
                <tr>
                  <td>Canada</td>
                  <td>In progress</td>
                  <td>Provincial taxes, CPP/OAS optimization</td>
                  <td>+15%</td>
                </tr>
                <tr>
                  <td>EU (select)</td>
                  <td>AI encoding enables fast entry</td>
                  <td>Cross-border job offers, expat planning</td>
                  <td>+50%</td>
                </tr>
                <tr className="total-row">
                  <td colSpan={3}><strong>Global potential</strong></td>
                  <td><strong>2x US TAM</strong></td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="pricing-tiers">
            <h3>Pricing Strategy</h3>
            <div className="tier-grid">
              <div className="tier-card">
                <div className="tier-name">Free</div>
                <div className="tier-price">$0</div>
                <p>Single scenario, build awareness</p>
              </div>
              <div className="tier-card tier-featured">
                <div className="tier-name">Pro</div>
                <div className="tier-price">$8/mo or $60/yr</div>
                <p>Save scenarios, PDF export, priority support</p>
              </div>
              <div className="tier-card">
                <div className="tier-name">B2B Embed</div>
                <div className="tier-price">$1-5/user</div>
                <p>White-label for HR platforms, benefits sites</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Competition */}
      <section className="thesis-section" ref={setRef("competition")}>
        <div className="thesis-content thesis-content-wide">
          <h2>6. Competitive Landscape</h2>
          <p>We've analyzed 13+ competitors across 4 categories. Despite billions in cumulative funding and millions of users, <strong>none combine Monte Carlo simulation with real tax calculations</strong>.</p>

          {/* Feature Matrix Summary */}
          <div className="feature-matrix-summary">
            <h3>The Gap in the Market</h3>
            <div className="matrix-visual">
              <div className="matrix-header">
                <span></span>
                <span className="feature-label">Monte Carlo</span>
                <span className="feature-label">Real Taxes</span>
                <span className="feature-label">Benefits</span>
                <span className="feature-label">Open Source</span>
              </div>
              <div className="matrix-row matrix-row-eggnest">
                <span className="competitor-name">EggNest</span>
                <span className="feature-check">✓</span>
                <span className="feature-check">✓</span>
                <span className="feature-check">✓</span>
                <span className="feature-check">✓</span>
              </div>
              <div className="matrix-row">
                <span className="competitor-name">All 13 competitors</span>
                <span className="feature-partial">9/13</span>
                <span className="feature-missing">0/13</span>
                <span className="feature-missing">0/13</span>
                <span className="feature-partial">2/13</span>
              </div>
            </div>
            <p className="matrix-insight">
              <strong>Key insight:</strong> Every competitor uses tax estimates or ignores taxes entirely.
              None model benefit cliffs. This is because accurate tax law is genuinely hard—PolicyEngine
              represents years of work to encode actual legislation.
            </p>
          </div>

          {/* Interactive Category Filter */}
          <div className="competitor-filter">
            <h3>Explore by Category</h3>
            <div className="filter-buttons">
              {(Object.keys(categoryLabels) as CompetitorCategory[]).map(cat => (
                <button
                  key={cat}
                  className={`filter-btn ${selectedCategories.has(cat) ? "active" : ""}`}
                  onClick={() => toggleCategory(cat)}
                >
                  {categoryLabels[cat]}
                  <span className="filter-count">
                    {competitors.filter(c => c.category === cat).length}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Competitor Cards */}
          <div className="competitor-cards">
            {filteredCompetitors.map(comp => (
              <div
                key={comp.name}
                className={`competitor-card ${expandedCompetitor === comp.name ? "expanded" : ""}`}
              >
                <div
                  className="competitor-card-header"
                  onClick={() => setExpandedCompetitor(
                    expandedCompetitor === comp.name ? null : comp.name
                  )}
                >
                  <div className="competitor-card-title">
                    <strong>{comp.name}</strong>
                    <span className="competitor-category-badge">
                      {categoryLabels[comp.category]}
                    </span>
                  </div>
                  <div className="competitor-card-meta">
                    <span className="competitor-pricing">{comp.pricing}</span>
                    <span className="expand-icon">{expandedCompetitor === comp.name ? "−" : "+"}</span>
                  </div>
                </div>

                <div className="competitor-card-features">
                  <span className={comp.monteCarlo ? "has-feature" : "no-feature"}>
                    {comp.monteCarlo ? "✓" : "✗"} Monte Carlo
                  </span>
                  <span className={comp.realTaxes ? "has-feature" : "no-feature"}>
                    {comp.realTaxes ? "✓" : "✗"} Real Taxes
                  </span>
                  <span className={comp.benefitsModeling ? "has-feature" : "no-feature"}>
                    {comp.benefitsModeling ? "✓" : "✗"} Benefits
                  </span>
                  <span className={comp.openSource ? "has-feature" : "no-feature"}>
                    {comp.openSource ? "✓" : "✗"} Open Source
                  </span>
                </div>

                {expandedCompetitor === comp.name && (
                  <div className="competitor-card-details">
                    <div className="detail-section">
                      <h4>Strengths</h4>
                      <ul>
                        {comp.strengths.map((s, i) => (
                          <li key={i}>{s}</li>
                        ))}
                      </ul>
                    </div>
                    <div className="detail-section detail-gaps">
                      <h4>Gaps (Our Opportunity)</h4>
                      <ul>
                        {comp.gaps.map((g, i) => (
                          <li key={i}>{g}</li>
                        ))}
                      </ul>
                    </div>
                    {comp.url && (
                      <a
                        href={comp.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="competitor-link"
                      >
                        Visit {comp.name} →
                      </a>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Adjacent Categories */}
          <div className="adjacent-section">
            <h3>Adjacent Categories</h3>
            <p>These tools serve related needs but don't solve the core problem:</p>
            <div className="adjacent-grid">
              <div className="adjacent-card">
                <strong>Tax Software</strong>
                <span className="adjacent-examples">TurboTax, H&R Block</span>
                <p>Backward-looking only. No "what if I earn more?" simulation.</p>
              </div>
              <div className="adjacent-card">
                <strong>Salary Comparison</strong>
                <span className="adjacent-examples">Levels.fyi, Glassdoor</span>
                <p>Comp data, but no after-tax net impact for your situation.</p>
              </div>
              <div className="adjacent-card">
                <strong>Cost of Living</strong>
                <span className="adjacent-examples">Numbeo, BestPlaces</span>
                <p>Rough averages. No personalized tax/benefit impact.</p>
              </div>
              <div className="adjacent-card">
                <strong>Budgeting Apps</strong>
                <span className="adjacent-examples">YNAB, Copilot, Monarch</span>
                <p>Track past spending. No future "what if" projections.</p>
              </div>
            </div>
          </div>

          {/* Differentiation */}
          <div className="differentiator-section">
            <h3>EggNest Differentiation</h3>
            <div className="diff-grid">
              <div className="diff-item">
                <strong>Real Tax Calculations</strong>
                <p>PolicyEngine models actual tax law—federal, state, credits, phase-outs—not simplified estimates</p>
              </div>
              <div className="diff-item">
                <strong>Benefits Integration</strong>
                <p>SNAP, Medicaid, ACA subsidies, EITC cliffs—the full picture for all income levels</p>
              </div>
              <div className="diff-item">
                <strong>Open Source</strong>
                <p>Verify the math yourself. No black box. Builds trust competitors can't match</p>
              </div>
              <div className="diff-item">
                <strong>Modern UX</strong>
                <p>Clean wizard interface, not 250+ input fields. Complexity available when you need it</p>
              </div>
            </div>
          </div>

          {/* Moat */}
          <div className="moat-section">
            <h3>Defensibility</h3>
            <div className="moat-grid">
              <div className="moat-item">
                <strong>Cosilico tax engine</strong>
                <p>AI-encoded tax rules enable fast international expansion competitors can't match</p>
              </div>
              <div className="moat-item">
                <strong>AI-native architecture</strong>
                <p>Filesystem-first design lets AI agents explore your data—competitors are API-locked</p>
              </div>
              <div className="moat-item">
                <strong>Open source trust</strong>
                <p>Inspect the models, verify the math. Black-box competitors can't replicate this.</p>
              </div>
              <div className="moat-item">
                <strong>Multi-country coverage</strong>
                <p>US, UK, Canada—with EU on deck. Same product, new markets.</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Model */}
      <section className="thesis-section" ref={setRef("model")}>
        <div className="thesis-content">
          <h2>7. Business Model</h2>

          <div className="revenue-streams">
            <div className="stream-card stream-primary">
              <h3>Consumer Direct (Primary)</h3>
              <p>Free tier democratizes access to probabilistic planning. Pro tier for power users who want saved scenarios, comparisons, and exports.</p>
              <div className="stream-metric">Goal: Replace the $5K/year advisor with a $60/year tool</div>
            </div>
            <div className="stream-card">
              <h3>B2B2C Partnerships</h3>
              <p>Embed in HR platforms, salary sites, benefits navigators. Reach people at decision moments.</p>
              <div className="stream-metric">Target: $1-5/user or $10K-50K/year enterprise</div>
            </div>
            <div className="stream-card">
              <h3>Open Source Ecosystem</h3>
              <p>EggNest Python package (MIT license) lets developers build on our engine. Drives adoption and trust, not direct revenue.</p>
              <div className="stream-metric">Strategic: Adoption over monetization</div>
            </div>
          </div>

          <div className="projections">
            <h3>Revenue Projections (Conservative)</h3>
            <table>
              <thead>
                <tr>
                  <th>Year</th>
                  <th>Free Users</th>
                  <th>Pro Subs</th>
                  <th>B2B Embed</th>
                  <th>Total ARR</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>1</td>
                  <td>25K</td>
                  <td>$8K</td>
                  <td>$0</td>
                  <td>$8K</td>
                </tr>
                <tr>
                  <td>2</td>
                  <td>100K</td>
                  <td>$40K</td>
                  <td>$30K</td>
                  <td>$70K</td>
                </tr>
                <tr>
                  <td>3</td>
                  <td>300K</td>
                  <td>$120K</td>
                  <td>$150K</td>
                  <td>$270K</td>
                </tr>
                <tr>
                  <td>4</td>
                  <td>750K</td>
                  <td>$300K</td>
                  <td>$400K</td>
                  <td>$700K</td>
                </tr>
                <tr>
                  <td>5</td>
                  <td>1.5M</td>
                  <td>$600K</td>
                  <td>$900K</td>
                  <td>$1.5M</td>
                </tr>
              </tbody>
            </table>
            <p className="projection-note">
              <strong>The bet:</strong> If we can get 1% of people who would've paid an advisor $5K to pay us $60 instead,
              we win. Open source builds trust; consumer-direct is the primary path.
            </p>
          </div>

          <div className="comparables">
            <h3>Realistic Comparables</h3>
            <div className="comparable-grid">
              <div className="comparable">
                <span className="comparable-name">Boldin</span>
                <span className="comparable-value">~$10M ARR</span>
                <span className="comparable-type">After 10+ years</span>
              </div>
              <div className="comparable">
                <span className="comparable-name">ProjectionLab</span>
                <span className="comparable-value">~$500K ARR</span>
                <span className="comparable-type">Solo founder, 3 years</span>
              </div>
              <div className="comparable">
                <span className="comparable-name">FI Calc</span>
                <span className="comparable-value">$0</span>
                <span className="comparable-type">Free, open source</span>
              </div>
              <div className="comparable">
                <span className="comparable-name">Pralana</span>
                <span className="comparable-value">~$200K ARR</span>
                <span className="comparable-type">Niche, loyal base</span>
              </div>
            </div>
            <p className="comparable-note">
              <strong>Reality:</strong> This is a $500K-$10M ARR category for consumer tools.
              B2B embedded deals are the path to larger outcomes.
            </p>
          </div>
        </div>
      </section>

      {/* GTM */}
      <section className="thesis-section" ref={setRef("gtm")}>
        <div className="thesis-content">
          <h2>8. Go-to-Market</h2>

          <div className="gtm-phases">
            <div className="gtm-phase gtm-now">
              <h3>Phase 1: FIRE Community (Now)</h3>
              <ul>
                <li>Launch on Reddit r/financialindependence, r/Fire, r/Bogleheads</li>
                <li>These people already distrust advisors—they're our early adopters</li>
                <li>Goal: 5K users who spread the "you don't need an advisor" message</li>
              </ul>
            </div>
            <div className="gtm-phase">
              <h3>Phase 2: Millennial/Gen Z Channels (6 months)</h3>
              <ul>
                <li>YouTube, TikTok, Instagram—where 79% of young people get financial info</li>
                <li>Content: "What your advisor isn't telling you about uncertainty"</li>
                <li>Target the 42% who are underserved by traditional advisors</li>
              </ul>
            </div>
            <div className="gtm-phase">
              <h3>Phase 3: B2B Partnerships (Year 2)</h3>
              <ul>
                <li>Embed in HR platforms, benefits navigators—reach people at decision moments</li>
                <li>Partner with fee-only advisor directories (as alternative, not tool for advisors)</li>
                <li>Target nonprofits helping low-income navigate benefit cliffs</li>
              </ul>
            </div>
            <div className="gtm-phase">
              <h3>Phase 4: International (Year 2-3)</h3>
              <ul>
                <li>UK launch—same advisor distrust, same need for probabilistic tools</li>
                <li>Canada as Cosilico coverage expands</li>
                <li>Localized content for each market's advisory fee structure</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Team */}
      <section className="thesis-section" ref={setRef("team")}>
        <div className="thesis-content">
          <h2>9. Team</h2>

          <div className="team-grid">
            <div className="team-now">
              <h3>Now</h3>
              <p>Technical founder</p>
            </div>
            <div className="team-year1">
              <h3>Year 1</h3>
              <ul>
                <li>Growth marketer</li>
                <li>Part-time designer</li>
              </ul>
            </div>
            <div className="team-year2">
              <h3>Year 2</h3>
              <ul>
                <li>2 engineers (simulation engine, API)</li>
                <li>Data scientist (model improvement)</li>
                <li>Content marketer</li>
              </ul>
            </div>
            <div className="team-year3">
              <h3>Year 3+</h3>
              <ul>
                <li>Sales (API/partnerships)</li>
                <li>Customer success</li>
                <li>Additional engineers</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Risks */}
      <section className="thesis-section" ref={setRef("risks")}>
        <div className="thesis-content">
          <h2>10. Risks & Hard Questions</h2>

          <div className="risks-grid">
            <div className="risk-card risk-high">
              <h4>Do people actually care about tax accuracy?</h4>
              <p>Unknown. "Close enough" may be good enough for most users. Must validate early.</p>
            </div>
            <div className="risk-card risk-high">
              <h4>Consumer fintech conversion is brutal</h4>
              <p>Boldin/ProjectionLab struggle to convert. B2B may be required path to revenue.</p>
            </div>
            <div className="risk-card risk-medium">
              <h4>Cosilico execution risk</h4>
              <p>Transitioning from PolicyEngine to AI-encoded rules. Timeline and accuracy TBD.</p>
            </div>
            <div className="risk-card risk-medium">
              <h4>International expansion complexity</h4>
              <p>Each country has unique tax/benefit systems. UK ready, others need validation.</p>
            </div>
            <div className="risk-card">
              <h4>FIRE community may not pay</h4>
              <p>They love spreadsheets and free tools. May drive awareness but not revenue.</p>
            </div>
            <div className="risk-card">
              <h4>B2B sales cycle is long</h4>
              <p>HR platforms move slowly. Need consumer traction to prove value first.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Summary */}
      <section className="thesis-summary">
        <div className="thesis-content">
          <h2>Summary</h2>
          <div className="summary-points">
            <p><strong>The problem:</strong> People don't think about uncertainty properly. Advisors exploit this with confident single-point estimates and product sales.</p>
            <p><strong>The opportunity:</strong> 140M Millennials and Gen Z want DIY tools, not $5K/year advisors. They're 42% of the population, 14% of advisory clients.</p>
            <p><strong>The solution:</strong> Robinhood for financial planning—real probabilistic tools with real tax math. Open source, transparent, no salespeople.</p>
            <p><strong>The plan:</strong></p>
            <ul>
              <li>Launch with FIRE community who already distrust advisors</li>
              <li>Expand to YouTube/TikTok/Instagram where young people actually are</li>
              <li>International expansion via Cosilico's AI-encoded tax rules</li>
              <li>Stay honest about what works and what doesn't</li>
            </ul>
            <p className="summary-tagline">
              Financial planning for people who want to see the numbers themselves.
            </p>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="thesis-cta">
        <h2>Try the Simulator</h2>
        <p>See your retirement projections in 30 seconds.</p>
        <div className="cta-buttons">
          <a href="https://app.eggnest.co" className="btn-primary">
            Launch App
          </a>
          <a href="/" className="btn-secondary">
            Back to Home
          </a>
        </div>
      </section>
    </div>
  );
}
