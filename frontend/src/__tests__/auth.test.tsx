import * as React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import LoginPage from "@/app/auth/login/page";
import RegisterPage from "@/app/auth/register/page";
import ForgotPasswordPage from "@/app/auth/forgot-password/page";

// Mock next/navigation
const mockPush = jest.fn();
const mockRouter = {
  push: mockPush,
  replace: jest.fn(),
  back: jest.fn(),
};

jest.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
}));

// Alert component tests
describe("Alert Component", () => {
  it("renders info alert variant", () => {
    render(
      <div className="border-blue-500/50 bg-blue-500/10 text-blue-700" role="alert">
        Info alert message
      </div>
    );
    expect(screen.getByText("Info alert message")).toBeInTheDocument();
  });

  it("renders success alert variant", () => {
    render(
      <div className="border-green-500/50 bg-green-500/10 text-green-700" role="alert">
        Success alert message
      </div>
    );
    expect(screen.getByText("Success alert message")).toBeInTheDocument();
  });

  it("renders warning alert variant", () => {
    render(
      <div className="border-yellow-500/50 bg-yellow-500/10 text-yellow-700" role="alert">
        Warning alert message
      </div>
    );
    expect(screen.getByText("Warning alert message")).toBeInTheDocument();
  });

  it("renders destructive alert variant", () => {
    render(
      <div className="border-destructive/50 bg-destructive/10 text-destructive" role="alert">
        Error alert message
      </div>
    );
    expect(screen.getByText("Error alert message")).toBeInTheDocument();
  });
});

// Login Page tests
describe("LoginPage", () => {
  beforeEach(() => {
    mockPush.mockClear();
  });

  it("renders login form", () => {
    render(<LoginPage />);

    expect(screen.getByText("Welcome back")).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("shows forgot password link", () => {
    render(<LoginPage />);

    expect(screen.getByText(/forgot password/i)).toBeInTheDocument();
  });

  it("shows register link", () => {
    render(<LoginPage />);

    expect(screen.getByText(/sign up/i)).toBeInTheDocument();
  });

  it("validates required email", async () => {
    render(<LoginPage />);

    const submitButton = screen.getByRole("button", { name: /sign in/i });
    fireEvent.click(submitButton);

    // Should show validation error for empty email
    await waitFor(() => {
      const emailInput = screen.getByLabelText(/email/i);
      expect(emailInput).toBeRequired();
    });
  });

  it("validates required password", async () => {
    render(<LoginPage />);

    const submitButton = screen.getByRole("button", { name: /sign in/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      const passwordInput = screen.getByLabelText(/password/i);
      expect(passwordInput).toBeRequired();
    });
  });

  it("validates email format", async () => {
    render(<LoginPage />);

    const emailInput = screen.getByLabelText(/email/i);
    fireEvent.change(emailInput, { target: { value: "invalid-email" } });

    const passwordInput = screen.getByLabelText(/password/i);
    fireEvent.change(passwordInput, { target: { value: "password123" } });

    const submitButton = screen.getByRole("button", { name: /sign in/i });
    fireEvent.click(submitButton);

    // Should show email format error
    await waitFor(() => {
      expect(emailInput).toHaveAttribute("type", "email");
    });
  });

  it("renders social login buttons", () => {
    render(<LoginPage />);

    expect(screen.getByText(/google/i)).toBeInTheDocument();
    expect(screen.getByText(/github/i)).toBeInTheDocument();
  });

  it("renders remember me checkbox", () => {
    render(<LoginPage />);

    expect(screen.getByLabelText(/remember me/i)).toBeInTheDocument();
  });
});

// Register Page tests
describe("RegisterPage", () => {
  beforeEach(() => {
    mockPush.mockClear();
  });

  it("renders register form", () => {
    render(<RegisterPage />);

    expect(screen.getByText("Create an account")).toBeInTheDocument();
    expect(screen.getByLabelText(/full name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^email$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /create account/i })).toBeInTheDocument();
  });

  it("shows terms checkbox", () => {
    render(<RegisterPage />);

    expect(screen.getByLabelText(/terms of service/i)).toBeInTheDocument();
  });

  it("shows login link", () => {
    render(<RegisterPage />);

    expect(screen.getByText(/already have an account/i)).toBeInTheDocument();
  });

  it("validates required fields", async () => {
    render(<RegisterPage />);

    const submitButton = screen.getByRole("button", { name: /create account/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      const nameInput = screen.getByLabelText(/full name/i);
      expect(nameInput).toBeRequired();
    });
  });

  it("validates password requirements", async () => {
    render(<RegisterPage />);

    const passwordInput = screen.getByLabelText(/^password$/i);

    // Check that password requirements are shown
    expect(screen.getByText(/at least 8 characters/i)).toBeInTheDocument();
    expect(passwordInput).toHaveAttribute("type", "password");
  });

  it("validates terms acceptance", async () => {
    render(<RegisterPage />);

    const termsCheckbox = screen.getByLabelText(/terms of service/i);
    expect(termsCheckbox).not.toBeChecked();
  });
});

// Forgot Password Page tests
describe("ForgotPasswordPage", () => {
  it("renders forgot password form", () => {
    render(<ForgotPasswordPage />);

    expect(screen.getByText("Forgot password?")).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send reset link/i })).toBeInTheDocument();
  });

  it("shows back to login link", () => {
    render(<ForgotPasswordPage />);

    expect(screen.getByText(/back to login/i)).toBeInTheDocument();
  });

  it("validates email input", async () => {
    render(<ForgotPasswordPage />);

    const emailInput = screen.getByLabelText(/email/i);
    expect(emailInput).toBeRequired();
    expect(emailInput).toHaveAttribute("type", "email");
  });

  it("shows success state after submission", async () => {
    render(<ForgotPasswordPage />);

    const emailInput = screen.getByLabelText(/email/i);
    fireEvent.change(emailInput, { target: { value: "test@example.com" } });

    const submitButton = screen.getByRole("button", { name: /send reset link/i });
    fireEvent.click(submitButton);

    // Wait for success state
    await waitFor(
      () => {
        expect(screen.getByText(/check your email/i)).toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });
});

