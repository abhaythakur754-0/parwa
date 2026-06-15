/**
 * PARWA Day 7 Unit Tests — useFocusTrap Hook
 *
 * Tests focus trapping, Tab cycling, Shift+Tab, Escape handling,
 * auto-focus, restore focus, and deactivation.
 */

import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { useFocusTrap } from '@/hooks/useFocusTrap';

// ── Test Component ────────────────────────────────────────────────

function FocusTrapTestComponent({
  active = true,
  autoFocus = true,
  restoreFocus = true,
  onEscape,
}: {
  active?: boolean;
  autoFocus?: boolean;
  restoreFocus?: boolean;
  onEscape?: () => void;
}) {
  const containerRef = React.useRef<HTMLDivElement>(null);
  useFocusTrap(containerRef, { active, autoFocus, restoreFocus, onEscape });

  return React.createElement('div', null,
    React.createElement('button', { 'data-testid': 'outside-button' }, 'Outside'),
    React.createElement('div', { ref: containerRef, 'data-testid': 'trap-container' },
      React.createElement('button', { 'data-testid': 'first-btn' }, 'First'),
      React.createElement('button', { 'data-testid': 'second-btn' }, 'Second'),
      React.createElement('button', { 'data-testid': 'third-btn' }, 'Third')
    )
  );
}

function EmptyTrapComponent() {
  const containerRef = React.useRef<HTMLDivElement>(null);
  useFocusTrap(containerRef);

  return React.createElement('div', { ref: containerRef, 'data-testid': 'empty-trap' },
    React.createElement('p', null, 'No focusable elements')
  );
}

describe('useFocusTrap', () => {
  it('renders the trap container with focusable elements', () => {
    render(React.createElement(FocusTrapTestComponent));
    expect(screen.getByTestId('trap-container')).toBeInTheDocument();
    expect(screen.getByTestId('first-btn')).toBeInTheDocument();
    expect(screen.getByTestId('second-btn')).toBeInTheDocument();
    expect(screen.getByTestId('third-btn')).toBeInTheDocument();
  });

  it('auto-focuses the first focusable element when active', () => {
    render(React.createElement(FocusTrapTestComponent));
    // auto-focus has a 50ms delay
    return new Promise<void>((resolve) => {
      setTimeout(() => {
        expect(screen.getByTestId('first-btn')).toHaveFocus();
        resolve();
      }, 100);
    });
  });

  it('does not auto-focus when autoFocus is false', () => {
    render(React.createElement(FocusTrapTestComponent, { autoFocus: false }));
    expect(screen.getByTestId('first-btn')).not.toHaveFocus();
  });

  it('wraps Tab from last to first element', () => {
    render(React.createElement(FocusTrapTestComponent));

    const lastBtn = screen.getByTestId('third-btn');
    const firstBtn = screen.getByTestId('first-btn');

    // Focus the last button
    lastBtn.focus();
    expect(lastBtn).toHaveFocus();

    // Tab from last should wrap to first
    fireEvent.keyDown(screen.getByTestId('trap-container'), {
      key: 'Tab',
      bubbles: true,
    });

    expect(firstBtn).toHaveFocus();
  });

  it('wraps Shift+Tab from first to last element', () => {
    render(React.createElement(FocusTrapTestComponent));

    const firstBtn = screen.getByTestId('first-btn');
    const lastBtn = screen.getByTestId('third-btn');

    // Focus the first button
    firstBtn.focus();
    expect(firstBtn).toHaveFocus();

    // Shift+Tab from first should wrap to last
    fireEvent.keyDown(screen.getByTestId('trap-container'), {
      key: 'Tab',
      shiftKey: true,
      bubbles: true,
    });

    expect(lastBtn).toHaveFocus();
  });

  it('calls onEscape when Escape is pressed', () => {
    const onEscape = jest.fn();
    render(React.createElement(FocusTrapTestComponent, { onEscape }));

    fireEvent.keyDown(screen.getByTestId('trap-container'), {
      key: 'Escape',
      bubbles: true,
    });

    expect(onEscape).toHaveBeenCalledTimes(1);
  });

  it('does not attach handlers when active is false', () => {
    const onEscape = jest.fn();
    render(React.createElement(FocusTrapTestComponent, { active: false, onEscape }));

    fireEvent.keyDown(screen.getByTestId('trap-container'), {
      key: 'Escape',
      bubbles: true,
    });

    // onEscape should NOT be called since trap is inactive
    expect(onEscape).not.toHaveBeenCalled();
  });

  it('handles container with no focusable elements', () => {
    render(React.createElement(EmptyTrapComponent));

    // Tab in an empty container should not crash
    fireEvent.keyDown(screen.getByTestId('empty-trap'), {
      key: 'Tab',
      bubbles: true,
    });

    expect(screen.getByTestId('empty-trap')).toBeInTheDocument();
  });

  it('does not intercept Tab when focus is on middle element', () => {
    render(React.createElement(FocusTrapTestComponent));

    const secondBtn = screen.getByTestId('second-btn');

    // Focus the middle button
    secondBtn.focus();
    expect(secondBtn).toHaveFocus();

    // Tab from middle element — the trap should NOT wrap focus
    // (it only wraps from last→first or first→last)
    fireEvent.keyDown(screen.getByTestId('trap-container'), {
      key: 'Tab',
      bubbles: true,
    });

    // Focus should still be on second (Tab from middle isn't handled by the trap)
    // The browser's default Tab behavior would move focus, but fireEvent
    // only fires the event — it doesn't actually move focus.
    // The important thing is that the trap didn't force focus to first or last.
    expect(screen.getByTestId('first-btn')).not.toHaveFocus();
    expect(screen.getByTestId('third-btn')).not.toHaveFocus();
  });
});
