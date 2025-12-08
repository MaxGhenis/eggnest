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
})
