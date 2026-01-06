import "../styles/Brand.css";

// In production, this is eggnest.co
const HOME_URL = import.meta.env.PROD
  ? "https://eggnest.co"
  : "http://localhost:5173";

interface TerminologyItem {
  term: string;
  definition: string;
  usage: string;
}

const TERMINOLOGY: TerminologyItem[] = [
  {
    term: "Monte Carlo simulation",
    definition: "A computational technique that runs thousands of scenarios using random sampling",
    usage: "We run 10,000 Monte Carlo simulations to estimate your success probability.",
  },
  {
    term: "Success probability",
    definition: "The percentage of simulations where your portfolio lasts through your target age",
    usage: "Your plan has a 94% success probability through age 95.",
  },
  {
    term: "Safe withdrawal rate",
    definition: "The percentage of your portfolio you can withdraw annually with minimal risk of depletion",
    usage: "Based on your allocation, a 3.8% withdrawal rate is sustainable.",
  },
  {
    term: "Sequence of returns risk",
    definition: "The risk that poor market returns early in retirement will deplete your portfolio faster",
    usage: "Consider holding 2 years of expenses in cash to mitigate sequence of returns risk.",
  },
  {
    term: "Tax-efficient withdrawal",
    definition: "Strategically drawing from accounts to minimize lifetime taxes",
    usage: "Withdraw from taxable accounts first to let tax-advantaged accounts grow.",
  },
  {
    term: "Required minimum distribution (RMD)",
    definition: "Mandatory annual withdrawals from traditional retirement accounts starting at age 73",
    usage: "Your RMDs begin at age 73 and are factored into income projections.",
  },
];

