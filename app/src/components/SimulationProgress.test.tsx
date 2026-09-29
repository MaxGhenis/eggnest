import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SimulationProgress } from './SimulationProgress'

describe('SimulationProgress', () => {
  it('renders progress bar with correct percentage', () => {
    render(<SimulationProgress currentYear={15} totalYears={30} />)

    expect(screen.getByRole('progressbar')).toBeInTheDocument()
    expect(screen.getByText(/50%/)).toBeInTheDocument()
  })

  it('shows 0% at start', () => {
    render(<SimulationProgress currentYear={0} totalYears={30} />)

    expect(screen.getByText(/0%/)).toBeInTheDocument()
  })

  it('shows 100% when complete', () => {
    render(<SimulationProgress currentYear={30} totalYears={30} />)

    expect(screen.getByText(/100%/)).toBeInTheDocument()
  })

  it('displays year information', () => {
    render(<SimulationProgress currentYear={10} totalYears={30} />)

    expect(screen.getByText(/Year 10 of 30/)).toBeInTheDocument()
  })

  it('shows message about PolicyEngine calculations', () => {
    render(<SimulationProgress currentYear={5} totalYears={30} />)

    expect(screen.getByText(/Calculating taxes/i)).toBeInTheDocument()
  })

  it('uses fractional progress for sub-year updates', () => {
    render(<SimulationProgress currentYear={0.35} totalYears={30} progress={0.02} message="Preparing cash flows" />)

    expect(screen.getByText(/2%/)).toBeInTheDocument()
    expect(screen.getByText(/Year 1 of 30/)).toBeInTheDocument()
    expect(screen.getByText(/Preparing cash flows/)).toBeInTheDocument()
  })

  it('shows the latest completed year preview', () => {
    render(
      <SimulationProgress
        currentYear={2}
        totalYears={30}
        progress={0.07}
        yearSummary={{
          year: 2,
          age: 67,
          median_portfolio: 500000,
          p25_portfolio: 400000,
          p75_portfolio: 650000,
          active_paths: 1000,
          median_tax: 2500,
          median_withdrawal: 30000,
        }}
      />
    )

    expect(screen.getByText(/Year 2 result/)).toBeInTheDocument()
    expect(screen.getByText(/Median portfolio/)).toBeInTheDocument()
    expect(screen.getByText(/Middle range/)).toBeInTheDocument()
  })
})
