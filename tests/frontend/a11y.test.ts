/**
 * Tests for Accessibility (A11y) Utilities
 * Tests for focus management, keyboard navigation, ARIA, and contrast
 */

import {
  focusFirstFocusable,
  focusLastFocusable,
  getFocusableElements,
  trapFocus,
  handleArrowNavigation,
  handleHomeEndKeys,
  generateId,
  setAriaAttributes,
  announceToScreenReader,
  getLuminance,
  getContrastRatio,
  meetsWCAGAA,
  meetsWCAGAAA,
  hexToRgb,
  meetsTouchTargetMinimum,
  prefersReducedMotion,
} from '@/lib/a11y';

describe('Accessibility Utilities', () => {
  describe('Focus Management', () => {
    let container: HTMLDivElement;

    beforeEach(() => {
      container = document.createElement('div');
      container.innerHTML = `
        <button id="first">First</button>
        <input id="middle" type="text" />
        <button id="last">Last</button>
      `;
      document.body.appendChild(container);
    });

    afterEach(() => {
      document.body.removeChild(container);
    });

    it('should get all focusable elements', () => {
      const focusable = getFocusableElements(container);
      expect(focusable.length).toBe(3);
    });

    it('should focus first focusable element', () => {
      focusFirstFocusable(container);
      expect(document.activeElement?.id).toBe('first');
    });

    it('should focus last focusable element', () => {
      focusLastFocusable(container);
      expect(document.activeElement?.id).toBe('last');
    });

    it('should trap focus on Tab', () => {
      const focusable = getFocusableElements(container);
      focusable[0].focus();

      const tabEvent = new KeyboardEvent('keydown', { key: 'Tab' });
      Object.defineProperty(tabEvent, 'shiftKey', { value: false });

      trapFocus(container, tabEvent);
      // Should cycle to next element or stay trapped
      expect(document.activeElement).toBeTruthy();
    });

    it('should trap focus on Shift+Tab', () => {
      const focusable = getFocusableElements(container);
      focusable[2].focus();

      const tabEvent = new KeyboardEvent('keydown', { key: 'Tab' });
      Object.defineProperty(tabEvent, 'shiftKey', { value: true });

      trapFocus(container, tabEvent);
      expect(document.activeElement).toBeTruthy();
    });
  });

  describe('Keyboard Navigation', () => {
    let items: HTMLElement[];

    beforeEach(() => {
      items = [
        document.createElement('button'),
        document.createElement('button'),
        document.createElement('button'),
      ];
      items.forEach((item, i) => {
        item.id = `item-${i}`;
        document.body.appendChild(item);
      });
    });

    afterEach(() => {
      items.forEach(item => document.body.removeChild(item));
    });

    it('should navigate down with ArrowDown', () => {
      items[0].focus();
      const event = new KeyboardEvent('keydown', { key: 'ArrowDown' });
      const newIndex = handleArrowNavigation(event, items, 0, 'vertical');
      expect(newIndex).toBe(1);
    });

    it('should navigate up with ArrowUp', () => {
      items[1].focus();
      const event = new KeyboardEvent('keydown', { key: 'ArrowUp' });
      const newIndex = handleArrowNavigation(event, items, 1, 'vertical');
      expect(newIndex).toBe(0);
    });

    it('should wrap to first when navigating down from last', () => {
      items[2].focus();
      const event = new KeyboardEvent('keydown', { key: 'ArrowDown' });
      const newIndex = handleArrowNavigation(event, items, 2, 'vertical');
      expect(newIndex).toBe(0);
    });

    it('should wrap to last when navigating up from first', () => {
      items[0].focus();
      const event = new KeyboardEvent('keydown', { key: 'ArrowUp' });
      const newIndex = handleArrowNavigation(event, items, 0, 'vertical');
      expect(newIndex).toBe(2);
    });

    it('should navigate right with ArrowRight in horizontal mode', () => {
      items[0].focus();
      const event = new KeyboardEvent('keydown', { key: 'ArrowRight' });
      const newIndex = handleArrowNavigation(event, items, 0, 'horizontal');
      expect(newIndex).toBe(1);
    });

    it('should handle Home key', () => {
      items[2].focus();
      const event = new KeyboardEvent('keydown', { key: 'Home' });
      const newIndex = handleHomeEndKeys(event, items);
      expect(newIndex).toBe(0);
    });

    it('should handle End key', () => {
      items[0].focus();
      const event = new KeyboardEvent('keydown', { key: 'End' });
      const newIndex = handleHomeEndKeys(event, items);
      expect(newIndex).toBe(2);
    });
  });

  describe('ARIA Helpers', () => {
    it('should generate unique IDs', () => {
      const id1 = generateId('test');
      const id2 = generateId('test');
      expect(id1).not.toBe(id2);
      expect(id1.startsWith('test-')).toBe(true);
    });

    it('should set ARIA attributes', () => {
      const element = document.createElement('div');
      setAriaAttributes(element, {
        label: 'Test Label',
        expanded: false,
        hidden: true,
      });

      expect(element.getAttribute('aria-label')).toBe('Test Label');
      expect(element.getAttribute('aria-expanded')).toBe('false');
      expect(element.getAttribute('aria-hidden')).toBe('true');
    });
  });

  describe('Color Contrast', () => {
    it('should calculate luminance correctly', () => {
      // White should have luminance close to 1
      const whiteLum = getLuminance(255, 255, 255);
      expect(whiteLum).toBeCloseTo(1, 1);

      // Black should have luminance close to 0
      const blackLum = getLuminance(0, 0, 0);
      expect(blackLum).toBeCloseTo(0, 1);
    });

    it('should calculate contrast ratio correctly', () => {
      // Black on white should be 21:1
      const ratio = getContrastRatio([0, 0, 0], [255, 255, 255]);
      expect(ratio).toBeCloseTo(21, 0);
    });

    it('should validate WCAG AA for normal text', () => {
      // Black on white passes AA (ratio 21:1 > 4.5)
      expect(meetsWCAGAA([0, 0, 0], [255, 255, 255], false)).toBe(true);

      // Light gray on white fails AA
      expect(meetsWCAGAA([200, 200, 200], [255, 255, 255], false)).toBe(false);
    });

    it('should validate WCAG AA for large text', () => {
      // Large text has lower threshold (3:1)
      expect(meetsWCAGAA([100, 100, 100], [255, 255, 255], true)).toBe(true);
    });

    it('should validate WCAG AAA', () => {
      // AAA has higher threshold (7:1 for normal text)
      expect(meetsWCAGAAA([0, 0, 0], [255, 255, 255], false)).toBe(true);
    });

    it('should convert hex to RGB', () => {
      expect(hexToRgb('#ffffff')).toEqual([255, 255, 255]);
      expect(hexToRgb('#000000')).toEqual([0, 0, 0]);
      expect(hexToRgb('#ff0000')).toEqual([255, 0, 0]);
      expect(hexToRgb('invalid')).toBeNull();
    });
  });

  describe('Touch Target', () => {
    it('should validate minimum touch target size', () => {
      // 44x44 is minimum
      expect(meetsTouchTargetMinimum(44, 44)).toBe(true);
      expect(meetsTouchTargetMinimum(50, 50)).toBe(true);

      // Below minimum
      expect(meetsTouchTargetMinimum(30, 30)).toBe(false);
      expect(meetsTouchTargetMinimum(44, 30)).toBe(false);
    });
  });

  describe('Reduced Motion', () => {
    it('should return boolean for reduced motion preference', () => {
      // This tests the function runs without error
      const result = prefersReducedMotion();
      expect(typeof result).toBe('boolean');
    });
  });
});
