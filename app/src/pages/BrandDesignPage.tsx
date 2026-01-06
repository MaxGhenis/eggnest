import "../styles/Brand.css";

// In production, this is eggnest.co
const HOME_URL = import.meta.env.PROD
  ? "https://eggnest.co"
  : "http://localhost:5173";

interface ColorSwatch {
  name: string;
  value: string;
  cssVar: string;
}

interface ColorGroup {
  title: string;
  colors: ColorSwatch[];
}

const COLOR_GROUPS: ColorGroup[] = [
  {
    title: "Primary - Golden Hour Amber",
    colors: [
      { name: "Primary", value: "#c2410c", cssVar: "--color-primary" },
      { name: "Primary light", value: "#ea580c", cssVar: "--color-primary-light" },
      { name: "Primary dark", value: "#9a3412", cssVar: "--color-primary-dark" },
      { name: "Primary 50", value: "#fff7ed", cssVar: "--color-primary-50" },
      { name: "Primary 100", value: "#ffedd5", cssVar: "--color-primary-100" },
      { name: "Primary 200", value: "#fed7aa", cssVar: "--color-primary-200" },
    ],
  },
  {
    title: "Secondary - Warm Gold",
    colors: [
      { name: "Gold", value: "#d97706", cssVar: "--color-gold" },
      { name: "Gold light", value: "#fbbf24", cssVar: "--color-gold-light" },
      { name: "Gold pale", value: "#fef3c7", cssVar: "--color-gold-pale" },
    ],
  },
  {
    title: "Accent - Sage",
    colors: [
      { name: "Sage", value: "#65a30d", cssVar: "--color-sage" },
      { name: "Sage light", value: "#84cc16", cssVar: "--color-sage-light" },
      { name: "Sage pale", value: "#ecfccb", cssVar: "--color-sage-pale" },
    ],
  },
  {
    title: "Semantic",
    colors: [
      { name: "Success", value: "#16a34a", cssVar: "--color-success" },
      { name: "Success light", value: "#dcfce7", cssVar: "--color-success-light" },
      { name: "Warning", value: "#ca8a04", cssVar: "--color-warning" },
      { name: "Warning light", value: "#fef9c3", cssVar: "--color-warning-light" },
      { name: "Danger", value: "#dc2626", cssVar: "--color-danger" },
      { name: "Danger light", value: "#fee2e2", cssVar: "--color-danger-light" },
    ],
  },
  {
    title: "Neutrals - Warm Tinted",
    colors: [
      { name: "Gray 50", value: "#fafaf9", cssVar: "--color-gray-50" },
      { name: "Gray 100", value: "#f5f5f4", cssVar: "--color-gray-100" },
      { name: "Gray 200", value: "#e7e5e4", cssVar: "--color-gray-200" },
      { name: "Gray 300", value: "#d6d3d1", cssVar: "--color-gray-300" },
      { name: "Gray 400", value: "#a8a29e", cssVar: "--color-gray-400" },
      { name: "Gray 500", value: "#78716c", cssVar: "--color-gray-500" },
      { name: "Gray 600", value: "#57534e", cssVar: "--color-gray-600" },
      { name: "Gray 700", value: "#44403c", cssVar: "--color-gray-700" },
      { name: "Gray 800", value: "#292524", cssVar: "--color-gray-800" },
      { name: "Gray 900", value: "#1c1917", cssVar: "--color-gray-900" },
    ],
  },
  {
    title: "Backgrounds",
    colors: [
      { name: "Background", value: "#fffbf5", cssVar: "--color-bg" },
      { name: "Background alt", value: "#fef7ed", cssVar: "--color-bg-alt" },
      { name: "Card", value: "#ffffff", cssVar: "--color-bg-card" },
    ],
  },
];

interface SpacingItem {
  name: string;
  value: string;
  pixels: number;
}

