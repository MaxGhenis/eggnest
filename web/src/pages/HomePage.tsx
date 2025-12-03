import { Link } from "react-router-dom";
import "../styles/Home.css";

export function HomePage() {
  return (
    <div className="home">
      {/* Hero */}
      <section className="hero">
        <nav className="nav">
          <div className="logo">FinSim</div>
          <div className="nav-links">
            <a href="#features">Features</a>
            <a href="#how-it-works">How It Works</a>
            <Link to="/app" className="nav-cta">
              Launch App
            </Link>
          </div>
        </nav>

        <div className="hero-content">
          <h1>
            Know if your money
            <br />
            will last.
          </h1>
          <p className="hero-subtitle">
            Monte Carlo simulation meets real tax law. See thousands of possible
            futures for your retirement—not just the rosy average.
          </p>
          <div className="hero-cta">
            <Link to="/app" className="btn-primary">
              Try the Simulator
            </Link>
            <a href="#how-it-works" className="btn-secondary">
              See How It Works
            </a>
          </div>
        </div>

        <div className="hero-visual">
          <div className="chart-preview">
            <svg viewBox="0 0 400 200" className="preview-chart">
              {/* Confidence band */}
              <path
                d="M 20 150 Q 100 140, 200 100 T 380 40 L 380 180 Q 200 160, 100 170 T 20 180 Z"
                fill="rgba(99, 102, 241, 0.1)"
              />
              {/* Median line */}
              <path
                d="M 20 160 Q 100 150, 200 120 T 380 80"
                fill="none"
                stroke="#6366f1"
                strokeWidth="3"
              />
              {/* Upper bound */}
              <path
                d="M 20 150 Q 100 140, 200 100 T 380 40"
                fill="none"
                stroke="#6366f1"
                strokeWidth="1"
                opacity="0.5"
              />
              {/* Lower bound */}
              <path
                d="M 20 170 Q 100 165, 200 150 T 380 140"
                fill="none"
                stroke="#6366f1"
                strokeWidth="1"
                opacity="0.5"
              />
            </svg>
            <div className="chart-labels">
              <span className="label-good">95th percentile</span>
              <span className="label-median">Median outcome</span>
              <span className="label-bad">5th percentile</span>
            </div>
          </div>
        </div>
      </section>

      {/* Problem */}
      <section className="problem" id="why">
        <h2>The 4% rule is a guess.</h2>
        <p>
          Most retirement calculators use averages. But markets don't move in
          averages—they crash, they boom, they surprise. A single "expected
          return" hides the range of outcomes that could make or break your
          retirement.
        </p>
        <div className="problem-stats">
          <div className="stat">
            <span className="stat-value">30%</span>
            <span className="stat-label">
              of retirees following the 4% rule run out of money in bad
              sequences
            </span>
          </div>
          <div className="stat">
            <span className="stat-value">$200K+</span>
            <span className="stat-label">
              difference between 25th and 75th percentile outcomes
            </span>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="features" id="features">
        <h2>What makes FinSim different</h2>
        <div className="feature-grid">
          <div className="feature-card">
            <div className="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M3 3v18h18" />
                <path d="M7 16l4-4 4 4 5-6" />
              </svg>
            </div>
            <h3>10,000 Simulations</h3>
            <p>
              Not one projection—thousands. See the full range of what could
              happen based on historical market behavior.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <path d="M3 9h18M9 21V9" />
              </svg>
            </div>
            <h3>Real Tax Calculations</h3>
            <p>
              Powered by PolicyEngine. Actual federal and state tax law—not
              estimates. See your true after-tax income.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <circle cx="12" cy="12" r="9" />
                <path d="M12 6v6l4 2" />
              </svg>
            </div>
            <h3>Mortality-Adjusted</h3>
            <p>
              Accounts for the probability you'll actually need the money.
              Earlier years matter more than year 40.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                <circle cx="9" cy="7" r="4" />
                <path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
              </svg>
            </div>
            <h3>Joint Planning</h3>
            <p>
              Model couples with different ages, incomes, and Social Security.
              See what happens when one spouse passes.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M12 2L2 7l10 5 10-5-10-5z" />
                <path d="M2 17l10 5 10-5M2 12l10 5 10-5" />
              </svg>
            </div>
            <h3>Multiple Income Sources</h3>
            <p>
              Social Security with COLA. Pensions. Employment income until
              retirement. See how they all interact.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
            </div>
            <h3>Annuity Comparison</h3>
            <p>
              Should you buy an annuity or invest? Compare guaranteed income vs.
              market upside with real numbers.
            </p>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="how-it-works" id="how-it-works">
        <h2>How it works</h2>
        <div className="steps">
          <div className="step">
            <div className="step-number">1</div>
            <h3>Enter your situation</h3>
            <p>
              Age, savings, income sources, state. Takes about 2 minutes.
            </p>
          </div>
          <div className="step">
            <div className="step-number">2</div>
            <h3>We simulate 10,000 futures</h3>
            <p>
              Using historical market data and actual tax law to model each
              year of your retirement.
            </p>
          </div>
          <div className="step">
            <div className="step-number">3</div>
            <h3>See your probability of success</h3>
            <p>
              Not just "you'll be fine"—the actual percentage chance your money
              lasts, with the full distribution of outcomes.
            </p>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="cta">
        <h2>Stop guessing. Start simulating.</h2>
        <p>Free to use. No account required.</p>
        <Link to="/app" className="btn-primary btn-large">
          Launch the Simulator
        </Link>
      </section>

      {/* Footer */}
      <footer className="footer">
        <div className="footer-content">
          <div className="footer-brand">
            <div className="logo">FinSim</div>
            <p>Monte Carlo retirement planning with real tax calculations.</p>
          </div>
          <div className="footer-links">
            <div className="footer-col">
              <h4>Product</h4>
              <Link to="/app">Simulator</Link>
              <a href="#features">Features</a>
              <a href="#how-it-works">How It Works</a>
            </div>
            <div className="footer-col">
              <h4>Company</h4>
              <a href="mailto:hello@finsim.app">Contact</a>
            </div>
          </div>
        </div>
        <div className="footer-bottom">
          <p>
            Tax calculations powered by{" "}
            <a href="https://policyengine.org" target="_blank" rel="noopener">
              PolicyEngine
            </a>
          </p>
          <p className="disclaimer">
            FinSim provides educational projections only. This is not financial
            advice. Consult a qualified financial advisor for personalized
            recommendations.
          </p>
        </div>
      </footer>
    </div>
  );
}
