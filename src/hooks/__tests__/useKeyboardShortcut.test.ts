/**
 * PARWA Day 7 Unit Tests — useKeyboardShortcut Hook
 *
 * Tests keyboard shortcut registration, modifier keys,
 * input field filtering, and cleanup.
 */

import { renderHook } from '@testing-library/react';
import '@testing-library/jest-dom';
import { useKeyboardShortcut } from '@/hooks/useKeyboardShortcut';

describe('useKeyboardShortcut', () => {
  it('calls handler when key is pressed', () => {
    const handler = jest.fn();
    renderHook(() =>
      useKeyboardShortcut({ key: 'Escape' }, handler)
    );

    const event = new KeyboardEvent('keydown', { key: 'Escape' });
    window.dispatchEvent(event);

    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('does not call handler for wrong key', () => {
    const handler = jest.fn();
    renderHook(() =>
      useKeyboardShortcut({ key: 'Escape' }, handler)
    );

    const event = new KeyboardEvent('keydown', { key: 'Enter' });
    window.dispatchEvent(event);

    expect(handler).not.toHaveBeenCalled();
  });

  it('calls handler with Ctrl+key', () => {
    const handler = jest.fn();
    renderHook(() =>
      useKeyboardShortcut({ key: 'k', ctrl: true }, handler)
    );

    const event = new KeyboardEvent('keydown', { key: 'k', ctrlKey: true });
    window.dispatchEvent(event);

    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('does not call handler when Ctrl is required but not held', () => {
    const handler = jest.fn();
    renderHook(() =>
      useKeyboardShortcut({ key: 'k', ctrl: true }, handler)
    );

    const event = new KeyboardEvent('keydown', { key: 'k' });
    window.dispatchEvent(event);

    expect(handler).not.toHaveBeenCalled();
  });

  it('calls handler with Meta+key', () => {
    const handler = jest.fn();
    renderHook(() =>
      useKeyboardShortcut({ key: 'k', meta: true }, handler)
    );

    const event = new KeyboardEvent('keydown', { key: 'k', metaKey: true });
    window.dispatchEvent(event);

    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('calls handler with Shift+key', () => {
    const handler = jest.fn();
    renderHook(() =>
      useKeyboardShortcut({ key: '?', shift: true }, handler)
    );

    const event = new KeyboardEvent('keydown', { key: '?', shiftKey: true });
    window.dispatchEvent(event);

    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('does not fire when typing in input field (except Escape)', () => {
    const handler = jest.fn();
    renderHook(() =>
      useKeyboardShortcut({ key: 'k', ctrl: true }, handler)
    );

    // Simulate event from an input element
    const input = document.createElement('input');
    document.body.appendChild(input);
    const event = new KeyboardEvent('keydown', { key: 'k', ctrlKey: true, bubbles: true });
    Object.defineProperty(event, 'target', { value: input, writable: false });
    window.dispatchEvent(event);

    expect(handler).not.toHaveBeenCalled();
    document.body.removeChild(input);
  });

  it('fires for Escape even when in input field', () => {
    const handler = jest.fn();
    renderHook(() =>
      useKeyboardShortcut({ key: 'Escape' }, handler)
    );

    const input = document.createElement('input');
    document.body.appendChild(input);
    const event = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true });
    Object.defineProperty(event, 'target', { value: input, writable: false });
    window.dispatchEvent(event);

    expect(handler).toHaveBeenCalledTimes(1);
    document.body.removeChild(input);
  });

  it('does not fire when enabled is false', () => {
    const handler = jest.fn();
    renderHook(() =>
      useKeyboardShortcut({ key: 'k', enabled: false }, handler)
    );

    const event = new KeyboardEvent('keydown', { key: 'k' });
    window.dispatchEvent(event);

    expect(handler).not.toHaveBeenCalled();
  });

  it('prevents default when preventDefault is true', () => {
    const handler = jest.fn();
    renderHook(() =>
      useKeyboardShortcut({ key: 'k', ctrl: true, preventDefault: true }, handler)
    );

    const event = new KeyboardEvent('keydown', { key: 'k', ctrlKey: true, cancelable: true });
    const spy = jest.spyOn(event, 'preventDefault');
    window.dispatchEvent(event);

    expect(spy).toHaveBeenCalled();
  });

  it('cleans up event listener on unmount', () => {
    const handler = jest.fn();
    const { unmount } = renderHook(() =>
      useKeyboardShortcut({ key: 'Escape' }, handler)
    );

    unmount();

    const event = new KeyboardEvent('keydown', { key: 'Escape' });
    window.dispatchEvent(event);

    expect(handler).not.toHaveBeenCalled();
  });
});
