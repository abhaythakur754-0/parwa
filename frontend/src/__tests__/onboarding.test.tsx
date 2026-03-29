import * as React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import {
  OnboardingWizard,
  type OnboardingData,
} from "@/components/onboarding/OnboardingWizard";

// Mock next/navigation
const mockPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: jest.fn(),
    back: jest.fn(),
  }),
}));

describe("OnboardingWizard", () => {
  const mockOnComplete = jest.fn();

  beforeEach(() => {
    mockOnComplete.mockClear();
    mockPush.mockClear();
  });

  it("renders with step indicator", () => {
    render(<OnboardingWizard onComplete={mockOnComplete} />);

    // Check step numbers are displayed
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("shows progress bar", () => {
    render(<OnboardingWizard onComplete={mockOnComplete} />);

    // Progress bar should be visible
    const progressBar = document.querySelector('[class*="bg-primary"][class*="h-full"]');
    expect(progressBar).toBeInTheDocument();
  });

  it("starts at step 1 by default", () => {
    render(<OnboardingWizard onComplete={mockOnComplete} />);

    // Company step should be visible
    expect(screen.getByLabelText(/company name/i)).toBeInTheDocument();
  });

  it("can start at a different step", () => {
    render(<OnboardingWizard onComplete={mockOnComplete} initialStep={2} />);

    // Step 2 title should be visible (Choose your plan)
    expect(screen.getByText("Choose your plan")).toBeInTheDocument();
  });

  it("navigates to next step with Continue button", async () => {
    render(<OnboardingWizard onComplete={mockOnComplete} />);

    // Fill step 1
    fireEvent.change(screen.getByLabelText(/company name/i), {
      target: { value: "Test Company" },
    });

    // Click Continue
    const continueButton = screen.getByRole("button", { name: /continue/i });
    fireEvent.click(continueButton);

    // Should advance to step 2
    await waitFor(() => {
      expect(screen.getByText("Choose your plan")).toBeInTheDocument();
    });
  });

  it("navigates back with Back button", async () => {
    render(<OnboardingWizard onComplete={mockOnComplete} initialStep={2} />);

    // Click Back
    const backButton = screen.getByRole("button", { name: /back/i });
    fireEvent.click(backButton);

    // Should go back to step 1
    await waitFor(() => {
      expect(screen.getByLabelText(/company name/i)).toBeInTheDocument();
    });
  });

  it("disables Back button on first step", () => {
    render(<OnboardingWizard onComplete={mockOnComplete} initialStep={1} />);

    const backButton = screen.getByRole("button", { name: /back/i });
    expect(backButton).toBeDisabled();
  });

  it("shows step descriptions on desktop", () => {
    render(<OnboardingWizard onComplete={mockOnComplete} />);

    expect(screen.getByText("Tell us about your business")).toBeInTheDocument();
  });
});

describe("Step 1 - Company", () => {
  it("has all required form fields", () => {
    render(<OnboardingWizard />);

    expect(screen.getByLabelText(/company name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^industry/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/company size/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/website/i)).toBeInTheDocument();
  });

  it("has industry dropdown with options", () => {
    render(<OnboardingWizard />);

    const industrySelect = screen.getByLabelText(/^industry/i);
    fireEvent.click(industrySelect);

    // Should have options
    expect(screen.getByText("E-commerce")).toBeInTheDocument();
    expect(screen.getByText("SaaS")).toBeInTheDocument();
    expect(screen.getByText("Healthcare")).toBeInTheDocument();
  });

  it("has company size dropdown with options", () => {
    render(<OnboardingWizard />);

    const sizeSelect = screen.getByLabelText(/company size/i);
    fireEvent.click(sizeSelect);

    // Should have options
    expect(screen.getByText("1-10 employees")).toBeInTheDocument();
    expect(screen.getByText("11-50 employees")).toBeInTheDocument();
  });
});

describe("Step 2 - Variant Selection", () => {
  it("displays all three variants", () => {
    render(<OnboardingWizard initialStep={2} />);

    expect(screen.getByText("Mini PARWA")).toBeInTheDocument();
    expect(screen.getByText("PARWA Junior")).toBeInTheDocument();
    expect(screen.getByText("PARWA High")).toBeInTheDocument();
  });

  it("shows pricing for each variant", () => {
    render(<OnboardingWizard initialStep={2} />);

    expect(screen.getByText(/\$999/)).toBeInTheDocument();
    expect(screen.getByText(/\$2,499/)).toBeInTheDocument();
    expect(screen.getByText(/\$3,999/)).toBeInTheDocument();
  });

  it("shows tier badges", () => {
    render(<OnboardingWizard initialStep={2} />);

    expect(screen.getByText("Light")).toBeInTheDocument();
    expect(screen.getByText("Medium")).toBeInTheDocument();
    expect(screen.getByText("Heavy")).toBeInTheDocument();
  });

  it("highlights selected variant", () => {
    render(<OnboardingWizard initialStep={2} />);

    // Click on Mini PARWA
    const miniCard = screen.getByText("Mini PARWA").closest("div");
    fireEvent.click(miniCard!);

    // Should have selection styling
    expect(miniCard).toHaveClass("border-primary");
  });

  it("shows 'Most Popular' badge on recommended variant", () => {
    render(<OnboardingWizard initialStep={2} />);

    expect(screen.getByText(/most popular/i)).toBeInTheDocument();
  });
});

describe("Step 3 - Integrations", () => {
  it("displays all integrations", () => {
    render(<OnboardingWizard initialStep={3} />);

    expect(screen.getByText("Shopify")).toBeInTheDocument();
    expect(screen.getByText("Zendesk")).toBeInTheDocument();
    expect(screen.getByText("Twilio")).toBeInTheDocument();
    expect(screen.getByText("Email Provider")).toBeInTheDocument();
  });

  it("has Connect buttons for each integration", () => {
    render(<OnboardingWizard initialStep={3} />);

    const connectButtons = screen.getAllByRole("button", { name: /connect/i });
    expect(connectButtons).toHaveLength(4);
  });

  it("toggles integration state on connect", async () => {
    render(<OnboardingWizard initialStep={3} />);

    const connectButtons = screen.getAllByRole("button", { name: /connect/i });
    fireEvent.click(connectButtons[0]);

    // Should show "Connected" after clicking
    await waitFor(() => {
      expect(screen.getByText("Connected")).toBeInTheDocument();
    });
  });

  it("shows skip message", () => {
    render(<OnboardingWizard initialStep={3} />);

    expect(screen.getByText(/skip this step/i)).toBeInTheDocument();
  });
});

describe("Step 4 - Team", () => {
  it("shows Add Team Member button", () => {
    render(<OnboardingWizard initialStep={4} />);

    expect(screen.getByRole("button", { name: /add team member/i })).toBeInTheDocument();
  });

  it("adds team member fields when clicking Add", () => {
    render(<OnboardingWizard initialStep={4} />);

    const addButton = screen.getByRole("button", { name: /add team member/i });
    fireEvent.click(addButton);

    // Should show email input
    expect(screen.getByPlaceholderText(/colleague@example.com/i)).toBeInTheDocument();
  });

  it("shows role dropdown for team members", () => {
    render(<OnboardingWizard initialStep={4} />);

    // Add a team member
    const addButton = screen.getByRole("button", { name: /add team member/i });
    fireEvent.click(addButton);

    // Role select should be present
    const roleSelect = document.querySelector("select");
    expect(roleSelect).toBeInTheDocument();
  });

  it("limits team members to 5", () => {
    render(<OnboardingWizard initialStep={4} />);

    const addButton = screen.getByRole("button", { name: /add team member/i });

    // Add 5 members
    for (let i = 0; i < 5; i++) {
      fireEvent.click(addButton);
    }

    // Button should no longer be available
    expect(screen.getByText(/maximum/i)).toBeInTheDocument();
  });

  it("can remove team members", () => {
    render(<OnboardingWizard initialStep={4} />);

    // Add a team member
    const addButton = screen.getByRole("button", { name: /add team member/i });
    fireEvent.click(addButton);

    // Remove button should be present
    const removeButton = screen.getByRole("button", { name: /remove team member/i });
    expect(removeButton).toBeInTheDocument();
  });
});

describe("Step 5 - Complete", () => {
  it("shows success message", () => {
    render(<OnboardingWizard initialStep={5} />);

    expect(screen.getByText(/you're all set/i)).toBeInTheDocument();
  });

  it("shows Go to Dashboard button", () => {
    render(<OnboardingWizard initialStep={5} />);

    expect(screen.getByRole("button", { name: /go to dashboard/i })).toBeInTheDocument();
  });

  it("shows summary card", () => {
    render(<OnboardingWizard initialStep={5} />);

    expect(screen.getByText(/setup summary/i)).toBeInTheDocument();
  });

  it("shows tutorial link", () => {
    render(<OnboardingWizard initialStep={5} />);

    expect(screen.getByText(/start the tutorial/i)).toBeInTheDocument();
  });

  it("calls onComplete when clicking Go to Dashboard", async () => {
    render(<OnboardingWizard onComplete={mockOnComplete} initialStep={5} />);

    const dashboardButton = screen.getByRole("button", { name: /go to dashboard/i });
    fireEvent.click(dashboardButton);

    await waitFor(() => {
      expect(mockOnComplete).toHaveBeenCalled();
    }, { timeout: 3000 });
  });

  it("shows loading state when submitting", async () => {
    render(<OnboardingWizard onComplete={mockOnComplete} initialStep={5} />);

    const dashboardButton = screen.getByRole("button", { name: /go to dashboard/i });
    fireEvent.click(dashboardButton);

    await waitFor(() => {
      expect(screen.getByText(/setting up/i)).toBeInTheDocument();
    });
  });
});

describe("Complete Onboarding Flow", () => {
  it("completes full 5-step flow", async () => {
    render(<OnboardingWizard onComplete={mockOnComplete} />);

    // Step 1: Company Info
    fireEvent.change(screen.getByLabelText(/company name/i), {
      target: { value: "Acme Corp" },
    });
    fireEvent.click(screen.getByRole("button", { name: /continue/i }));

    // Step 2: Variant Selection
    await waitFor(() => {
      expect(screen.getByText("Mini PARWA")).toBeInTheDocument();
    });
    const miniCard = screen.getByText("Mini PARWA").closest("div");
    fireEvent.click(miniCard!);
    fireEvent.click(screen.getByRole("button", { name: /continue/i }));

    // Step 3: Integrations (skip)
    await waitFor(() => {
      expect(screen.getByText("Shopify")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: /continue/i }));

    // Step 4: Team (skip)
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /add team member/i })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: /complete setup/i }));

    // Step 5: Complete
    await waitFor(() => {
      expect(screen.getByText(/you're all set/i)).toBeInTheDocument();
    });
  });
});
