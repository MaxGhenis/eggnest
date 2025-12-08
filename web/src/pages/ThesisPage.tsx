import { useState, useEffect, useRef } from "react";
import "../styles/Thesis.css";

type Section = "problem" | "vision" | "phases" | "unlock" | "market" | "competition" | "model" | "gtm" | "team" | "risks";

const sections: Section[] = ["problem", "vision", "phases", "unlock", "market", "competition", "model", "gtm", "team", "risks"];

export function ThesisPage() {
  const [activeSection, setActiveSection] = useState<Section>("problem");

  const sectionRefs = useRef<Record<Section, HTMLElement | null>>(
    Object.fromEntries(sections.map(s => [s, null])) as Record<Section, HTMLElement | null>
  );

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
        </div>
      </section>

      {/* Vision */}
      <section className="thesis-section" ref={setRef("vision")}>
        <div className="thesis-content">
          <h2>2. The Vision</h2>
          <p>
            EggNest is the <strong>financial simulation engine for life decisions</strong>. We answer "what if?" for every major financial decision—job changes, relocations, home purchases, having children, and more.
          </p>

          <div className="vision-stack">
            <div className="stack-item stack-model">
              <span className="stack-label">Model</span>
              <span className="stack-value">B2C freemium SaaS, open source core</span>
            </div>
            <div className="stack-item stack-wedge">
              <span className="stack-label">Wedge</span>
              <span className="stack-value">Monte Carlo retirement simulator with real tax calculations</span>
            </div>
            <div className="stack-item stack-vision">
              <span className="stack-label">Vision</span>
              <span className="stack-value">The simulation layer for all life decisions</span>
            </div>
          </div>

          <div className="vision-insight">
            <h3>Why This Works</h3>
            <p>
              <strong>PolicyEngine is the unlock.</strong> Most "what if" tools fail because taxes are too complex. PolicyEngine solves this with actual tax law (not estimates), federal + state + local coverage, all credits and deductions, benefit program interactions, and continuous updates as laws change.
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
              <p>The wedge. Prove the model with the highest-stakes, most calculable decision.</p>
              <ul>
                <li>Monte Carlo simulation</li>
                <li>Real federal + state taxes via PolicyEngine</li>
                <li>Social Security optimization</li>
                <li>Annuity comparison</li>
              </ul>
            </div>

            <div className="phase-card">
              <div className="phase-badge">Year 2</div>
              <h3>Phase 2: Life Event Simulator</h3>
              <p>Expand to adjacent decisions that share the same engine.</p>
              <ul>
                <li><strong>Job Change:</strong> Total comp, state taxes, benefits</li>
                <li><strong>Relocation:</strong> SALT cap, property tax, cost of living</li>
                <li><strong>Home Purchase:</strong> Mortgage interest, rent vs buy Monte Carlo</li>
              </ul>
            </div>

            <div className="phase-card">
              <div className="phase-badge">Year 3</div>
              <h3>Phase 3: Family Planning</h3>
              <p>High emotional stakes, high financial complexity.</p>
              <ul>
                <li><strong>Child Cost:</strong> Childcare, tax credits, income impact</li>
                <li><strong>Education:</strong> College ROI, student loans, trade school comparison</li>
              </ul>
            </div>

            <div className="phase-card">
              <div className="phase-badge">Year 4+</div>
              <h3>Phase 4: Full Life Simulator</h3>
              <p>The everything engine.</p>
              <ul>
                <li>Career path modeling</li>
                <li>Business formation (LLC vs S-corp)</li>
                <li>Estate planning</li>
                <li>Healthcare cost projection</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Unlock */}
      <section className="thesis-section" ref={setRef("unlock")}>
        <div className="thesis-content">
          <h2>4. Why Monte Carlo + PolicyEngine</h2>

          <div className="unlock-grid">
            <div className="unlock-card">
              <h3>Monte Carlo is the Right Framework</h3>
              <p>Life is uncertain. Single-point estimates are misleading.</p>
              <ul>
                <li>Job: "What if I get laid off in year 2?"</li>
                <li>House: "What if interest rates change?"</li>
                <li>Retirement: "What if markets crash early?"</li>
                <li>Child: "What if childcare costs rise faster than inflation?"</li>
              </ul>
              <p className="unlock-conclusion">
                <strong>Monte Carlo shows the distribution of outcomes</strong>, not just the expected case.
              </p>
            </div>

            <div className="unlock-card">
              <h3>PolicyEngine Models Both Sides</h3>
              <p>Taxes AND benefits in one engine:</p>
              <ul>
                <li><strong>Taxes:</strong> Federal, state, local, FICA, credits, deductions</li>
                <li><strong>Benefits:</strong> SNAP, Medicaid, ACA subsidies, EITC, CTC, housing assistance, childcare subsidies, SSI, TANF</li>
              </ul>
              <p className="unlock-conclusion">
                <strong>True marginal rate</strong>—including benefit loss—for any family's decisions.
              </p>
            </div>

            <div className="unlock-card unlock-trust">
              <h3>Open Source Builds Trust</h3>
              <p>Financial decisions are high-stakes. People don't trust black boxes.</p>
              <ul>
                <li>Users can verify the math</li>
                <li>Community catches errors</li>
                <li>No hidden agenda (we're not selling products)</li>
                <li>Transparent methodology</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Market */}
      <section className="thesis-section" ref={setRef("market")}>
        <div className="thesis-content">
          <h2>5. Market Opportunity</h2>

          <div className="market-table">
            <table>
              <thead>
                <tr>
                  <th>Decision</th>
                  <th>Annual US</th>
                  <th>Willingness to Pay</th>
                  <th>TAM</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Retirement planning</td>
                  <td>4M retiring/year</td>
                  <td>High ($100+)</td>
                  <td>$400M+</td>
                </tr>
                <tr>
                  <td>Job changes</td>
                  <td>50M/year</td>
                  <td>Medium ($20-50)</td>
                  <td>$1B+</td>
                </tr>
                <tr>
                  <td>Home purchases</td>
                  <td>5M/year</td>
                  <td>High ($50-100)</td>
                  <td>$500M+</td>
                </tr>
                <tr>
                  <td>Relocations</td>
                  <td>30M/year</td>
                  <td>Medium ($20-50)</td>
                  <td>$600M+</td>
                </tr>
                <tr>
                  <td>New children</td>
                  <td>3.6M/year</td>
                  <td>Medium ($30-50)</td>
                  <td>$150M+</td>
                </tr>
                <tr className="total-row">
                  <td colSpan={3}><strong>Total addressable</strong></td>
                  <td><strong>$3B+</strong></td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="pricing-tiers">
            <h3>Pricing Tiers</h3>
            <div className="tier-grid">
              <div className="tier-card">
                <div className="tier-name">Free</div>
                <div className="tier-price">$0</div>
                <p>Single scenario, basic inputs</p>
              </div>
              <div className="tier-card tier-featured">
                <div className="tier-name">Pro</div>
                <div className="tier-price">$12/mo or $99/yr</div>
                <p>Save scenarios, compare side-by-side, PDF export</p>
              </div>
              <div className="tier-card">
                <div className="tier-name">Family</div>
                <div className="tier-price">$20/mo or $179/yr</div>
                <p>Multiple life events, shared household planning</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Competition */}
      <section className="thesis-section" ref={setRef("competition")}>
        <div className="thesis-content">
          <h2>6. Competitive Landscape</h2>
          <p>The retirement planning space has several established players, but none combine Monte Carlo simulation with real tax calculations:</p>

          <div className="competitor-table">
            <h3>Direct Competitors (Retirement Planning)</h3>
            <table>
              <thead>
                <tr>
                  <th>Competitor</th>
                  <th>Pricing</th>
                  <th>Strengths</th>
                  <th>Gap</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><strong>MaxiFi</strong></td>
                  <td>$109-149/yr</td>
                  <td>Economist-backed (Kotlikoff), living standard focus, Roth optimizer</td>
                  <td>No real tax integration, complex UI, closed source</td>
                </tr>
                <tr>
                  <td><strong>Boldin</strong> (NewRetirement)</td>
                  <td>Free–$144/yr</td>
                  <td>250+ inputs, good UI, CFP access option</td>
                  <td>Tax estimates not actual law, no benefit modeling</td>
                </tr>
                <tr>
                  <td><strong>ProjectionLab</strong></td>
                  <td>Free–$109/yr</td>
                  <td>Beautiful charts, excellent what-if scenarios</td>
                  <td>Tax modeling is estimates, no state-specific accuracy</td>
                </tr>
                <tr>
                  <td><strong>Pralana</strong></td>
                  <td>~$100/yr</td>
                  <td>Most detailed analysis, Excel power users love it</td>
                  <td>Steep learning curve, Excel-based, limited accessibility</td>
                </tr>
                <tr>
                  <td><strong>Empower</strong> (Personal Capital)</td>
                  <td>Free</td>
                  <td>Free, account aggregation, solid Monte Carlo</td>
                  <td>Leads to wealth management sales, simplified tax model</td>
                </tr>
                <tr>
                  <td><strong>FI Calc</strong></td>
                  <td>Free</td>
                  <td>Great for FIRE community, historical backtesting</td>
                  <td>No tax modeling, no benefit integration</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="competitor-table">
            <h3>Adjacent Categories</h3>
            <table>
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Examples</th>
                  <th>Gap</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Tax software</td>
                  <td>TurboTax, H&R Block</td>
                  <td>Backward-looking only, no "what if" simulation</td>
                </tr>
                <tr>
                  <td>Salary comparison</td>
                  <td>Levels.fyi, Glassdoor</td>
                  <td>Comp data but no after-tax net impact</td>
                </tr>
                <tr>
                  <td>Cost of living</td>
                  <td>Numbeo, BestPlaces</td>
                  <td>Rough estimates, no personalization</td>
                </tr>
                <tr>
                  <td>Budgeting apps</td>
                  <td>YNAB, Copilot</td>
                  <td>Track spending, no future projection</td>
                </tr>
                <tr>
                  <td>Robo-advisors</td>
                  <td>Betterment, Wealthfront</td>
                  <td>Investment management, not decision simulation</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="differentiator-section">
            <h3>EggNest Differentiation</h3>
            <div className="diff-grid">
              <div className="diff-item">
                <strong>Real Tax Calculations</strong>
                <p>PolicyEngine models actual tax law—federal, state, credits, phase-outs—not estimates</p>
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
                <p>Clean wizard interface, not 250+ input fields. Complexity when you need it</p>
              </div>
            </div>
          </div>

          <div className="moat-section">
            <h3>Our Moat</h3>
            <div className="moat-grid">
              <div className="moat-item">
                <strong>PolicyEngine integration</strong>
                <p>Years of tax law encoded, continuously updated</p>
              </div>
              <div className="moat-item">
                <strong>Open source trust</strong>
                <p>Competitors can't replicate transparency</p>
              </div>
              <div className="moat-item">
                <strong>Data network effects</strong>
                <p>More users → better assumptions → better simulations</p>
              </div>
              <div className="moat-item">
                <strong>Brand</strong>
                <p>"EggNest it" becomes the verb for life decision simulation</p>
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
              <h3>Consumer Subscriptions (Primary)</h3>
              <p>Free tier drives awareness. Pro/Family tiers for power users.</p>
              <div className="stream-metric">Target: 1-2% conversion, $100 ARPU</div>
            </div>
            <div className="stream-card">
              <h3>API Access (Year 2+)</h3>
              <p>HR platforms, real estate, fintech apps. "Add life simulation to your product."</p>
              <div className="stream-metric">Pricing: $0.10-1.00/simulation</div>
            </div>
            <div className="stream-card">
              <h3>Embedded Partnerships (Year 3+)</h3>
              <p>Employers for relocation packages. Universities for degree ROI. Benefits platforms.</p>
            </div>
          </div>

          <div className="projections">
            <h3>Revenue Projections</h3>
            <table>
              <thead>
                <tr>
                  <th>Year</th>
                  <th>Users</th>
                  <th>Subscribers</th>
                  <th>API Revenue</th>
                  <th>Total ARR</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>1</td>
                  <td>100K</td>
                  <td>1K</td>
                  <td>$0</td>
                  <td>$100K</td>
                </tr>
                <tr>
                  <td>2</td>
                  <td>500K</td>
                  <td>7.5K</td>
                  <td>$100K</td>
                  <td>$850K</td>
                </tr>
                <tr>
                  <td>3</td>
                  <td>2M</td>
                  <td>30K</td>
                  <td>$500K</td>
                  <td>$3.5M</td>
                </tr>
                <tr>
                  <td>4</td>
                  <td>5M</td>
                  <td>100K</td>
                  <td>$2M</td>
                  <td>$12M</td>
                </tr>
                <tr>
                  <td>5</td>
                  <td>15M</td>
                  <td>300K</td>
                  <td>$10M</td>
                  <td>$40M</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="comparables">
            <h3>Comparable Exits</h3>
            <div className="comparable-grid">
              <div className="comparable">
                <span className="comparable-name">Credit Karma</span>
                <span className="comparable-value">$7B</span>
                <span className="comparable-type">Intuit acquisition</span>
              </div>
              <div className="comparable">
                <span className="comparable-name">NerdWallet</span>
                <span className="comparable-value">$5B</span>
                <span className="comparable-type">IPO</span>
              </div>
              <div className="comparable">
                <span className="comparable-name">Personal Capital</span>
                <span className="comparable-value">$1B</span>
                <span className="comparable-type">Empower acquisition</span>
              </div>
              <div className="comparable">
                <span className="comparable-name">Mint</span>
                <span className="comparable-value">$170M</span>
                <span className="comparable-type">Intuit acquisition</span>
              </div>
            </div>
            <p className="comparable-note">
              EggNest's category: <strong>Life decision simulation</strong>. Bigger than any single vertical.
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
              <h3>Phase 1: Retirement Community (Now)</h3>
              <ul>
                <li>Launch on HN, Reddit (r/financialindependence, r/Fire)</li>
                <li>SEO: "Monte Carlo retirement calculator"</li>
                <li>Build credibility with FIRE community</li>
              </ul>
            </div>
            <div className="gtm-phase">
              <h3>Phase 2: Job/Relocation (Year 2)</h3>
              <ul>
                <li>Target: Tech workers evaluating offers</li>
                <li>Channels: Blind, Levels.fyi, LinkedIn</li>
                <li>Partner with salary transparency sites</li>
              </ul>
            </div>
            <div className="gtm-phase">
              <h3>Phase 3: Home/Family (Year 3)</h3>
              <ul>
                <li>Target: First-time homebuyers, new parents</li>
                <li>Channels: Real estate content, parenting communities</li>
                <li>Partner with real estate platforms</li>
              </ul>
            </div>
            <div className="gtm-phase">
              <h3>Phase 4: Platform (Year 4+)</h3>
              <ul>
                <li>API launches</li>
                <li>Embedded partnerships</li>
                <li>B2B sales team</li>
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
          <h2>10. Risks & Mitigations</h2>

          <div className="risks-grid">
            <div className="risk-card">
              <h4>Complexity of multi-domain simulation</h4>
              <p>Start with retirement, prove model, expand carefully</p>
            </div>
            <div className="risk-card">
              <h4>Data acquisition costs</h4>
              <p>Partner with data providers, crowdsource benchmarks</p>
            </div>
            <div className="risk-card">
              <h4>PolicyEngine dependency</h4>
              <p>Deep partnership, contribute upstream, potential acquisition</p>
            </div>
            <div className="risk-card">
              <h4>Big tech competition</h4>
              <p>Open source moat, move fast, niche expertise</p>
            </div>
            <div className="risk-card">
              <h4>User trust in financial AI</h4>
              <p>Transparency, show methodology, no product recommendations</p>
            </div>
          </div>
        </div>
      </section>

      {/* Summary */}
      <section className="thesis-summary">
        <div className="thesis-content">
          <h2>Summary</h2>
          <div className="summary-points">
            <p><strong>Starting point:</strong> Monte Carlo retirement calculator with real taxes.</p>
            <p><strong>Vision:</strong> The simulation engine for every major life decision.</p>
            <p><strong>Why now:</strong></p>
            <ul>
              <li>PolicyEngine makes real tax calculation possible</li>
              <li>Open source builds trust in financial tools</li>
              <li>People are increasingly making decisions without advisors</li>
            </ul>
            <p className="summary-tagline">
              The nest isn't just for retirement. It's where you go to see all your possible futures.
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
