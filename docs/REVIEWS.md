# Editorial Summary: EggNest Methodology Paper (Round 2)

## Decision: Minor Revisions (Conditional Accept)

The paper makes a genuine contribution to the retirement planning literature by demonstrating integration of Monte Carlo simulation with real tax microsimulation via PolicyEngine. All four reviewers recommend Minor Revisions.

---

## Reviewer Recommendations

| Reviewer | Recommendation | Key Concerns |
|----------|----------------|--------------|
| 🔬 Methodology | Minor Revisions | Bootstrap/serial correlation claim, sample size mismatch, confidence intervals |
| 👤 Practitioner | Minor Revisions | Needs practical guidance, inflation handling, runtime benchmarks |
| 💼 CFP | Maybe (Would Use) | Missing Roth conversions, IRMAA, spousal modeling |
| 🔄 Reproducibility | Minor Revisions | Sample size 1000 vs 10000, CI/CD, data archival |

---

## Critical Issues (Must Address)

### 1. Bootstrap/Serial Correlation Mismatch
**Severity: High** | **Reviewer: Methodology**

Paper claims bootstrap "preserves serial correlation patterns" but the default method samples independently.

**Fix**: Correct the claim or switch to block_bootstrap as the default method.

### 2. Sample Size Discrepancy
**Severity: High** | **Reviewers: Reproducibility, Methodology**

Paper claims 10,000 simulations but `eggnest_results.py` uses 1,000 simulations.

**Fix**: Align claims with actual implementation or increase simulation count.

### 3. Missing Confidence Intervals
**Severity: Medium-High** | **Reviewers: Methodology, Practitioner**

Success rates reported as point estimates (82%, 78%) without uncertainty quantification.

**Fix**: Add 95% confidence intervals (+/- ~0.8pp for n=10,000).

---

## Changes Made This Round

- ✅ Fixed log-normal vs bootstrap description (now correctly describes bootstrap sampling)
- ✅ Documented inflation treatment limitation prominently in Limitations section
- ✅ Fixed TCJA abbreviation (now "Tax Cuts and Jobs Act (TCJA)")
- ✅ Fixed LTCG abbreviation (now "long-term capital gains rate")
- ✅ Added fixed random seed (PAPER_SEED = 42) for reproducible results
- ✅ Access RMD divisor directly from UNIFORM_LIFETIME_TABLE

---

## Remaining Issues

### High Priority
- [x] Fix bootstrap/serial correlation claim (now notes independent sampling doesn't preserve it)
- [x] Increase n_simulations to 10,000 (was 1,000)
- [x] Add confidence intervals to success rate estimates (95% CI using normal approximation)
- [x] Add practical interpretation guidance (new "Practical Interpretation" section)

### Medium Priority
- [ ] Add runtime benchmarks
- [ ] Include sensitivity analysis for inflation
- [ ] Explain TCJA sunset handling explicitly
- [ ] Add CI/CD with test badge

### Future Work (Acknowledged by CFP Reviewer)
- [ ] Roth conversion optimization (critical for real client work)
- [ ] IRMAA threshold modeling
- [ ] Married couple support
- [ ] Social Security claiming optimization

---

## Noted Strengths (All Reviewers)

1. **Novel PolicyEngine Integration**: First open-source retirement simulator with real tax microsimulation
2. **Correct RMD Enforcement**: Properly implements IRS Uniform Lifetime Table
3. **Calendar-Year Bracket Inflation**: Sophisticated feature most tools lack
4. **Account Type Distinction**: Correct tax treatment across traditional/Roth/taxable
5. **Open Source & Transparent**: Auditable methodology, MIT license
6. **Strong Test Coverage**: 80+ tests covering core simulation logic

---

## Target Venue Fit

| Venue | Fit | Notes |
|-------|-----|-------|
| **Journal of Financial Planning** | Good | Applied focus matches; needs practitioner guidance section |
| Journal of Retirement | Good | Domain-specific audience |
| Financial Analysts Journal | Possible | More technical rigor needed |
| SSRN/Working Paper | Ready | Current state appropriate |

---

## Summary

This paper demonstrates that accurate tax modeling materially affects retirement planning outcomes. The integration with PolicyEngine is the key innovation—one of the first tools to combine Monte Carlo simulation with real microsimulation.

With targeted revisions addressing the bootstrap claim, sample size, and confidence intervals, this would be a strong submission to **Journal of Financial Planning** or similar applied finance venues.

The CFP reviewer's perspective was particularly valuable: the tool is innovative but needs Roth conversion optimization, IRMAA awareness, and married couple support before professional financial planners would adopt it fully.

---

*This review was synthesized from 4 independent referee reports. Full reviews posted to [PR #3](https://github.com/MaxGhenis/eggnest/pull/3).*
