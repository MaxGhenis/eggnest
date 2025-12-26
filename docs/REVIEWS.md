# Editorial Summary: EggNest Methodology Paper

## Decision: Minor Revisions (Conditional Accept)

The paper makes a genuine contribution to the retirement planning literature by demonstrating integration of Monte Carlo simulation with real tax microsimulation via PolicyEngine. Four of five reviewers recommend Minor Revisions; one recommends Major Revisions citing missing features for professional use. The consensus is that targeted revisions can address the main concerns.

---

## Reviewer Recommendations

| Reviewer | Recommendation | Key Concerns |
|----------|----------------|--------------|
| 🔬 Methodology | Minor Revisions | Log-normal vs bootstrap discrepancy, inflation treatment, validation evidence |
| 🏛️ Domain Expert | Major Revisions | Missing Roth conversions, IRMAA, dynamic strategies, TCJA sunset |
| 👤 Practitioner | Minor Revisions | Needs practical guidance, inflation-adjusted spending, confidence intervals |
| 🔄 Reproducibility | Minor Revisions | Placeholder values in results, no fixed random seed |
| ✍️ Academic Style | Minor Revisions | Template variables unresolved, structural inconsistencies |

---

## Critical Issues (Must Address)

### 1. Paper Results Use Placeholder Values
**Severity: High** | **Reviewers: Reproducibility, Methodology**

The `eggnest_results.py` falls back to hardcoded placeholder values when simulation modules can't be imported. The paper may not reflect actual simulation outputs.

**Fix**: Run actual simulations with fixed seed (e.g., `seed=42`) and verify all numerical claims.

### 2. Log-Normal vs Bootstrap Discrepancy
**Severity: High** | **Reviewers: Methodology**

Paper claims "returns modeled as log-normal" but implementation uses historical bootstrap sampling.

**Fix**: Correct the paper to accurately describe the bootstrap methodology, or explain which method is used under what conditions.

### 3. Inflation Treatment Inconsistency
**Severity: High** | **Reviewers: Methodology, Domain Expert, Practitioner**

Returns are nominal, spending is fixed nominal, but bracket inflation is modeled. Over 30+ years, fixed nominal spending significantly understates real spending needs.

**Fix**: Either (a) model real returns with inflation-adjusted spending, or (b) clearly document this limitation and its impact on results.

### 4. Template Variables Unresolved
**Severity: High** | **Reviewers: Academic Style**

Multiple `{eval}` placeholders throughout the paper need to be resolved before submission (e.g., `{eval}r.reference.description`).

**Fix**: Build the MyST document and verify all computed values render correctly.

---

## Common Themes Across Reviews

### Missing Features (Domain Expert, Practitioner)
- No Roth conversion optimization
- No IRMAA (Medicare premium surcharges) modeling
- No dynamic withdrawal strategies (Guyton-Klinger, variable percentage)
- No Social Security claiming optimization
- Limited spouse/joint filing sophistication

**Recommendation**: Acknowledge these as limitations; prioritize Roth conversions for future work.

### Validation Evidence Needed (Methodology, Reproducibility)
- No unit tests demonstrating edge case handling
- Tax calculation validation against IRS/TurboTax mentioned but not shown
- PolicyEngine integration accuracy not independently verified

**Recommendation**: Add validation section with specific test cases and expected vs. actual results.

### Practical Guidance Missing (Practitioner, Domain Expert)
- No "how to use in client meetings" guidance
- No sensitivity analysis for key parameters
- No discussion of computational cost/runtime

**Recommendation**: Add a "Practical Implications" section for practitioner audience.

---

## Noted Strengths

All reviewers acknowledged:

1. **Novel PolicyEngine Integration**: First open-source retirement simulator with real tax microsimulation
2. **Account Type Distinction**: Correct tax treatment across traditional/Roth/taxable accounts
3. **RMD Enforcement**: Properly implements IRS Uniform Lifetime Table
4. **Calendar-Year Bracket Inflation**: Sophisticated feature most tools lack
5. **Open Source & Transparent**: Reproducible methodology, auditable code
6. **Strong Test Coverage**: 33+ tests covering core simulation logic
7. **Clear Writing**: Well-organized, appropriate for applied finance audience

---

## Specific Revision Checklist

### High Priority (Before Resubmission)
- [ ] Resolve all `{eval}` template variables
- [ ] Run actual simulations with fixed random seed
- [ ] Correct log-normal vs bootstrap description
- [ ] Document inflation treatment limitation prominently
- [ ] Introduce TCJA abbreviation before first use
- [ ] Add LTCG abbreviation introduction

### Medium Priority (Strengthen Paper)
- [ ] Add validation section with specific test cases
- [ ] Include runtime/computational cost information
- [ ] Reorganize Results section by finding rather than strategy
- [ ] Address fund type discussion (currently orphaned)
- [ ] Add sensitivity analysis table

### Lower Priority (Nice-to-Have)
- [ ] Add Roth conversion discussion to Future Work
- [ ] Include confidence intervals on success rates
- [ ] Add FAQ for common practitioner questions
- [ ] Provide worked example with manual verification

---

## Questions Requiring Author Response

1. **Return Distribution**: Which accurately describes the methodology—log-normal or bootstrap?

2. **Validation**: Can you provide specific test cases comparing EggNest vs. IRS/TurboTax calculations?

3. **Placeholder Values**: Are the paper's numerical results (82% taxable-first, etc.) from actual simulations or placeholders?

4. **TCJA Sunset**: Does PolicyEngine model the 2026 tax law changes? If not, how should users interpret post-2025 projections?

5. **Cost Basis**: What assumption is used for taxable account cost basis? Is all growth treated as LTCG?

6. **Convergence**: Have you formally verified 10,000 simulations achieve the claimed ~0.5% standard error?

---

## Target Venue Fit

| Venue | Fit | Notes |
|-------|-----|-------|
| Journal of Financial Planning | Good | Applied focus matches; needs practitioner guidance |
| Financial Analysts Journal | Possible | More technical rigor needed |
| Journal of Retirement | Good | Domain-specific audience |
| SSRN/Working Paper | Ready | Current state appropriate |

---

## Summary

This paper makes a valuable contribution by demonstrating that real tax microsimulation materially affects retirement planning outcomes. The 4 percentage point difference in success rates (82% vs 78%) between strategies is meaningful and properly contextualized.

With targeted revisions addressing:
1. Placeholder values → actual simulation results
2. Log-normal/bootstrap discrepancy
3. Inflation treatment documentation
4. Template variable resolution

...this would be a strong submission to Journal of Financial Planning or similar applied finance venues.

The integration with PolicyEngine is the key innovation—it's one of the first tools to combine Monte Carlo simulation with real microsimulation, and the paper effectively demonstrates why this matters for retirement planning decisions.

---

*This review was synthesized from 5 independent referee reports. Address feedback and re-run reviews for another round.*
