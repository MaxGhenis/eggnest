"""Tax calculations using PolicyEngine-US."""

import tempfile
from pathlib import Path

import numpy as np
from policyengine_core.data import Dataset
from policyengine_us import Microsimulation


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

        filing_status_map = {
            "SINGLE": 1,
            "single": 1,
            "JOINT": 2,
            "married_filing_jointly": 2,
            "SEPARATE": 3,
            "married_filing_separately": 3,
            "HEAD_OF_HOUSEHOLD": 4,
            "head_of_household": 4,
            "WIDOW": 5,
        }
        filing_status_values = np.full(
            self.n_scenarios, filing_status_map.get(self.filing_status, 1)
        )

        state_fips_map = {
            "AL": 1,
            "AK": 2,
            "AZ": 4,
            "AR": 5,
            "CA": 6,
            "CO": 8,
            "CT": 9,
            "DE": 10,
            "DC": 11,
            "FL": 12,
            "GA": 13,
            "HI": 15,
            "ID": 16,
            "IL": 17,
            "IN": 18,
            "IA": 19,
            "KS": 20,
            "KY": 21,
            "LA": 22,
            "ME": 23,
            "MD": 24,
            "MA": 25,
            "MI": 26,
            "MN": 27,
            "MS": 28,
            "MO": 29,
            "MT": 30,
            "NE": 31,
            "NV": 32,
            "NH": 33,
            "NJ": 34,
            "NM": 35,
            "NY": 36,
            "NC": 37,
            "ND": 38,
            "OH": 39,
            "OK": 40,
            "OR": 41,
            "PA": 42,
            "RI": 44,
            "SC": 45,
            "SD": 46,
            "TN": 47,
            "TX": 48,
            "UT": 49,
            "VT": 50,
            "VA": 51,
            "WA": 53,
            "WV": 54,
            "WI": 55,
            "WY": 56,
        }
        state_code = state_fips_map.get(self.state, 6)

        data = {
            "person_id": {self.year: person_ids},
            "person_household_id": {self.year: household_ids},
            "person_tax_unit_id": {self.year: tax_unit_ids},
            "person_family_id": {self.year: family_ids},
            "person_spm_unit_id": {self.year: spm_unit_ids},
            "person_marital_unit_id": {self.year: marital_unit_ids},
            "person_weight": {self.year: weights},
            "age": {self.year: self.ages},
            "long_term_capital_gains": {self.year: self.capital_gains},
            "social_security": {self.year: self.social_security},
            "social_security_retirement": {self.year: self.social_security},
            "employment_income": {self.year: self.employment_income},
            "interest_income": {self.year: np.zeros(self.n_scenarios)},
            "dividend_income": {self.year: self.dividend_income},
            "household_id": {self.year: household_ids},
            "household_weight": {self.year: weights},
            "household_state_fips": {self.year: np.full(self.n_scenarios, state_code)},
            "tax_unit_id": {self.year: tax_unit_ids},
            "tax_unit_weight": {self.year: weights},
            "filing_status": {self.year: filing_status_values},
            "family_id": {self.year: family_ids},
            "family_weight": {self.year: weights},
            "spm_unit_id": {self.year: spm_unit_ids},
            "spm_unit_weight": {self.year: weights},
            "marital_unit_id": {self.year: marital_unit_ids},
            "marital_unit_weight": {self.year: weights},
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

    def calculate_batch_taxes(
        self,
        capital_gains_array: np.ndarray,
        social_security_array: np.ndarray,
        ages: np.ndarray,
        filing_status: str = "SINGLE",
        dividend_income_array: np.ndarray | None = None,
        employment_income_array: np.ndarray | None = None,
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
        )

        try:
            dataset.generate()

            sim = Microsimulation(dataset=dataset)

            results = {
                "federal_income_tax": sim.calculate("income_tax", calc_year),
                "state_income_tax": sim.calculate("state_income_tax", calc_year),
                "taxable_income": sim.calculate("taxable_income", calc_year),
            }

            results["total_tax"] = (
                results["federal_income_tax"] + results["state_income_tax"]
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
