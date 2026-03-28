# Accessibility (A11y) Guide

This guide outlines PARWA's accessibility standards and implementation patterns to ensure WCAG 2.1 AA compliance across all components.

## Overview

PARWA is committed to providing an accessible experience for all users, including those using assistive technologies. Our goal is **100% WCAG 2.1 AA compliance**.

## WCAG 2.1 AA Requirements

### Perceivable

1. **Text Alternatives** (1.1.1)
   - All images must have meaningful `alt` text
   - Decorative images use `alt=""` or `role="presentation"`
   - Complex images have extended descriptions

2. **Time-based Media** (1.2.1 - 1.2.5)
   - Video content has captions
   - Audio content has transcripts
   - Live content has real-time captions

3. **Adaptable** (1.3.1 - 1.3.6)
   - Content is programmatically determinable
   - Meaningful sequence is preserved
   - Instructions don't rely solely on sensory characteristics
   - Orientation is not restricted
   - Input modality is flexible

4. **Distinguishable** (1.4.1 - 1.4.12)
   - Color is not the only visual indicator
   - Audio control is available
   - Text can be resized to 200%
   - Images of text are avoided
   - Reflow at 320px width
   - Contrast ratio: 4.5:1 (normal text), 3:1 (large text)
   - Spacing requirements met
   - Content on hover/focus is dismissible
   - Pointer gestures have alternatives
   - Motion can be disabled

### Operable

1. **Keyboard Accessible** (2.1.1 - 2.1.4)
   - All functionality available via keyboard
   - No keyboard traps
   - No keyboard shortcuts that conflict with assistive tech
   - Character key shortcuts can be turned off

2. **Enough Time** (2.2.1 - 2.2.2)
   - Time limits are adjustable
   - Moving content can be paused

3. **Seizures** (2.3.1 - 2.3.3)
   - No more than 3 flashes per second
   - Animation from interactions can be disabled

4. **Navigable** (2.4.1 - 2.4.11)
   - Skip links provided
   - Pages have descriptive titles
   - Focus order is logical
   - Link purpose is clear
   - Multiple navigation methods available
   - Focus is visible
   - Current location is indicated
   - Consistent navigation
   - Consistent identification
   - Focus not obscured (minimized)

5. **Input Modalities** (2.5.1 - 2.5.8)
   - Touch targets minimum 44x44px
   - Pointer cancellation available
   - Label in name matches visible label
   - Motion-activated functions have alternatives
   - Target size minimum for touch
   - Concurrent input mechanisms supported

### Understandable

1. **Readable** (3.1.1 - 3.1.2)
   - Page language is declared
   - Language of parts is identified

2. **Predictable** (3.2.1 - 3.2.6)
   - Focus doesn't trigger context change
   - Input doesn't trigger unexpected change
   - Consistent navigation
   - Consistent identification
   - Help available
   - Error prevention for legal/financial actions

3. **Input Assistance** (3.3.1 - 3.3.4)
   - Error identification
   - Labels and instructions
   - Error suggestion
   - Error prevention for important actions

### Robust

1. **Compatible** (4.1.1 - 4.1.3)
   - Valid HTML parsing
   - Name, role, value for UI components
   - Status messages announced

## Component Patterns

### Skip Links

Every page must have a skip link as the first focusable element:

```tsx
<SkipLink targetId="main-content" label="Skip to main content" />
```

### Focus Management

Use FocusTrap for modals and dialogs:

```tsx
<FocusTrap active={isOpen} onEscape={handleClose}>
  <Dialog>...</Dialog>
</FocusTrap>
```

### Color Contrast

Test with our contrast utilities:

```tsx
import { meetsWCAGAA, hexToRgb } from '@/lib/a11y';

const foreground = hexToRgb('#000000');
const background = hexToRgb('#ffffff');

if (meetsWCAGAA(foreground!, background!)) {
  // Contrast is WCAG AA compliant
}
```

### Touch Targets

Ensure all interactive elements are at least 44x44px:

```css
.button {
  min-width: 44px;
  min-height: 44px;
  padding: 12px;
}
```

### Screen Reader Announcements

Announce dynamic content changes:

```tsx
import { announceToScreenReader } from '@/lib/a11y';

announceToScreenReader('Form submitted successfully', 'polite');
```

## Testing

### Automated Testing

Run axe-core accessibility tests:

```bash
npm run test:a11y
```

### Manual Testing Checklist

- [ ] Navigate entire page with keyboard only
- [ ] Test with screen reader (VoiceOver, NVDA, JAWS)
- [ ] Verify color contrast with WebAIM Contrast Checker
- [ ] Test at 200% zoom
- [ ] Test with high contrast mode
- [ ] Test with reduced motion preference
- [ ] Verify focus order is logical
- [ ] Check all images have appropriate alt text

### Browser Extensions

- axe DevTools
- WAVE
- Lighthouse (Accessibility audit)
- ColorZilla (color contrast)

## Common Patterns

### Buttons vs Links

- **Buttons**: Actions (submit, open modal, toggle)
- **Links**: Navigation (go to different page/section)

```tsx
// Correct
<Button onClick={handleSubmit}>Submit</Button>
<Link href="/dashboard">Go to Dashboard</Link>

// Incorrect
<div onClick={handleSubmit}>Submit</div>
<span onClick={navigate}>Go to Dashboard</span>
```

### Form Labels

Always associate labels with inputs:

```tsx
// Correct
<Label htmlFor="email">Email</Label>
<Input id="email" type="email" />

// Also correct
<Input aria-label="Email address" type="email" />
```

### Icons

Provide accessible names for icon-only buttons:

```tsx
<Button aria-label="Close dialog">
  <XIcon />
</Button>
```

### Dynamic Content

Use ARIA live regions for dynamic updates:

```tsx
<div role="status" aria-live="polite">
  {statusMessage}
</div>
```

### Tables

Use semantic table markup:

```tsx
<table>
  <caption>Monthly Sales Report</caption>
  <thead>
    <tr>
      <th scope="col">Month</th>
      <th scope="col">Revenue</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th scope="row">January</th>
      <td>$10,000</td>
    </tr>
  </tbody>
</table>
```

## Resources

- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [WebAIM](https://webaim.org/)
- [MDN Accessibility](https://developer.mozilla.org/en-US/docs/Web/Accessibility)
- [A11y Project](https://www.a11yproject.com/)
- [Inclusive Components](https://inclusive-components.design/)

## Violation Remediation

| Violation | Priority | Remediation |
|-----------|----------|-------------|
| Missing alt text | High | Add descriptive alt text |
| Color contrast < 4.5:1 | High | Adjust colors |
| Missing form labels | High | Add associated labels |
| Keyboard trap | Critical | Fix focus management |
| Missing skip link | Medium | Add skip link |
| Missing ARIA roles | Medium | Add appropriate roles |
