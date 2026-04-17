"""Tax calculations using PolicyEngine-US."""

import tempfile
from pathlib import Path

import numpy as np
from policyengine_core.data import Dataset
from policyengine_us import Microsimulation

from eggnest.constants import FILING_STATUS_PE_DATASET, STATE_FIPS

FILING_STATUS_IRMAA_PARAMETER: dict[str, str] = {
    "single": "single",
    "SINGLE": "single",
    "married_filing_jointly": "joint",
    "JOINT": "joint",
    "married_filing_separately": "separate",
    "SEPARATE": "separate",
    "head_of_household": "head_of_household",
    "HEAD_OF_HOUSEHOLD": "head_of_household",
    "surviving_spouse": "surviving_spouse",
    "SURVIVING_SPOUSE": "surviving_spouse",
    "widow": "surviving_spouse",
    "WIDOW": "surviving_spouse",
}


def _format_irmaa_bracket_label(
    thresholds: np.ndarray, tier_index: int
) -> str:
    """Render a compact MAGI band label for one IRMAA tier."""
    if tier_index <= 0:
        return "none"

    lower = int(thresholds[tier_index])
    upper = (
        int(thresholds[tier_index + 1]) - 1
        if tier_index + 1 < len(thresholds)
        else None
    )
    if upper is None:
        return f"${lower:,.0f}+ MAGI"
    return f"${lower:,.0f}-${upper:,.0f} MAGI"


class MonteCarloDataset(Dataset):
    """Custom dataset for Monte Carlo simulations."""

    name = "monte_carlo_dataset"
    label = "Monte Carlo simulation dataset"
    data_format = Dataset.TIME_PERIOD_ARRAYS

    def __init__(
        self,
        n_scenarios: int,
        capital_gains_array: np.ndarray,
        social_security_array: np.ndarray,
        ages: np.ndarray,
        state: str = "CA",
        year: int = 2025,
        filing_status: str = "SINGLE",
        dividend_income_array: np.ndarray | None = None,
        employment_income_array: np.ndarray | None = None,
        agi_two_years_prior_array: np.ndarray | None = None,
        tax_exempt_interest_two_years_prior_array: np.ndarray | None = None,
    ):
        self.n_scenarios = n_scenarios
        self.capital_gains = capital_gains_array
        self.social_security = social_security_array
        self.ages = ages
        self.state = state
        self.year = year
        self.filing_status = filing_status
        self.dividend_income = (
            dividend_income_array
            if dividend_income_array is not None
            else np.zeros(n_scenarios)
        )
        self.employment_income = (
            employment_income_array
            if employment_income_array is not None
            else np.zeros(n_scenarios)
        )
        self.agi_two_years_prior = (
            agi_two_years_prior_array
            if agi_two_years_prior_array is not None
            else np.zeros(n_scenarios)
        )
        self.tax_exempt_interest_two_years_prior = (
            tax_exempt_interest_two_years_prior_array
            if tax_exempt_interest_two_years_prior_array is not None
            else np.zeros(n_scenarios)
        )

        self.tmp_file = tempfile.NamedTemporaryFile(suffix=".h5", delete=False)
        self.file_path = Path(self.tmp_file.name)

        super().__init__()

    def generate(self) -> None:
        """Generate the dataset with all Monte Carlo scenarios."""
        person_ids = np.arange(self.n_scenarios)
        household_ids = np.arange(self.n_scenarios)
        tax_unit_ids = np.arange(self.n_scenarios)
        family_ids = np.arange(self.n_scenarios)
        spm_unit_ids = np.arange(self.n_scenarios)
        marital_unit_ids = np.arange(self.n_scenarios)

        weights = np.ones(self.n_scenarios)

        filing_status_values = np.full(
            self.n_scenarios, FILING_STATUS_PE_DATASET.get(self.filing_status, 1)
        )

        state_code = STATE_FIPS.get(self.state, 6)
        prior_year = self.year - 2
        ages_two_years_prior = np.maximum(self.ages - 2, 0)

        data = {
            "person_id": {prior_year: person_ids, self.year: person_ids},
            "person_household_id": {prior_year: household_ids, self.year: household_ids},
            "person_tax_unit_id": {prior_year: tax_unit_ids, self.year: tax_unit_ids},
            "person_family_id": {prior_year: family_ids, self.year: family_ids},
            "person_spm_unit_id": {prior_year: spm_unit_ids, self.year: spm_unit_ids},
            "person_marital_unit_id": {
                prior_year: marital_unit_ids,
                self.year: marital_unit_ids,
            },
            "person_weight": {prior_year: weights, self.year: weights},
            "age": {prior_year: ages_two_years_prior, self.year: self.ages},
            "long_term_capital_gains": {self.year: self.capital_gains},
            "social_security": {self.year: self.social_security},
            "social_security_retirement": {self.year: self.social_security},
            "employment_income": {self.year: self.employment_income},
            "interest_income": {self.year: np.zeros(self.n_scenarios)},
            "dividend_income": {self.year: self.dividend_income},
            "household_id": {prior_year: household_ids, self.year: household_ids},
            "household_weight": {prior_year: weights, self.year: weights},
            "household_state_fips": {
                prior_year: np.full(self.n_scenarios, state_code),
                self.year: np.full(self.n_scenarios, state_code),
            },
            "tax_unit_id": {prior_year: tax_unit_ids, self.year: tax_unit_ids},
            "tax_unit_weight": {prior_year: weights, self.year: weights},
            "filing_status": {
                prior_year: filing_status_values,
                self.year: filing_status_values,
            },
            "adjusted_gross_income": {prior_year: self.agi_two_years_prior},
            "tax_exempt_interest_income": {prior_year: self.tax_exempt_interest_two_years_prior},
            "family_id": {prior_year: family_ids, self.year: family_ids},
            "family_weight": {prior_year: weights, self.year: weights},
            "spm_unit_id": {prior_year: spm_unit_ids, self.year: spm_unit_ids},
            "spm_unit_weight": {prior_year: weights, self.year: weights},
            "marital_unit_id": {prior_year: marital_unit_ids, self.year: marital_unit_ids},
            "marital_unit_weight": {prior_year: weights, self.year: weights},
        }

        self.save_dataset(data)

    def cleanup(self) -> None:
        """Clean up temporary file."""
        if hasattr(self, "tmp_file"):
            try:
                self.file_path.unlink()
            except Exception:
                pass


