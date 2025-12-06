import "../styles/Home.css";

// In production, this is app.eggnest.co
const APP_URL = import.meta.env.PROD ? "https://app.eggnest.co" : "http://localhost:5174";

export function HomePage() {
  return (
    <div className="home">
      {/* Hero */}
      <section className="hero">
        <nav className="nav">
          <a href="/" className="logo">
            <img src="/logo.svg" alt="EggNest" height="32" />
          </a>
          <div className="nav-links">
            <a href="#features">Features</a>
            <a href="#how-it-works">How It Works</a>
            <a href={APP_URL} className="nav-cta">
              Launch App
            </a>
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
            <a href={APP_URL} className="btn-primary">
              Try the Simulator
            </a>
            <a href="#how-it-works" className="btn-secondary">
              See How It Works
            </a>
          </div>
        </div>

        <div className="hero-visual">
          <div className="chart-preview">
            <svg viewBox="0 0 420 240" className="preview-chart">
              {/* Y-axis */}
              <line x1="50" y1="20" x2="50" y2="200" stroke="#e5e7eb" strokeWidth="1" />
              {/* X-axis */}
              <line x1="50" y1="200" x2="400" y2="200" stroke="#e5e7eb" strokeWidth="1" />

              {/* Y-axis label */}
              <text x="15" y="110" fontSize="11" fill="#6b7280" transform="rotate(-90, 15, 110)">Portfolio Value</text>

              {/* X-axis label */}
              <text x="225" y="230" fontSize="11" fill="#6b7280" textAnchor="middle">Years in Retirement</text>

              {/* X-axis ticks */}
              <text x="50" y="215" fontSize="10" fill="#9ca3af" textAnchor="middle">0</text>
              <text x="165" y="215" fontSize="10" fill="#9ca3af" textAnchor="middle">10</text>
              <text x="280" y="215" fontSize="10" fill="#9ca3af" textAnchor="middle">20</text>
              <text x="395" y="215" fontSize="10" fill="#9ca3af" textAnchor="middle">30</text>

              {/* Outer confidence band (5th-95th) */}
              <path
                d="M 50 100 Q 120 90, 200 60 T 395 25 L 395 195 Q 280 180, 200 170 T 50 140 Z"
                fill="rgba(217, 119, 6, 0.1)"
              />

              {/* Inner confidence band (25th-75th) */}
              <path
                d="M 50 115 Q 120 105, 200 80 T 395 50 L 395 175 Q 280 165, 200 155 T 50 130 Z"
                fill="rgba(217, 119, 6, 0.15)"
              />

              {/* Median line */}
              <path
                d="M 50 120 Q 150 110, 250 100 T 395 95"
                fill="none"
                stroke="#d97706"
                strokeWidth="3"
                strokeLinecap="round"
              />

              {/* Legend */}
              <g transform="translate(260, 50)">
                <rect x="0" y="0" width="130" height="70" fill="white" rx="4" opacity="0.9" />
                <rect x="10" y="12" width="20" height="3" fill="#d97706" />
                <text x="35" y="16" fontSize="10" fill="#374151">Median outcome</text>
                <rect x="10" y="30" width="20" height="8" fill="rgba(217, 119, 6, 0.25)" />
                <text x="35" y="36" fontSize="10" fill="#374151">Likely range</text>
                <rect x="10" y="48" width="20" height="8" fill="rgba(217, 119, 6, 0.1)" />
                <text x="35" y="54" fontSize="10" fill="#374151">Possible range</text>
              </g>

              {/* Annotation arrow pointing to fan */}
              <text x="85" y="55" fontSize="10" fill="#d97706" fontWeight="500">10,000 simulations</text>
              <path d="M 130 60 L 150 80" stroke="#d97706" strokeWidth="1" fill="none" markerEnd="url(#arrowhead)" />
            </svg>
            <p className="chart-caption">
              Each line is a possible future. Which one will be yours?
            </p>
          </div>
        </div>
      </section>

      {/* Problem */}
      <section className="problem" id="why">
        <h2>Averages hide the risk.</h2>
        <p>
          Most retirement calculators show one number: your "expected" outcome.
          But markets don't move in averages—they crash, they boom, they surprise.
          A single projection hides the range of outcomes that could make or break
          your retirement.
        </p>
        <div className="problem-stats">
          <div className="stat">
            <span className="stat-value">2x</span>
            <span className="stat-label">
              difference between good and bad market sequences with identical average returns
            </span>
          </div>
          <div className="stat">
            <span className="stat-value">$400K+</span>
            <span className="stat-label">
              gap between 25th and 75th percentile outcomes on a $1M portfolio
            </span>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="features" id="features">
        <h2>What makes EggNest different</h2>
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
            <h3>Couples Planning</h3>
            <p>
              Retiring with a partner? Model both of you—different ages, incomes,
              and Social Security benefits.
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
        <h2>See your odds. Make better decisions.</h2>
        <p>Free to use. No account required. Results in 30 seconds.</p>
        <a href={APP_URL} className="btn-primary btn-large">
          Run Your Simulation
        </a>
      </section>

      {/* Footer */}
      <footer className="footer">
        <div className="footer-content">
          <div className="footer-brand">
            <div className="logo">EggNest</div>
            <p>Monte Carlo financial planning with real tax calculations.</p>
          </div>
          <div className="footer-links">
            <div className="footer-col">
              <h4>Product</h4>
              <a href={APP_URL}>Simulator</a>
              <a href="#features">Features</a>
              <a href="#how-it-works">How It Works</a>
            </div>
            <div className="footer-col">
              <h4>Company</h4>
              <a href="mailto:hello@eggnest.co">Contact</a>
            </div>
          </div>
        </div>
        <div className="footer-bottom">
          <p>
            © {new Date().getFullYear()} EggNest. Tax calculations powered by{" "}
            <a href="https://policyengine.org" target="_blank" rel="noopener">
              PolicyEngine
            </a>
          </p>
          <p className="disclaimer">
            EggNest provides educational projections only and is not financial
            advice. Consult a qualified financial advisor for personalized
            recommendations.
          </p>
        </div>
      </footer>
    </div>
  );
}
