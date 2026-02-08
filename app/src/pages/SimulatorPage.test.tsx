import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import { SimulatorPage } from './SimulatorPage';

describe('SimulatorPage - Portfolio Mode', () => {
  const navigateToMoneyStep = async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><SimulatorPage /></MemoryRouter>);

    // Click "Start from scratch"
    const startButton = screen.getByText('Start from scratch with your own numbers');
    await user.click(startButton);

    // Click "Next" to get to money step
    const nextButton = screen.getByText('Next');
    await user.click(nextButton);
  };

  it('should show simple mode by default', async () => {
    await navigateToMoneyStep();

    // Should see "Current Portfolio Value" label
    expect(screen.getByText(/current portfolio value/i)).toBeInTheDocument();
  });

  it('should show detailed mode explainer when switching to detailed mode', async () => {
    await navigateToMoneyStep();

    const user = userEvent.setup();

    // Click "By Account Type" button to switch to detailed mode
    const detailedModeButton = screen.getByText('By Account Type');
    await user.click(detailedModeButton);

    // Should see the detailed mode explainer
    expect(screen.getByText(/track each account separately/i)).toBeInTheDocument();
    expect(screen.getByText(/rmds automatically calculated/i)).toBeInTheDocument();
  });

  it('should show holdings editor in detailed mode', async () => {
    await navigateToMoneyStep();

    const user = userEvent.setup();

    // Click "By Account Type" button to switch to detailed mode
    const detailedModeButton = screen.getByText('By Account Type');
    await user.click(detailedModeButton);

    // Should see empty state
    expect(screen.getByText(/no holdings added yet/i)).toBeInTheDocument();
    expect(screen.getByText(/add holding/i)).toBeInTheDocument();
  });

  it('should not show withdrawal strategy selector in simple portfolio mode', async () => {
    await navigateToMoneyStep();

    // In simple mode - should not see withdrawal strategy
    const withdrawalStrategyLabel = screen.queryByText(/Withdrawal Strategy/i);
    expect(withdrawalStrategyLabel).toBeNull();
  });

  it('should show withdrawal strategy selector when in detailed portfolio mode', async () => {
    await navigateToMoneyStep();

    const user = userEvent.setup();

    // Click "By Account Type" button to switch to detailed mode
    const detailedModeButton = screen.getByText('By Account Type');
    await user.click(detailedModeButton);

    // Should now see withdrawal strategy selector
    const withdrawalStrategyLabel = screen.queryByText(/Withdrawal Strategy/i);
    expect(withdrawalStrategyLabel).not.toBeNull();
  });

  it('should default to taxable_first withdrawal strategy', async () => {
    await navigateToMoneyStep();

    const user = userEvent.setup();

    // Switch to detailed mode
    const detailedModeButton = screen.getByText('By Account Type');
    await user.click(detailedModeButton);

    // Check that "Taxable First" is selected
    const select = screen.getByLabelText(/Withdrawal Strategy/i) as HTMLSelectElement;
    expect(select.value).toBe('taxable_first');
  });

  it('should have all four withdrawal strategy options', async () => {
    await navigateToMoneyStep();

    const user = userEvent.setup();

    // Switch to detailed mode
    const detailedModeButton = screen.getByText('By Account Type');
    await user.click(detailedModeButton);

    const select = screen.getByLabelText(/Withdrawal Strategy/i);
    const options = Array.from(select.querySelectorAll('option'));

    expect(options).toHaveLength(4);
    expect(options.map(o => o.value)).toEqual([
      'taxable_first',
      'traditional_first',
      'roth_first',
      'pro_rata'
    ]);
  });
});
