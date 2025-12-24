import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { HoldingsEditor } from './HoldingsEditor';
import type { Holding } from '../lib/api';

describe('HoldingsEditor', () => {
  it('should render empty state when no holdings', () => {
    const onChange = vi.fn();
    render(<HoldingsEditor holdings={[]} onChange={onChange} />);

    expect(screen.getByText(/add your portfolio holdings/i)).toBeInTheDocument();
  });

  it('should render add button', () => {
    const onChange = vi.fn();
    render(<HoldingsEditor holdings={[]} onChange={onChange} />);

    expect(screen.getByText(/add holding/i)).toBeInTheDocument();
  });

  it('should display existing holdings', () => {
    const holdings: Holding[] = [
      { account_type: 'traditional_401k', fund: 'vt', balance: 300000 },
      { account_type: 'roth_ira', fund: 'sp500', balance: 100000 },
    ];
    const onChange = vi.fn();

    render(<HoldingsEditor holdings={holdings} onChange={onChange} />);

    expect(screen.getByDisplayValue('300000')).toBeInTheDocument();
    expect(screen.getByDisplayValue('100000')).toBeInTheDocument();
  });

  it('should call onChange when adding a holding', () => {
    const onChange = vi.fn();
    render(<HoldingsEditor holdings={[]} onChange={onChange} />);

    const addButton = screen.getByText(/add holding/i);
    fireEvent.click(addButton);

    expect(onChange).toHaveBeenCalledWith([
      {
        account_type: 'traditional_401k',
        fund: 'vt',
        balance: 0,
      },
    ]);
  });

  it('should call onChange when removing a holding', () => {
    const holdings: Holding[] = [
      { account_type: 'traditional_401k', fund: 'vt', balance: 300000 },
      { account_type: 'roth_ira', fund: 'sp500', balance: 100000 },
    ];
    const onChange = vi.fn();

    render(<HoldingsEditor holdings={holdings} onChange={onChange} />);

    const removeButtons = screen.getAllByLabelText(/remove holding/i);
    fireEvent.click(removeButtons[0]);

    expect(onChange).toHaveBeenCalledWith([
      { account_type: 'roth_ira', fund: 'sp500', balance: 100000 },
    ]);
  });

  it('should call onChange when updating account type', () => {
    const holdings: Holding[] = [
      { account_type: 'traditional_401k', fund: 'vt', balance: 300000 },
    ];
    const onChange = vi.fn();

    render(<HoldingsEditor holdings={holdings} onChange={onChange} />);

    const select = screen.getByLabelText(/account type/i);
    fireEvent.change(select, { target: { value: 'roth_ira' } });

    expect(onChange).toHaveBeenCalledWith([
      { account_type: 'roth_ira', fund: 'vt', balance: 300000 },
    ]);
  });

  it('should call onChange when updating fund', () => {
    const holdings: Holding[] = [
      { account_type: 'traditional_401k', fund: 'vt', balance: 300000 },
    ];
    const onChange = vi.fn();

    render(<HoldingsEditor holdings={holdings} onChange={onChange} />);

    const select = screen.getByLabelText(/fund/i);
    fireEvent.change(select, { target: { value: 'sp500' } });

    expect(onChange).toHaveBeenCalledWith([
      { account_type: 'traditional_401k', fund: 'sp500', balance: 300000 },
    ]);
  });

  it('should call onChange when updating balance', () => {
    const holdings: Holding[] = [
      { account_type: 'traditional_401k', fund: 'vt', balance: 300000 },
    ];
    const onChange = vi.fn();

    render(<HoldingsEditor holdings={holdings} onChange={onChange} />);

    const input = screen.getByDisplayValue('300000');
    fireEvent.change(input, { target: { value: '350000' } });

    expect(onChange).toHaveBeenCalledWith([
      { account_type: 'traditional_401k', fund: 'vt', balance: 350000 },
    ]);
  });

  it('should display total portfolio value', () => {
    const holdings: Holding[] = [
      { account_type: 'traditional_401k', fund: 'vt', balance: 300000 },
      { account_type: 'roth_ira', fund: 'sp500', balance: 100000 },
      { account_type: 'taxable', fund: 'bnd', balance: 50000 },
    ];
    const onChange = vi.fn();

    render(<HoldingsEditor holdings={holdings} onChange={onChange} />);

    expect(screen.getByText(/total portfolio/i)).toBeInTheDocument();
    expect(screen.getByText(/\$450,000/)).toBeInTheDocument();
  });

  it('should display account type labels correctly', () => {
    const holdings: Holding[] = [
      { account_type: 'traditional_401k', fund: 'vt', balance: 100000 },
      { account_type: 'traditional_ira', fund: 'vt', balance: 100000 },
      { account_type: 'roth_401k', fund: 'vt', balance: 100000 },
      { account_type: 'roth_ira', fund: 'vt', balance: 100000 },
      { account_type: 'taxable', fund: 'vt', balance: 100000 },
    ];
    const onChange = vi.fn();

    render(<HoldingsEditor holdings={holdings} onChange={onChange} />);

    // All account types should be present in the select options (checking for at least one)
    expect(screen.getAllByText('Traditional 401(k)').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Traditional IRA').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Roth 401(k)').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Roth IRA').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Taxable').length).toBeGreaterThan(0);
  });

  it('should display fund type labels correctly', () => {
    const holdings: Holding[] = [
      { account_type: 'taxable', fund: 'vt', balance: 100000 },
      { account_type: 'taxable', fund: 'sp500', balance: 100000 },
      { account_type: 'taxable', fund: 'bnd', balance: 100000 },
      { account_type: 'taxable', fund: 'treasury', balance: 100000 },
    ];
    const onChange = vi.fn();

    render(<HoldingsEditor holdings={holdings} onChange={onChange} />);

    // All fund types should be present in the select options (checking for at least one)
    expect(screen.getAllByText('VT (Total World)').length).toBeGreaterThan(0);
    expect(screen.getAllByText('S&P 500').length).toBeGreaterThan(0);
    expect(screen.getAllByText('BND (Total Bond)').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Treasury Bonds').length).toBeGreaterThan(0);
  });
});