export function BrandWritingPage() {
  return (
    <div className="brand-page writing-page">
      <header className="brand-header">
        <a href={HOME_URL} className="brand-logo">
          <img src="/logo.svg" alt="EggNest" height="28" />
        </a>
        <a href="#/brand" className="brand-back-link">
          ← Brand
        </a>
        <span className="brand-title">Writing guide</span>
        <a href="#/" className="brand-nav-link">Simulator</a>
      </header>

      <main className="brand-content">
        <div className="brand-hero">
          <div className="brand-hero-icon">✍️</div>
          <h1>Writing guide</h1>
          <p className="brand-hero-subtitle">
            How we communicate financial concepts with clarity and warmth
          </p>
        </div>

        {/* Voice and Tone */}
        <section className="writing-section">
          <h2>Voice and tone</h2>
          <p>
            EggNest speaks like a knowledgeable friend who happens to be a financial planner.
            We are warm but not casual, precise but not clinical, helpful but not prescriptive.
          </p>

          <ul className="writing-guidelines">
            <li>Be direct and confident without being condescending</li>
            <li>Acknowledge uncertainty where it exists (markets are unpredictable)</li>
            <li>Empower users to make their own decisions with good information</li>
            <li>Avoid jargon when simpler language works, but use precise terms when needed</li>
            <li>Present numbers neutrally - let users interpret whether outcomes are good or bad</li>
          </ul>
        </section>

        {/* Sentence Case */}
        <section className="writing-section">
          <h2>Sentence case for headings</h2>
          <p>
            Always use sentence case for all headings, titles, and button labels.
            This follows the modern standard used by Apple, Google, and most tech companies.
            It feels more natural and conversational.
          </p>

          <div className="writing-example">
            <div className="writing-example-header">
              <div className="writing-example-column">
                <span className="example-label do">✓ Do</span>
                <p className="example-text">Plan your retirement with confidence</p>
              </div>
              <div className="writing-example-column">
                <span className="example-label dont">✗ Don't</span>
                <p className="example-text">Plan Your Retirement With Confidence</p>
              </div>
            </div>
          </div>

          <div className="writing-example">
            <div className="writing-example-header">
              <div className="writing-example-column">
                <span className="example-label do">✓ Do</span>
                <p className="example-text">Monte Carlo simulation results</p>
              </div>
              <div className="writing-example-column">
                <span className="example-label dont">✗ Don't</span>
                <p className="example-text">Monte Carlo Simulation Results</p>
              </div>
            </div>
          </div>

          <p>
            <strong>Exception:</strong> Proper nouns and acronyms remain capitalized:
            "Social Security benefits", "Roth IRA", "Medicare enrollment"
          </p>
        </section>

        {/* Active Voice */}
        <section className="writing-section">
          <h2>Active voice</h2>
          <p>
            Use active voice to make writing clearer and more direct.
            The subject should perform the action, not receive it.
          </p>

          <div className="writing-example">
            <div className="writing-example-header">
              <div className="writing-example-column">
                <span className="example-label do">✓ Do</span>
                <p className="example-text">Your portfolio grows to $1.2M by age 75</p>
              </div>
              <div className="writing-example-column">
                <span className="example-label dont">✗ Don't</span>
                <p className="example-text">$1.2M is reached by your portfolio at age 75</p>
              </div>
            </div>
          </div>

          <div className="writing-example">
            <div className="writing-example-header">
              <div className="writing-example-column">
                <span className="example-label do">✓ Do</span>
                <p className="example-text">You can withdraw $48,000 annually</p>
              </div>
              <div className="writing-example-column">
                <span className="example-label dont">✗ Don't</span>
                <p className="example-text">$48,000 can be withdrawn annually</p>
              </div>
            </div>
          </div>
        </section>

        {/* Number Presentation */}
        <section className="writing-section">
          <h2>Dispassionate number presentation</h2>
          <p>
            Present financial figures neutrally. Let users interpret whether outcomes meet their goals.
            Avoid editorializing with words like "only", "just", or "impressive".
          </p>

          <div className="writing-example">
            <div className="writing-example-header">
              <div className="writing-example-column">
                <span className="example-label do">✓ Do</span>
                <p className="example-text">Your success probability is 78%</p>
              </div>
              <div className="writing-example-column">
                <span className="example-label dont">✗ Don't</span>
                <p className="example-text">Your success probability is only 78%</p>
              </div>
            </div>
          </div>

          <div className="writing-example">
            <div className="writing-example-header">
              <div className="writing-example-column">
                <span className="example-label do">✓ Do</span>
                <p className="example-text">Median portfolio at age 85: $450,000</p>
              </div>
              <div className="writing-example-column">
                <span className="example-label dont">✗ Don't</span>
                <p className="example-text">You'll have an impressive $450,000 left!</p>
              </div>
            </div>
          </div>

          <ul className="writing-guidelines">
            <li>Use dollar signs for currency: $500,000 not 500000 dollars</li>
            <li>Use commas for thousands: $1,250,000</li>
            <li>Abbreviate large numbers in charts: $1.2M, $500K</li>
            <li>Show percentages with one decimal: 94.5%, not 94.5432%</li>
            <li>Round appropriately - $847,293 becomes "approximately $850,000"</li>
          </ul>
        </section>

        {/* Uncertainty */}
        <section className="writing-section">
          <h2>Expressing uncertainty</h2>
          <p>
            Financial projections are inherently uncertain. Acknowledge this honestly
            while still providing useful information.
          </p>

          <div className="writing-example">
            <div className="writing-example-header">
              <div className="writing-example-column">
                <span className="example-label do">✓ Do</span>
                <p className="example-text">In 90% of simulations, your portfolio lasts through age 92</p>
              </div>
              <div className="writing-example-column">
                <span className="example-label dont">✗ Don't</span>
                <p className="example-text">Your money will definitely last until age 92</p>
              </div>
            </div>
          </div>

          <div className="writing-example">
            <div className="writing-example-header">
              <div className="writing-example-column">
                <span className="example-label do">✓ Do</span>
                <p className="example-text">Based on historical returns, you could withdraw...</p>
              </div>
              <div className="writing-example-column">
                <span className="example-label dont">✗ Don't</span>
                <p className="example-text">You should withdraw exactly...</p>
              </div>
            </div>
          </div>

          <ul className="writing-guidelines">
            <li>Use probability language: "In X% of scenarios..."</li>
            <li>Reference the methodology: "Based on 10,000 simulations..."</li>
            <li>Acknowledge limitations: "Past performance does not guarantee future results"</li>
            <li>Suggest consulting professionals for personalized advice</li>
          </ul>
        </section>

        {/* Terminology */}
        <section className="writing-section">
          <h2>Financial terminology</h2>
          <p>
            Use precise financial terms when they add clarity, but always provide context
            for technical concepts. Here are key terms and how to use them:
          </p>

          <table className="terminology-table">
            <thead>
              <tr>
                <th>Term</th>
                <th>Definition</th>
                <th>Example usage</th>
              </tr>
            </thead>
            <tbody>
              {TERMINOLOGY.map((item) => (
                <tr key={item.term}>
                  <td>{item.term}</td>
                  <td>{item.definition}</td>
                  <td>{item.usage}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {/* Error Messages */}
        <section className="writing-section">
          <h2>Error messages</h2>
          <p>
            When something goes wrong, be helpful and specific. Tell users what happened
            and what they can do about it.
          </p>

          <div className="writing-example">
            <div className="writing-example-header">
              <div className="writing-example-column">
                <span className="example-label do">✓ Do</span>
                <p className="example-text">Simulation timed out. Try reducing the number of scenarios or check your connection.</p>
              </div>
              <div className="writing-example-column">
                <span className="example-label dont">✗ Don't</span>
                <p className="example-text">Error: Request failed</p>
              </div>
            </div>
          </div>

          <div className="writing-example">
            <div className="writing-example-header">
              <div className="writing-example-column">
                <span className="example-label do">✓ Do</span>
                <p className="example-text">Age must be between 18 and 100</p>
              </div>
              <div className="writing-example-column">
                <span className="example-label dont">✗ Don't</span>
                <p className="example-text">Invalid input</p>
              </div>
            </div>
          </div>
        </section>

        {/* Disclaimers */}
        <section className="writing-section">
          <h2>Disclaimers</h2>
          <p>
            Include appropriate disclaimers for financial content, but keep them concise
            and readable. Place them near relevant content, not hidden at the bottom.
          </p>

          <ul className="writing-guidelines">
            <li>Keep disclaimers short and in plain language</li>
            <li>Place near the content they relate to</li>
            <li>Use a slightly smaller font size and muted color</li>
            <li>Don't bury important limitations in legal jargon</li>
          </ul>

          <div className="writing-example">
            <div className="writing-example-header">
              <div className="writing-example-column">
                <span className="example-label do">✓ Do</span>
                <p className="example-text" style={{ fontSize: "0.875rem", color: "#78716c" }}>
                  Results are estimates based on historical data. Consult a financial advisor for personalized guidance.
                </p>
              </div>
              <div className="writing-example-column">
                <span className="example-label dont">✗ Don't</span>
                <p className="example-text" style={{ fontSize: "0.75rem", color: "#a8a29e" }}>
                  THE INFORMATION PROVIDED HEREIN IS FOR EDUCATIONAL PURPOSES ONLY AND DOES NOT CONSTITUTE FINANCIAL ADVICE...
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
