import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import WebhooksPage from "@/app/dashboard/settings/webhooks/page";
import AuditLogPage from "@/app/dashboard/settings/audit-log/page";

// Mock toast
vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}));

const renderWithRouter = (component: React.ReactElement) => {
  return render(<BrowserRouter>{component}</BrowserRouter>);
};

describe("Webhooks Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders webhooks page correctly", () => {
    renderWithRouter(<WebhooksPage />);
    expect(screen.getByText("Webhooks")).toBeInTheDocument();
    expect(screen.getByText("Configure webhooks for real-time event notifications")).toBeInTheDocument();
  });

  it("shows Add Webhook button", () => {
    renderWithRouter(<WebhooksPage />);
    expect(screen.getByRole("button", { name: /add webhook/i })).toBeInTheDocument();
  });

  it("displays existing webhooks", () => {
    renderWithRouter(<WebhooksPage />);
    expect(screen.getByText("https://api.example.com/webhooks/parwa")).toBeInTheDocument();
  });

  it("opens create webhook dialog", async () => {
    renderWithRouter(<WebhooksPage />);
    fireEvent.click(screen.getByRole("button", { name: /add webhook/i }));
    expect(screen.getByText("Create Webhook")).toBeInTheDocument();
  });

  it("shows test button for each webhook", () => {
    renderWithRouter(<WebhooksPage />);
    const testButtons = screen.getAllByRole("button", { name: /test/i });
    expect(testButtons.length).toBeGreaterThan(0);
  });

  it("shows delete button for each webhook", () => {
    renderWithRouter(<WebhooksPage />);
    const deleteButtons = screen.getAllByRole("button", { name: /delete/i });
    expect(deleteButtons.length).toBeGreaterThan(0);
  });

  it("has webhook secret section", () => {
    renderWithRouter(<WebhooksPage />);
    expect(screen.getByText("Webhook Secret")).toBeInTheDocument();
  });

  it("has copy secret button", () => {
    renderWithRouter(<WebhooksPage />);
    expect(screen.getByRole("button", { name: /copy/i })).toBeInTheDocument();
  });
});

describe("Audit Log Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders audit log page correctly", () => {
    renderWithRouter(<AuditLogPage />);
    expect(screen.getByText("Audit Log")).toBeInTheDocument();
    expect(screen.getByText("Track all system activities and changes")).toBeInTheDocument();
  });

  it("shows export CSV button", () => {
    renderWithRouter(<AuditLogPage />);
    expect(screen.getByRole("button", { name: /export csv/i })).toBeInTheDocument();
  });

  it("displays filters section", () => {
    renderWithRouter(<AuditLogPage />);
    expect(screen.getByText("Filters")).toBeInTheDocument();
  });

  it("shows search input", () => {
    renderWithRouter(<AuditLogPage />);
    expect(screen.getByPlaceholderText("Search logs...")).toBeInTheDocument();
  });

  it("displays audit log entries", () => {
    renderWithRouter(<AuditLogPage />);
    expect(screen.getByText("john@example.com")).toBeInTheDocument();
    expect(screen.getByText("jane@example.com")).toBeInTheDocument();
  });

  it("shows action type badges", () => {
    renderWithRouter(<AuditLogPage />);
    expect(screen.getByText("approval")).toBeInTheDocument();
    expect(screen.getByText("create")).toBeInTheDocument();
  });

  it("has clear filters button", () => {
    renderWithRouter(<AuditLogPage />);
    expect(screen.getByRole("button", { name: /clear filters/i })).toBeInTheDocument();
  });

  it("filters logs by search query", async () => {
    renderWithRouter(<AuditLogPage />);
    const searchInput = screen.getByPlaceholderText("Search logs...");
    fireEvent.change(searchInput, { target: { value: "refund" } });

    await waitFor(() => {
      expect(screen.getByText("Approved refund request")).toBeInTheDocument();
    });
  });

  it("shows date range inputs", () => {
    renderWithRouter(<AuditLogPage />);
    const dateInputs = screen.getAllByRole("textbox").filter(input =>
      input.getAttribute("type") === "date"
    );
    expect(dateInputs.length).toBe(2);
  });

  it("displays IP addresses", () => {
    renderWithRouter(<AuditLogPage />);
    expect(screen.getByText("192.168.1.100")).toBeInTheDocument();
  });
});

describe("Settings Sub-Pages Integration", () => {
  it("webhooks page has correct structure", () => {
    renderWithRouter(<WebhooksPage />);
    // Check for card structure
    expect(screen.getByText("Active Webhooks")).toBeInTheDocument();
    expect(screen.getByText("Manage your webhook endpoints")).toBeInTheDocument();
  });

  it("audit log page has correct structure", () => {
    renderWithRouter(<AuditLogPage />);
    // Check for card structure
    expect(screen.getByText("Activity Log")).toBeInTheDocument();
    expect(screen.getByText(/Showing.*entries/i)).toBeInTheDocument();
  });
});
