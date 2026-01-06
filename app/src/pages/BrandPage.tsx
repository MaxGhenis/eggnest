import "../styles/Brand.css";

// In production, this is eggnest.co
const HOME_URL = import.meta.env.PROD
  ? "https://eggnest.co"
  : "http://localhost:5173";

interface BrandCard {
  id: string;
  title: string;
  description: string;
  icon: string;
  href: string;
}

const BRAND_SECTIONS: BrandCard[] = [
  {
    id: "design",
    title: "Design system",
    description: "Colors, typography, spacing, and visual guidelines for the Golden Hour aesthetic",
    icon: "🎨",
    href: "#/brand/design",
  },
  {
    id: "writing",
    title: "Writing guide",
    description: "Voice, tone, and style guidelines for financial content",
    icon: "✍️",
    href: "#/brand/writing",
  },
];

export function BrandPage() {
  return (
    <div className="brand-page">
      <header className="brand-header">
        <a href={HOME_URL} className="brand-logo">
          <img src="/logo.svg" alt="EggNest" height="28" />
        </a>
        <span className="brand-title">Brand guidelines</span>
        <a href="#/" className="brand-nav-link">Simulator</a>
      </header>

      <main className="brand-content">
        <div className="brand-hero">
          <div className="brand-hero-icon">🥚</div>
          <h1>EggNest brand</h1>
          <p className="brand-hero-subtitle">
            Guidelines for creating a consistent, warm experience across all EggNest products
          </p>
        </div>

        <div className="brand-grid">
          {BRAND_SECTIONS.map((section) => (
            <a key={section.id} href={section.href} className="brand-card">
              <span className="brand-card-icon">{section.icon}</span>
              <h2 className="brand-card-title">{section.title}</h2>
              <p className="brand-card-description">{section.description}</p>
              <span className="brand-card-arrow">→</span>
            </a>
          ))}
        </div>

        <section className="brand-overview">
          <h2>Brand essence</h2>
          <div className="brand-values">
            <div className="brand-value">
              <h3>Warm and approachable</h3>
              <p>
                Financial planning can feel cold and intimidating. EggNest uses warm amber tones
                and friendly language to make retirement planning feel welcoming.
              </p>
            </div>
            <div className="brand-value">
              <h3>Trustworthy precision</h3>
              <p>
                Behind the warmth is rigorous Monte Carlo simulation and tax-aware modeling.
                We present numbers with appropriate confidence intervals.
              </p>
            </div>
            <div className="brand-value">
              <h3>Empowering clarity</h3>
              <p>
                Complex financial concepts are explained simply. Users leave feeling more
                confident about their financial future.
              </p>
            </div>
          </div>
        </section>

        <section className="brand-quick-ref">
          <h2>Quick reference</h2>
          <div className="quick-ref-grid">
            <div className="quick-ref-item">
              <span className="quick-ref-label">Primary color</span>
              <div className="quick-ref-color" style={{ backgroundColor: "#c2410c" }}></div>
              <span className="quick-ref-value">#c2410c</span>
            </div>
            <div className="quick-ref-item">
              <span className="quick-ref-label">Gold accent</span>
              <div className="quick-ref-color" style={{ backgroundColor: "#d97706" }}></div>
              <span className="quick-ref-value">#d97706</span>
            </div>
            <div className="quick-ref-item">
              <span className="quick-ref-label">Display font</span>
              <span className="quick-ref-value" style={{ fontFamily: "Fraunces, serif" }}>Fraunces</span>
            </div>
            <div className="quick-ref-item">
              <span className="quick-ref-label">Body font</span>
              <span className="quick-ref-value" style={{ fontFamily: "DM Sans, sans-serif" }}>DM Sans</span>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