const SPACING_SCALE: SpacingItem[] = [
  { name: "--space-1", value: "0.25rem", pixels: 4 },
  { name: "--space-2", value: "0.5rem", pixels: 8 },
  { name: "--space-3", value: "0.75rem", pixels: 12 },
  { name: "--space-4", value: "1rem", pixels: 16 },
  { name: "--space-5", value: "1.25rem", pixels: 20 },
  { name: "--space-6", value: "1.5rem", pixels: 24 },
  { name: "--space-8", value: "2rem", pixels: 32 },
  { name: "--space-10", value: "2.5rem", pixels: 40 },
  { name: "--space-12", value: "3rem", pixels: 48 },
];

interface RadiusItem {
  name: string;
  value: string;
}

const RADIUS_SCALE: RadiusItem[] = [
  { name: "sm", value: "8px" },
  { name: "md", value: "12px" },
  { name: "lg", value: "20px" },
  { name: "xl", value: "28px" },
  { name: "full", value: "9999px" },
];

export function BrandDesignPage() {
  return (
    <div className="brand-page design-page">
      <header className="brand-header">
        <a href={HOME_URL} className="brand-logo">
          <img src="/logo.svg" alt="EggNest" height="28" />
        </a>
        <a href="#/brand" className="brand-back-link">
          ← Brand
        </a>
        <span className="brand-title">Design system</span>
        <a href="#/" className="brand-nav-link">Simulator</a>
      </header>

      <main className="brand-content">
        <div className="brand-hero">
          <div className="brand-hero-icon">🎨</div>
          <h1>Design system</h1>
          <p className="brand-hero-subtitle">
            The visual language of EggNest - warm, trustworthy, and approachable
          </p>
        </div>

        {/* Colors */}
        <section className="design-section">
          <h2>Colors</h2>
          <p>
            Our palette is built around warm amber tones that evoke the comfort of a golden hour.
            These colors create an inviting atmosphere for discussing financial planning.
          </p>

          {COLOR_GROUPS.map((group) => (
            <div key={group.title} className="color-group">
              <h3 className="color-group-title">{group.title}</h3>
              <div className="color-swatches">
                {group.colors.map((color) => (
                  <div key={color.cssVar} className="color-swatch">
                    <div
                      className="color-swatch-preview"
                      style={{ backgroundColor: color.value }}
                    />
                    <div className="color-swatch-info">
                      <span className="color-swatch-name">{color.name}</span>
                      <span className="color-swatch-value">{color.value}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </section>

        {/* Typography */}
        <section className="design-section">
          <h2>Typography</h2>
          <p>
            Fraunces brings warmth and personality to headings, while DM Sans provides
            excellent readability for body text and interface elements.
          </p>

          <div className="type-samples">
            <div className="type-sample">
              <div className="type-sample-meta">
                <span>Fraunces</span>
                <span>Display / Headings</span>
                <span>Weight: 500</span>
              </div>
              <div className="type-sample-preview display">
                <h1>Plan your retirement with confidence</h1>
              </div>
            </div>

            <div className="type-sample">
              <div className="type-sample-meta">
                <span>Fraunces</span>
                <span>Section heading</span>
                <span>Weight: 500</span>
              </div>
              <div className="type-sample-preview display">
                <h2>Monte Carlo simulation results</h2>
              </div>
            </div>

            <div className="type-sample">
              <div className="type-sample-meta">
                <span>Fraunces</span>
                <span>Subsection heading</span>
                <span>Weight: 500</span>
              </div>
              <div className="type-sample-preview display">
                <h3>Portfolio allocation</h3>
              </div>
            </div>

            <div className="type-sample">
              <div className="type-sample-meta">
                <span>DM Sans</span>
                <span>Body text</span>
                <span>Weight: 400</span>
              </div>
              <div className="type-sample-preview body">
                <p>
                  Based on 10,000 simulations of your financial plan, you have a 92% probability
                  of maintaining your desired lifestyle through age 95. The median portfolio value
                  at age 85 is $1.2M.
                </p>
              </div>
            </div>

            <div className="type-sample">
              <div className="type-sample-meta">
                <span>DM Sans</span>
                <span>Small / Caption</span>
                <span>Weight: 400</span>
              </div>
              <div className="type-sample-preview body small-text">
                <p>
                  Results based on historical market data. Past performance does not guarantee future results.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Spacing */}
        <section className="design-section">
          <h2>Spacing</h2>
          <p>
            A consistent spacing scale creates visual rhythm and hierarchy.
            Based on a 4px base unit for precise alignment.
          </p>

          <div className="spacing-scale">
            {SPACING_SCALE.map((space) => (
              <div key={space.name} className="spacing-item">
                <span className="spacing-label">{space.name}</span>
                <div
                  className="spacing-bar"
                  style={{ width: `${space.pixels * 3}px` }}
                />
                <span className="spacing-value">{space.pixels}px</span>
              </div>
            ))}
          </div>
        </section>

        {/* Border Radius */}
        <section className="design-section">
          <h2>Border radius</h2>
          <p>
            Rounded corners create a friendly, approachable feel. Use larger radii for
            prominent elements like cards, smaller for compact UI elements.
          </p>

          <div className="radius-samples">
            {RADIUS_SCALE.map((radius) => (
              <div key={radius.name} className="radius-sample">
                <div
                  className="radius-preview"
                  style={{
                    borderRadius: radius.name === "full" ? "50%" : radius.value,
                  }}
                />
                <span>{radius.name}: {radius.value}</span>
              </div>
            ))}
          </div>
        </section>

        {/* Shadows */}
        <section className="design-section">
          <h2>Shadows</h2>
          <p>
            Soft, warm shadows create depth without harshness. Use sparingly to
            indicate elevation and interactive states.
          </p>

          <div className="shadow-samples">
            <div className="shadow-sample">
              <div className="shadow-preview" style={{ boxShadow: "0 1px 2px rgba(28, 25, 23, 0.04)" }} />
              <span>shadow-sm</span>
            </div>
            <div className="shadow-sample">
              <div className="shadow-preview" style={{ boxShadow: "0 4px 12px rgba(28, 25, 23, 0.06), 0 1px 3px rgba(28, 25, 23, 0.04)" }} />
              <span>shadow-md</span>
            </div>
            <div className="shadow-sample">
              <div className="shadow-preview" style={{ boxShadow: "0 12px 32px rgba(28, 25, 23, 0.08), 0 4px 12px rgba(28, 25, 23, 0.04)" }} />
              <span>shadow-lg</span>
            </div>
            <div className="shadow-sample">
              <div className="shadow-preview" style={{ boxShadow: "0 0 40px rgba(234, 88, 12, 0.12)" }} />
              <span>shadow-glow</span>
            </div>
          </div>
        </section>

        {/* Gradients */}
        <section className="design-section">
          <h2>Gradients</h2>
          <p>
            Subtle gradients add warmth and dimension. Use for backgrounds and
            decorative accents, not for text or critical UI elements.
          </p>

          <div className="shadow-samples">
            <div className="shadow-sample">
              <div
                className="shadow-preview"
                style={{ background: "linear-gradient(135deg, #fef3c7 0%, #fed7aa 50%, #fdba74 100%)" }}
              />
              <span>gradient-sunrise</span>
            </div>
            <div className="shadow-sample">
              <div
                className="shadow-preview"
                style={{ background: "linear-gradient(135deg, #d97706 0%, #ea580c 100%)" }}
              />
              <span>gradient-golden</span>
            </div>
            <div className="shadow-sample">
              <div
                className="shadow-preview"
                style={{ background: "linear-gradient(180deg, #fffbf5 0%, #fef7ed 100%)" }}
              />
              <span>gradient-warm</span>
            </div>
            <div className="shadow-sample">
              <div
                className="shadow-preview"
                style={{ background: "linear-gradient(180deg, #ffffff 0%, #fefcf9 100%)" }}
              />
              <span>gradient-card</span>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
