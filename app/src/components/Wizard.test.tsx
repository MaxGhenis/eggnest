import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Wizard, type WizardStep } from './Wizard'

const mockSteps: WizardStep[] = [
  {
    id: 'step1',
    title: 'Step 1',
    subtitle: 'First step',
    content: <div>Step 1 content</div>,
  },
  {
    id: 'step2',
    title: 'Step 2',
    subtitle: 'Second step',
    content: <div>Step 2 content</div>,
  },
  {
    id: 'step3',
    title: 'Step 3',
    subtitle: 'Third step',
    optional: true,
    content: <div>Step 3 content</div>,
  },
]

describe('Wizard', () => {
  it('renders the first step by default', () => {
    render(<Wizard steps={mockSteps} onComplete={vi.fn()} />)

    expect(screen.getByRole('heading', { name: 'Step 1' })).toBeInTheDocument()
    expect(screen.getByText('Step 1 content')).toBeInTheDocument()
    expect(screen.getByText(/Step 1 of 3/)).toBeInTheDocument()
  })

  it('shows Back button disabled on first step', () => {
    render(<Wizard steps={mockSteps} onComplete={vi.fn()} />)

    const backButton = screen.getByRole('button', { name: /previous step/i })
    expect(backButton).toBeDisabled()
  })

  it('navigates to next step when clicking Next', async () => {
    const user = userEvent.setup()
    render(<Wizard steps={mockSteps} onComplete={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: /next/i }))

    expect(screen.getByText('Step 2 content')).toBeInTheDocument()
    expect(screen.getByText('Step 2 of 3')).toBeInTheDocument()
  })

  it('navigates back when clicking Back', async () => {
    const user = userEvent.setup()
    render(<Wizard steps={mockSteps} onComplete={vi.fn()} />)

    // Go to step 2
    await user.click(screen.getByRole('button', { name: /next/i }))
    expect(screen.getByText('Step 2 content')).toBeInTheDocument()

    // Go back to step 1
    await user.click(screen.getByRole('button', { name: /previous step/i }))
    expect(screen.getByText('Step 1 content')).toBeInTheDocument()
  })

  it('shows optional badge for optional steps', () => {
    render(<Wizard steps={mockSteps} onComplete={vi.fn()} />)

    expect(screen.getByText('Optional')).toBeInTheDocument()
  })

  it('calls onComplete when clicking button on last step', async () => {
    const onComplete = vi.fn()
    const user = userEvent.setup()
    render(<Wizard steps={mockSteps} onComplete={onComplete} />)

    // Navigate to last step
    await user.click(screen.getByRole('button', { name: /next/i }))
    await user.click(screen.getByRole('button', { name: /next/i }))

    // Click complete button
    await user.click(screen.getByRole('button', { name: /run simulation/i }))

    expect(onComplete).toHaveBeenCalledTimes(1)
  })

  it('shows custom complete button text', async () => {
    const user = userEvent.setup()
    render(
      <Wizard
        steps={mockSteps}
        onComplete={vi.fn()}
        completeButtonText="Submit Form"
      />
    )

    // Navigate to last step
    await user.click(screen.getByRole('button', { name: /next/i }))
    await user.click(screen.getByRole('button', { name: /next/i }))

    expect(screen.getByRole('button', { name: /submit form/i })).toBeInTheDocument()
  })

  it('shows loading state when isLoading is true on last step', async () => {
    const user = userEvent.setup()
    const { rerender } = render(
      <Wizard
        steps={mockSteps}
        onComplete={vi.fn()}
        isLoading={false}
        loadingButtonText="Processing..."
      />
    )

    // Navigate to last step
    await user.click(screen.getByRole('button', { name: /next/i }))
    await user.click(screen.getByRole('button', { name: /next/i }))

    // Now set loading
    rerender(
      <Wizard
        steps={mockSteps}
        onComplete={vi.fn()}
        isLoading={true}
        loadingButtonText="Processing..."
      />
    )

    const button = screen.getByRole('button', { name: /processing/i })
    expect(button).toBeDisabled()
  })

  it('allows clicking on completed steps to navigate back', async () => {
    const user = userEvent.setup()
    render(<Wizard steps={mockSteps} onComplete={vi.fn()} />)

    // Go to step 2
    await user.click(screen.getByRole('button', { name: /next/i }))
    expect(screen.getByText('Step 2 content')).toBeInTheDocument()

    // Click on step 1 indicator (first button in progress bar)
    const stepIndicators = screen.getAllByRole('button')
    const step1Indicator = stepIndicators.find(btn => btn.classList.contains('wizard-step-indicator') && btn.classList.contains('completed'))
    expect(step1Indicator).toBeDefined()
    await user.click(step1Indicator!)

    expect(screen.getByText('Step 1 content')).toBeInTheDocument()
  })

  it('marks completed steps with checkmark', async () => {
    const user = userEvent.setup()
    render(<Wizard steps={mockSteps} onComplete={vi.fn()} />)

    // Go to step 2
    await user.click(screen.getByRole('button', { name: /next/i }))

    // Step 1 should have checkmark (svg path)
    const step1Button = screen.getAllByRole('button')[0]
    expect(step1Button.querySelector('svg')).toBeInTheDocument()
  })
})
