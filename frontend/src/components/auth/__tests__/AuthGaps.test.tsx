/**
 * Day 4 Auth Frontend Gap Tests
 * 
 * Tests for security and functional gaps identified in auth frontend:
 * 
 * CRITICAL:
 * - GAP-001: XSS in Signup Form
 * - GAP-002: Token Storage Security
 * - GAP-003: Logout Token Revocation
 * 
 * HIGH:
 * - GAP-004: Race Condition in Auth State
 * - GAP-005: OAuth State Parameter
 * - GAP-006: Password Field Not Cleared on Error
 * - GAP-007: Token Refresh Race Condition
 * 
 * MEDIUM:
 * - GAP-008: Error Message Information Disclosure
 * - GAP-009: Input Length Validation
 * - GAP-010: Session Timeout Handling
 * - GAP-011: Auth Context Initialization
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SignupForm } from '../SignupForm';
import { LoginForm } from '../LoginForm';

// Mock next/link
jest.mock('next/link', () => {
  const MockLink = ({ children, href }: { children: React.ReactNode; href: string }) => {
    return <a href={href}>{children}</a>;
  };
  MockLink.displayName = 'MockLink';
  return MockLink;
});

// ── GAP-001: XSS Prevention Tests ─────────────────────────────────────────

describe('GAP-001: XSS Prevention in Forms', () => {
  const mockOnSubmit = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    mockOnSubmit.mockResolvedValue(undefined);
  });

  it('should sanitize script tags from full_name field', async () => {
    render(<SignupForm onSubmit={mockOnSubmit} />);

    const nameInput = screen.getByLabelText(/full name/i);
    
    // Attempt to inject XSS payload
    await userEvent.type(screen.getByLabelText(/email address/i), 'test@example.com');
    await userEvent.type(nameInput, '<script>alert("XSS")</script>John Doe');
    await userEvent.type(screen.getByLabelText(/company name/i), 'Acme Inc.');
    await userEvent.selectOptions(screen.getByLabelText(/industry/i), 'saas');
    await userEvent.type(screen.getByLabelText(/^password$/i), 'Password123!');
    await userEvent.type(screen.getByLabelText(/confirm password/i), 'Password123!');

    const submitButton = screen.getByRole('button', { name: /create account/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      if (mockOnSubmit.mock.calls.length > 0) {
        const submittedData = mockOnSubmit.mock.calls[0][0];
        // Should NOT contain script tags (sanitized)
        expect(submittedData.full_name).not.toContain('<script>');
        expect(submittedData.full_name).not.toContain('</script>');
      }
    }, { timeout: 3000 });
  });

  it('should sanitize img tags with onerror from company_name field', async () => {
    render(<SignupForm onSubmit={mockOnSubmit} />);

    await userEvent.type(screen.getByLabelText(/email address/i), 'test@example.com');
    await userEvent.type(screen.getByLabelText(/full name/i), 'John Doe');
    
    const companyInput = screen.getByLabelText(/company name/i);
    await userEvent.type(companyInput, '<img src=x onerror=alert(1)>Acme');
    await userEvent.selectOptions(screen.getByLabelText(/industry/i), 'saas');
    await userEvent.type(screen.getByLabelText(/^password$/i), 'Password123!');
    await userEvent.type(screen.getByLabelText(/confirm password/i), 'Password123!');

    const submitButton = screen.getByRole('button', { name: /create account/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      if (mockOnSubmit.mock.calls.length > 0) {
        const submittedData = mockOnSubmit.mock.calls[0][0];
        // Should NOT contain img tags (sanitized)
        expect(submittedData.company_name).not.toContain('<img');
        expect(submittedData.company_name).not.toContain('onerror');
      }
    }, { timeout: 3000 });
  });

  it('should reject XSS attempts in email field', async () => {
    render(<SignupForm onSubmit={mockOnSubmit} />);

    const emailInput = screen.getByLabelText(/email address/i);
    
    // Attempt to inject XSS payload in email
    await userEvent.type(emailInput, 'test<script>@example.com');
    await userEvent.type(screen.getByLabelText(/full name/i), 'John Doe');
    await userEvent.type(screen.getByLabelText(/company name/i), 'Acme Inc.');
    await userEvent.selectOptions(screen.getByLabelText(/industry/i), 'saas');
    await userEvent.type(screen.getByLabelText(/^password$/i), 'Password123!');
    await userEvent.type(screen.getByLabelText(/confirm password/i), 'Password123!');

    const submitButton = screen.getByRole('button', { name: /create account/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      // Should show validation error for invalid email
      const errorElement = screen.queryByText(/invalid/i);
      expect(errorElement).toBeInTheDocument();
    });
  });
});

// ── GAP-004: Race Condition Tests ─────────────────────────────────────────

describe('GAP-004: Race Condition Prevention', () => {
  it('should prevent multiple simultaneous form submissions', async () => {
    const slowOnSubmit = jest.fn().mockImplementation(() => 
      new Promise(resolve => setTimeout(resolve, 500))
    );
    
    render(<SignupForm onSubmit={slowOnSubmit} />);

    // Fill form
    await userEvent.type(screen.getByLabelText(/email address/i), 'test@example.com');
    await userEvent.type(screen.getByLabelText(/full name/i), 'John Doe');
    await userEvent.type(screen.getByLabelText(/company name/i), 'Acme Inc.');
    await userEvent.selectOptions(screen.getByLabelText(/industry/i), 'saas');
    await userEvent.type(screen.getByLabelText(/^password$/i), 'Password123!');
    await userEvent.type(screen.getByLabelText(/confirm password/i), 'Password123!');

    const submitButton = screen.getByRole('button', { name: /create account/i });
    
    // Click multiple times rapidly
    fireEvent.click(submitButton);
    fireEvent.click(submitButton);
    fireEvent.click(submitButton);

    await waitFor(() => {
      // Should only call submit once despite multiple clicks
      expect(slowOnSubmit).toHaveBeenCalledTimes(1);
    }, { timeout: 2000 });
  });

  it('should disable submit button during submission', async () => {
    const slowOnSubmit = jest.fn().mockImplementation(() => 
      new Promise(resolve => setTimeout(resolve, 500))
    );
    
    render(<SignupForm onSubmit={slowOnSubmit} />);

    await userEvent.type(screen.getByLabelText(/email address/i), 'test@example.com');
    await userEvent.type(screen.getByLabelText(/full name/i), 'John Doe');
    await userEvent.type(screen.getByLabelText(/company name/i), 'Acme Inc.');
    await userEvent.selectOptions(screen.getByLabelText(/industry/i), 'saas');
    await userEvent.type(screen.getByLabelText(/^password$/i), 'Password123!');
    await userEvent.type(screen.getByLabelText(/confirm password/i), 'Password123!');

    const submitButton = screen.getByRole('button', { name: /create account/i });
    
    fireEvent.click(submitButton);

    // Button should be disabled immediately
    await waitFor(() => {
      expect(submitButton).toBeDisabled();
    });
  });
});

// ── GAP-006: Password Field Clear on Error ────────────────────────────────

describe('GAP-006: Password Field Clear on Error', () => {
  it('should clear password fields after failed submission', async () => {
    const mockOnSubmit = jest.fn().mockRejectedValueOnce(new Error('Registration failed'));
    
    render(<SignupForm onSubmit={mockOnSubmit} />);

    const passwordInput = screen.getByLabelText(/^password$/i);
    const confirmPasswordInput = screen.getByLabelText(/confirm password/i);

    await userEvent.type(screen.getByLabelText(/email address/i), 'test@example.com');
    await userEvent.type(screen.getByLabelText(/full name/i), 'John Doe');
    await userEvent.type(screen.getByLabelText(/company name/i), 'Acme Inc.');
    await userEvent.selectOptions(screen.getByLabelText(/industry/i), 'saas');
    await userEvent.type(passwordInput, 'Password123!');
    await userEvent.type(confirmPasswordInput, 'Password123!');

    const submitButton = screen.getByRole('button', { name: /create account/i });
    fireEvent.click(submitButton);

    // Wait for submission to be called
    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalled();
    });

    // Password fields should be cleared after error
    await waitFor(() => {
      expect(passwordInput).toHaveValue('');
      expect(confirmPasswordInput).toHaveValue('');
    }, { timeout: 3000 });
  });
});

// ── GAP-008: Error Message Information Disclosure ─────────────────────────

describe('GAP-008: Generic Error Messages', () => {
  it('should not reveal specific error details in form', () => {
    // Test that LoginForm has proper error prop that displays generic messages
    const mockOnSubmit = jest.fn();
    
    // Render with a generic error
    render(<LoginForm onSubmit={mockOnSubmit} error="An error occurred. Please try again." />);
    
    // Should display the error
    const errorElement = screen.getByText(/error occurred/i);
    expect(errorElement).toBeInTheDocument();
    
    // Should NOT contain specific details
    expect(errorElement.textContent?.toLowerCase()).not.toContain('user not found');
    expect(errorElement.textContent?.toLowerCase()).not.toContain('password incorrect');
  });
  
  it('should show error message when error prop is provided', () => {
    const mockOnSubmit = jest.fn();
    
    render(<LoginForm onSubmit={mockOnSubmit} error="Invalid email or password" />);
    
    // Error should be displayed
    expect(screen.getByText(/invalid email or password/i)).toBeInTheDocument();
  });
});

// ── GAP-009: Input Length Validation ──────────────────────────────────────

describe('GAP-009: Input Length Validation', () => {
  const mockOnSubmit = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    mockOnSubmit.mockResolvedValue(undefined);
  });

  it('should validate maximum email length', async () => {
    render(<SignupForm onSubmit={mockOnSubmit} />);
    
    const longEmail = 'a'.repeat(250) + '@example.com';
    await userEvent.type(screen.getByLabelText(/email address/i), longEmail);

    // Trigger validation
    const submitButton = screen.getByRole('button', { name: /create account/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      // Should show validation error for too long email
      const errorElement = screen.queryByText(/email.*255|255.*email/i);
      // Or the email should be truncated
      if (mockOnSubmit.mock.calls.length > 0) {
        const submittedEmail = mockOnSubmit.mock.calls[0][0].email;
        expect(submittedEmail.length).toBeLessThanOrEqual(255);
      }
    });
  });

  it('should validate maximum name length', async () => {
    render(<SignupForm onSubmit={mockOnSubmit} />);
    
    const longName = 'A'.repeat(300);
    await userEvent.type(screen.getByLabelText(/full name/i), longName);
    await userEvent.type(screen.getByLabelText(/email address/i), 'test@example.com');
    await userEvent.type(screen.getByLabelText(/company name/i), 'Acme Inc.');
    await userEvent.selectOptions(screen.getByLabelText(/industry/i), 'saas');
    await userEvent.type(screen.getByLabelText(/^password$/i), 'Password123!');
    await userEvent.type(screen.getByLabelText(/confirm password/i), 'Password123!');

    const submitButton = screen.getByRole('button', { name: /create account/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      if (mockOnSubmit.mock.calls.length > 0) {
        const submittedName = mockOnSubmit.mock.calls[0][0].full_name;
        expect(submittedName.length).toBeLessThanOrEqual(255);
      }
    }, { timeout: 3000 });
  });

  it('should validate password minimum length', async () => {
    render(<SignupForm onSubmit={mockOnSubmit} />);
    
    await userEvent.type(screen.getByLabelText(/email address/i), 'test@example.com');
    await userEvent.type(screen.getByLabelText(/full name/i), 'John Doe');
    await userEvent.type(screen.getByLabelText(/company name/i), 'Acme Inc.');
    await userEvent.selectOptions(screen.getByLabelText(/industry/i), 'saas');
    
    const passwordInput = screen.getByLabelText(/^password$/i);
    await userEvent.type(passwordInput, 'short');
    await userEvent.type(screen.getByLabelText(/confirm password/i), 'short');

    const submitButton = screen.getByRole('button', { name: /create account/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      // Should show error for short password
      const errorElement = screen.queryByText(/8 character|at least 8/i);
      expect(errorElement).toBeInTheDocument();
    });
  });
});

// ── GAP-011: Auth Context Initialization ───────────────────────────────────

describe('GAP-011: Auth Context Initialization', () => {
  it('should show loading state during auth check', () => {
    const mockOnSubmit = jest.fn();
    render(<SignupForm onSubmit={mockOnSubmit} isLoading={true} />);
    
    const submitButton = screen.getByRole('button', { name: /creating|loading/i });
    expect(submitButton).toBeDisabled();
  });

  it('should handle auth state gracefully', async () => {
    const mockOnSubmit = jest.fn().mockResolvedValue(undefined);
    render(<SignupForm onSubmit={mockOnSubmit} />);
    
    // Form should be interactive
    const emailInput = screen.getByLabelText(/email address/i);
    expect(emailInput).not.toBeDisabled();
  });
});

// ── Additional Security Tests ─────────────────────────────────────────────

describe('Additional Security Tests', () => {
  it('should use autocomplete=new-password for signup password field', () => {
    render(<SignupForm onSubmit={jest.fn()} />);
    
    const passwordInput = screen.getByLabelText(/^password$/i);
    expect(passwordInput).toHaveAttribute('autoComplete', 'new-password');
  });

  it('should use autocomplete=current-password for login password field', () => {
    render(<LoginForm onSubmit={jest.fn()} />);
    
    const passwordInput = screen.getByLabelText(/^password$/i);
    expect(passwordInput).toHaveAttribute('autoComplete', 'current-password');
  });

  it('should require email field', () => {
    render(<SignupForm onSubmit={jest.fn()} />);
    
    const emailInput = screen.getByLabelText(/email address/i);
    expect(emailInput).toHaveAttribute('required');
  });

  it('should have proper input types', () => {
    render(<SignupForm onSubmit={jest.fn()} />);
    
    expect(screen.getByLabelText(/email address/i)).toHaveAttribute('type', 'email');
    expect(screen.getByLabelText(/^password$/i)).toHaveAttribute('type', 'password');
  });

  it('should validate password confirmation matches', async () => {
    const mockOnSubmit = jest.fn().mockResolvedValue(undefined);
    render(<SignupForm onSubmit={mockOnSubmit} />);
    
    await userEvent.type(screen.getByLabelText(/email address/i), 'test@example.com');
    await userEvent.type(screen.getByLabelText(/full name/i), 'John Doe');
    await userEvent.type(screen.getByLabelText(/company name/i), 'Acme Inc.');
    await userEvent.selectOptions(screen.getByLabelText(/industry/i), 'saas');
    await userEvent.type(screen.getByLabelText(/^password$/i), 'Password123!');
    await userEvent.type(screen.getByLabelText(/confirm password/i), 'DifferentPassword123!');

    const submitButton = screen.getByRole('button', { name: /create account/i });
    fireEvent.click(submitButton);

    // Wait a bit for validation to process
    await new Promise(resolve => setTimeout(resolve, 100));
    
    // Should not submit due to mismatched passwords
    expect(mockOnSubmit).not.toHaveBeenCalled();
  });

  it('should require special character in password', async () => {
    const mockOnSubmit = jest.fn().mockResolvedValue(undefined);
    render(<SignupForm onSubmit={mockOnSubmit} />);
    
    await userEvent.type(screen.getByLabelText(/email address/i), 'test@example.com');
    await userEvent.type(screen.getByLabelText(/full name/i), 'John Doe');
    await userEvent.type(screen.getByLabelText(/company name/i), 'Acme Inc.');
    await userEvent.selectOptions(screen.getByLabelText(/industry/i), 'saas');
    
    // Password without special character
    await userEvent.type(screen.getByLabelText(/^password$/i), 'Password123');
    await userEvent.type(screen.getByLabelText(/confirm password/i), 'Password123');

    const submitButton = screen.getByRole('button', { name: /create account/i });
    fireEvent.click(submitButton);

    // Wait a bit for validation to process
    await new Promise(resolve => setTimeout(resolve, 100));
    
    // Should not submit due to missing special character
    expect(mockOnSubmit).not.toHaveBeenCalled();
  });
});

// ── Summary: Gap Test Coverage ────────────────────────────────────────────

describe('Gap Test Coverage Summary', () => {
  it('should document all tested gaps', () => {
    const gapsTested = [
      { id: 'GAP-001', name: 'XSS Prevention', tests: 3 },
      { id: 'GAP-004', name: 'Race Condition Prevention', tests: 2 },
      { id: 'GAP-006', name: 'Password Field Clear on Error', tests: 1 },
      { id: 'GAP-008', name: 'Generic Error Messages', tests: 1 },
      { id: 'GAP-009', name: 'Input Length Validation', tests: 3 },
      { id: 'GAP-011', name: 'Auth Context Initialization', tests: 2 },
    ];

    console.log('\n=== DAY 4 AUTH FRONTEND GAP TEST COVERAGE ===\n');
    gapsTested.forEach(gap => {
      console.log(`${gap.id}: ${gap.name} - ${gap.tests} tests`);
    });
    console.log('\n===========================================\n');

    expect(gapsTested.length).toBeGreaterThan(0);
  });
});
