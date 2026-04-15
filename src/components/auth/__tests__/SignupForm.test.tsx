import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SignupForm } from '../SignupForm';

// Mock next/link
jest.mock('next/link', () => {
  const MockLink = ({ children, href }: { children: React.ReactNode; href: string }) => {
    return <a href={href}>{children}</a>;
  };
  MockLink.displayName = 'MockLink';
  return MockLink;
});

describe('SignupForm', () => {
  const mockOnSubmit = jest.fn();
  const mockOnCheckEmail = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    mockOnCheckEmail.mockResolvedValue(true);
  });

  const validFormData = {
    email: 'test@example.com',
    password: 'Password123!',
    full_name: 'John Doe',
    company_name: 'Acme Inc.',
    industry: 'saas',
  };

  it('should render all form fields', () => {
    render(<SignupForm onSubmit={mockOnSubmit} />);

    // Check for all required fields
    expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/full name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/company name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/industry/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();

    // Check for submit button
    expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument();

    // Check for sign in link
    expect(screen.getByText(/already have an account\?/i)).toBeInTheDocument();
  });

  it('should render industry dropdown with options', () => {
    render(<SignupForm onSubmit={mockOnSubmit} />);

    const industrySelect = screen.getByLabelText(/industry/i);
    
    // Check for some industry options
    expect(screen.getByRole('option', { name: /select your industry/i })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /e-commerce/i })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /saas/i })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /other/i })).toBeInTheDocument();
  });

  it('should show password strength meter when typing password', async () => {
    render(<SignupForm onSubmit={mockOnSubmit} />);

    const passwordInput = screen.getByLabelText(/^password$/i);
    
    // Type a password to trigger strength meter
    await userEvent.type(passwordInput, 'Password123!');

    // Check for strength indicator
    await waitFor(() => {
      // The strength text should appear (Strong or Very Strong)
      const strengthText = screen.queryByText(/strong|fair|weak/i);
      expect(strengthText).toBeInTheDocument();
    });
  });

  it('should call onSubmit with valid data', async () => {
    mockOnSubmit.mockResolvedValueOnce(undefined);
    render(<SignupForm onSubmit={mockOnSubmit} />);

    // Fill out the form
    await userEvent.type(screen.getByLabelText(/email address/i), validFormData.email);
    await userEvent.type(screen.getByLabelText(/full name/i), validFormData.full_name);
    await userEvent.type(screen.getByLabelText(/company name/i), validFormData.company_name);
    await userEvent.selectOptions(screen.getByLabelText(/industry/i), validFormData.industry);
    await userEvent.type(screen.getByLabelText(/^password$/i), validFormData.password);
    await userEvent.type(screen.getByLabelText(/confirm password/i), validFormData.password);

    const submitButton = screen.getByRole('button', { name: /create account/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith(validFormData);
    });
  });

  it('should display error message when error prop is provided', () => {
    const errorMessage = 'Registration failed';
    render(<SignupForm onSubmit={mockOnSubmit} error={errorMessage} />);

    expect(screen.getByText(errorMessage)).toBeInTheDocument();
  });

  it('should disable all fields when loading', () => {
    render(<SignupForm onSubmit={mockOnSubmit} isLoading={true} />);

    expect(screen.getByLabelText(/email address/i)).toBeDisabled();
    expect(screen.getByLabelText(/full name/i)).toBeDisabled();
    expect(screen.getByLabelText(/company name/i)).toBeDisabled();
    expect(screen.getByLabelText(/industry/i)).toBeDisabled();
    expect(screen.getByLabelText(/^password$/i)).toBeDisabled();
    expect(screen.getByLabelText(/confirm password/i)).toBeDisabled();
    expect(screen.getByRole('button', { name: /creating account/i })).toBeDisabled();
  });

  it('should have correct form attributes', () => {
    render(<SignupForm onSubmit={mockOnSubmit} />);

    const emailInput = screen.getByLabelText(/email address/i);
    const passwordInput = screen.getByLabelText(/^password$/i);

    expect(emailInput).toHaveAttribute('type', 'email');
    expect(emailInput).toHaveAttribute('required');
    expect(emailInput).toHaveAttribute('autoComplete', 'email');

    expect(passwordInput).toHaveAttribute('type', 'password');
    expect(passwordInput).toHaveAttribute('required');
    expect(passwordInput).toHaveAttribute('autoComplete', 'new-password');
  });
});