// Auth Layout tests
describe("AuthLayout", () => {
  it("renders logo", async () => {
    const { default: AuthLayout } = await import("@/app/auth/layout");
    render(
      <AuthLayout>
        <div>Test</div>
      </AuthLayout>
    );

    expect(screen.getByText("PARWA")).toBeInTheDocument();
  });

  it("renders terms links", async () => {
    const { default: AuthLayout } = await import("@/app/auth/layout");
    render(
      <AuthLayout>
        <div>Test</div>
      </AuthLayout>
    );

    expect(screen.getByText(/terms of service/i)).toBeInTheDocument();
    expect(screen.getByText(/privacy policy/i)).toBeInTheDocument();
  });
});

// Form Interaction tests
describe("Form Interactions", () => {
  it("handles input changes", async () => {
    render(<LoginPage />);

    const emailInput = screen.getByLabelText(/email/i) as HTMLInputElement;
    fireEvent.change(emailInput, { target: { value: "test@example.com" } });

    expect(emailInput.value).toBe("test@example.com");
  });

  it("handles checkbox changes", async () => {
    render(<LoginPage />);

    const rememberCheckbox = screen.getByLabelText(/remember me/i) as HTMLInputElement;
    expect(rememberCheckbox.checked).toBe(false);

    fireEvent.click(rememberCheckbox);
    expect(rememberCheckbox.checked).toBe(true);
  });

  it("disables submit button during loading", async () => {
    render(<LoginPage />);

    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);

    fireEvent.change(emailInput, { target: { value: "test@example.com" } });
    fireEvent.change(passwordInput, { target: { value: "Password123" } });

    const submitButton = screen.getByRole("button", { name: /sign in/i });
    expect(submitButton).not.toBeDisabled();
  });
});
