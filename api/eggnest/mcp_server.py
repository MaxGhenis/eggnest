"""EggNest MCP server.

Expose the local retirement modeling engine over stdio so AI agents can call it
without going through the web API.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .mcp_tools import (
    analyze_compensation_tool,
    calculate_household_tool,
    compare_allocations_tool,
    compare_life_event_tool,
    compare_roth_conversions_tool,
    compare_social_security_timing_tool,
    compare_withdrawal_strategies_tool,
    describe_engine_tool,
    historical_backtest_tool,
    optimize_roth_conversions_report_tool,
    optimize_roth_conversions_tool,
    simulate_plan,
)


def build_mcp_server() -> FastMCP:
    """Create the stdio MCP server."""
    mcp = FastMCP("EggNest", json_response=True)

    @mcp.tool()
    def describe_engine() -> dict:
        """Describe the local EggNest engine surface and capabilities."""
        return describe_engine_tool()

    @mcp.tool()
    def simulate_retirement_plan(input_data: dict) -> dict:
        """Run one Monte Carlo retirement simulation from a SimulationInput payload."""
        return simulate_plan(input_data)

    @mcp.tool()
    def historical_backtest(base_input: dict, start_years: list[int] | None = None) -> dict:
        """Replay the current plan across deterministic historical retirement cohorts."""
        return historical_backtest_tool(base_input=base_input, start_years=start_years)

    @mcp.tool()
    def compare_withdrawal_strategies(
        base_input: dict,
        strategies: list[str] | None = None,
    ) -> dict:
        """Compare withdrawal strategies for a detailed-holdings plan."""
        return compare_withdrawal_strategies_tool(
            base_input=base_input,
            strategies=strategies,
        )

    @mcp.tool()
    def compare_roth_conversions(
        base_input: dict,
        annual_conversion_amounts: list[float] | None = None,
        conversion_policies: list[str] | None = None,
        conversion_start_age: int | None = None,
        conversion_end_age: int | None = None,
    ) -> dict:
        """Compare fixed and bracket-fill Roth conversion scenarios for a detailed-holdings plan."""
        return compare_roth_conversions_tool(
            base_input=base_input,
            annual_conversion_amounts=annual_conversion_amounts,
            conversion_policies=conversion_policies,
            conversion_start_age=conversion_start_age,
            conversion_end_age=conversion_end_age,
        )

    @mcp.tool()
    def optimize_roth_conversions(
        base_input: dict,
        annual_conversion_amounts: list[float] | None = None,
        conversion_policies: list[str] | None = None,
        candidate_start_ages: list[int] | None = None,
        window_lengths: list[int] | None = None,
    ) -> dict:
        """Search bounded Roth conversion windows and sizing rules on one plan."""
        return optimize_roth_conversions_tool(
            base_input=base_input,
            annual_conversion_amounts=annual_conversion_amounts,
            conversion_policies=conversion_policies,
            candidate_start_ages=candidate_start_ages,
            window_lengths=window_lengths,
        )

    @mcp.tool()
    def optimize_roth_conversions_report(
        base_input: dict,
        annual_conversion_amounts: list[float] | None = None,
        conversion_policies: list[str] | None = None,
        candidate_start_ages: list[int] | None = None,
        window_lengths: list[int] | None = None,
    ) -> dict:
        """Search Roth conversion candidates and return an export-friendly report artifact."""
        return optimize_roth_conversions_report_tool(
            base_input=base_input,
            annual_conversion_amounts=annual_conversion_amounts,
            conversion_policies=conversion_policies,
            candidate_start_ages=candidate_start_ages,
            window_lengths=window_lengths,
        )

    @mcp.tool()
    def compare_allocations(
        base_input: dict,
        allocations: list[float] | None = None,
    ) -> dict:
        """Compare alternative stock allocations on the same plan."""
        return compare_allocations_tool(base_input=base_input, allocations=allocations)

    @mcp.tool()
    def compare_social_security_timing(
        base_input: dict,
        birth_year: int,
        pia_monthly: float,
        claiming_ages: list[int] | None = None,
    ) -> dict:
        """Compare Social Security claiming ages under one shared scenario."""
        return compare_social_security_timing_tool(
            base_input=base_input,
            birth_year=birth_year,
            pia_monthly=pia_monthly,
            claiming_ages=claiming_ages,
        )

    @mcp.tool()
    def calculate_household(household: dict) -> dict:
        """Calculate taxes and benefits for one household payload."""
        return calculate_household_tool(household)

    @mcp.tool()
    def compare_life_event(before: dict, after: dict, event_name: str = "Life Event") -> dict:
        """Compare taxes and benefits before and after a household change."""
        return compare_life_event_tool(before=before, after=after, event_name=event_name)

    @mcp.tool()
    def analyze_compensation(input_data: dict) -> list[dict]:
        """Analyze employer packages and employee after-tax value."""
        return analyze_compensation_tool(input_data)

    return mcp


def main() -> None:
    """Run the EggNest MCP server over stdio."""
    build_mcp_server().run()


if __name__ == "__main__":
    main()