class TaxCalculator:
    """Calculate taxes using PolicyEngine-US."""

    def __init__(self, state: str = "CA", year: int = 2025):
        self.state = state
        self.year = year

    def _medicare_irmaa_details(
        self,
        *,
        sim: Microsimulation,
        calc_year: int,
        filing_status: str,
        agi_two_years_prior_array: np.ndarray | None,
        tax_exempt_interest_two_years_prior_array: np.ndarray | None,
        medicare_part_b_premium: np.ndarray,
        medicare_part_d_premium_surcharge: np.ndarray,
    ) -> dict[str, np.ndarray]:
        """Return IRMAA detail arrays derived from PE parameters and MAGI."""
        n_scenarios = len(medicare_part_b_premium)
        status_key = FILING_STATUS_IRMAA_PARAMETER.get(filing_status, "single")
        params = sim.tax_benefit_system.parameters(calc_year).gov.hhs.medicare
        magi = np.asarray(
            agi_two_years_prior_array
            if agi_two_years_prior_array is not None
            else np.zeros(n_scenarios),
            dtype=float,
        ) + np.asarray(
            tax_exempt_interest_two_years_prior_array
            if tax_exempt_interest_two_years_prior_array is not None
            else np.zeros(n_scenarios),
            dtype=float,
        )

        part_b_scale = getattr(params.part_b.irmaa, status_key)
        part_b_thresholds = np.asarray(part_b_scale.thresholds, dtype=float)
        part_b_tiers = np.searchsorted(part_b_thresholds, magi, side="right") - 1
        part_b_tiers = np.clip(part_b_tiers, 0, len(part_b_scale.amounts) - 1)
        part_b_labels = np.asarray(
            [
                _format_irmaa_bracket_label(part_b_thresholds, int(tier))
                for tier in part_b_tiers
            ],
            dtype=object,
        )

        part_d_labels = np.full(n_scenarios, "none", dtype=object)
        if hasattr(params, "part_d") and hasattr(params.part_d, "irmaa"):
            part_d_scale = getattr(params.part_d.irmaa, status_key)
            part_d_thresholds = np.asarray(part_d_scale.thresholds, dtype=float)
            part_d_tiers = np.searchsorted(part_d_thresholds, magi, side="right") - 1
            part_d_tiers = np.clip(part_d_tiers, 0, len(part_d_scale.amounts) - 1)
            part_d_labels = np.asarray(
                [
                    _format_irmaa_bracket_label(part_d_thresholds, int(tier))
                    for tier in part_d_tiers
                ],
                dtype=object,
            )

        base_part_b_premium = np.asarray(
            sim.calculate("base_part_b_premium", calc_year), dtype=float
        ).flatten()
        part_b_increment = np.maximum(
            0.0,
            np.asarray(medicare_part_b_premium, dtype=float).flatten()
            - base_part_b_premium,
        )

        return {
            "base_part_b_premium": base_part_b_premium,
            "medicare_part_b_irmaa_increment": part_b_increment,
            "medicare_part_b_irmaa_bracket": part_b_labels,
            "medicare_part_d_irmaa_bracket": part_d_labels,
        }

    def calculate_batch_taxes(
        self,
        capital_gains_array: np.ndarray,
        social_security_array: np.ndarray,
        ages: np.ndarray,
        filing_status: str = "SINGLE",
        dividend_income_array: np.ndarray | None = None,
        employment_income_array: np.ndarray | None = None,
        agi_two_years_prior_array: np.ndarray | None = None,
        tax_exempt_interest_two_years_prior_array: np.ndarray | None = None,
        year: int | None = None,
    ) -> dict[str, np.ndarray]:
        """
        Calculate taxes for a batch of scenarios using PolicyEngine-US.

        Args:
            year: Calendar year for tax calculation. If None, uses self.year.
                  PolicyEngine inflates tax brackets, so future years will
                  have lower effective tax rates on the same nominal income.
        """
        n_scenarios = len(capital_gains_array)
        calc_year = year if year is not None else self.year

        if dividend_income_array is None:
            dividend_income_array = np.zeros(n_scenarios)

        if employment_income_array is None:
            employment_income_array = np.zeros(n_scenarios)

        dataset = MonteCarloDataset(
            n_scenarios=n_scenarios,
            capital_gains_array=capital_gains_array,
            social_security_array=social_security_array,
            ages=ages,
            state=self.state,
            year=calc_year,
            filing_status=filing_status,
            dividend_income_array=dividend_income_array,
            employment_income_array=employment_income_array,
            agi_two_years_prior_array=agi_two_years_prior_array,
            tax_exempt_interest_two_years_prior_array=(
                tax_exempt_interest_two_years_prior_array
            ),
        )

        try:
            dataset.generate()

            sim = Microsimulation(dataset=dataset)
            has_part_d_irmaa = (
                "income_adjusted_part_d_premium_surcharge"
                in sim.tax_benefit_system.variables
            )
            medicare_part_b_premium = sim.calculate(
                "income_adjusted_part_b_premium", calc_year
            )
            medicare_part_d_premium_surcharge = (
                sim.calculate("income_adjusted_part_d_premium_surcharge", calc_year)
                if has_part_d_irmaa
                else np.zeros(n_scenarios, dtype=float)
            )
            irmaa_details = self._medicare_irmaa_details(
                sim=sim,
                calc_year=calc_year,
                filing_status=filing_status,
                agi_two_years_prior_array=agi_two_years_prior_array,
                tax_exempt_interest_two_years_prior_array=(
                    tax_exempt_interest_two_years_prior_array
                ),
                medicare_part_b_premium=medicare_part_b_premium,
                medicare_part_d_premium_surcharge=medicare_part_d_premium_surcharge,
            )

            results = {
                "federal_income_tax": sim.calculate("income_tax", calc_year),
                "state_income_tax": sim.calculate("state_income_tax", calc_year),
                "taxable_income": sim.calculate("taxable_income", calc_year),
                "adjusted_gross_income": sim.calculate(
                    "adjusted_gross_income", calc_year
                ),
                "medicare_part_b_premium": medicare_part_b_premium,
                "medicare_part_d_premium_surcharge": medicare_part_d_premium_surcharge,
                **irmaa_details,
            }

            results["total_tax"] = (
                results["federal_income_tax"] + results["state_income_tax"]
            )
            results["total_medicare_premium"] = (
                medicare_part_b_premium + medicare_part_d_premium_surcharge
            )

            total_income = (
                capital_gains_array + social_security_array + dividend_income_array
            )
            results["effective_tax_rate"] = np.where(
                total_income > 0, results["total_tax"] / total_income, 0
            )

            return results

        finally:
            dataset.cleanup()
