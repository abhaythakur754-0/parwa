/**
 * Zustand Stores Tests
 *
 * Unit tests for PARWA state management stores.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act } from "@testing-library/react";

// Mock the API functions
vi.mock("../lib/api/auth", () => ({
  authAPI: {
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    getCurrentUser: vi.fn(),
    updateProfile: vi.fn(),
  },
}));

vi.mock("../lib/api/client", () => ({
  apiClient: {
    setAuthToken: vi.fn(),
    clearAuthToken: vi.fn(),
    getAuthToken: vi.fn(() => null),
  },
}));

vi.mock("../lib/api/variants", () => ({
  variantsAPI: {
    getVariants: vi.fn(),
    getVariantConfig: vi.fn(),
    selectVariant: vi.fn(),
  },
  getDefaultVariantConfigs: vi.fn(() => [
    {
      id: "mini",
      name: "Mini PARWA",
      tier: "light",
      price: 1000,
      maxConcurrentCalls: 2,
      refundLimit: 50,
      escalationThreshold: 70,
    },
    {
      id: "parwa",
      name: "PARWA Junior",
      tier: "medium",
      price: 2500,
      maxConcurrentCalls: 5,
      refundLimit: 500,
      escalationThreshold: 60,
    },
    {
      id: "parwa_high",
      name: "PARWA High",
      tier: "heavy",
      price: 4000,
      maxConcurrentCalls: 10,
      refundLimit: 2000,
      escalationThreshold: 50,
    },
  ]),
}));

import { authAPI } from "../services/api/auth";
import { variantsAPI, getDefaultVariantConfigs } from "../services/api/variants";
import { apiClient } from "../services/api/client";

// Import stores after mocking
import { useAuthStore } from "../stores/authStore";
import { useVariantStore } from "../stores/variantStore";
import { useUIStore } from "../stores/uiStore";

const mockedAuthAPI = vi.mocked(authAPI);
const mockedVariantsAPI = vi.mocked(variantsAPI);
const mockedAPIClient = vi.mocked(apiClient);
const mockedGetDefaultConfigs = vi.mocked(getDefaultVariantConfigs);

describe("Auth Store", () => {
  beforeEach(() => {
    // Reset store state
    useAuthStore.setState({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe("initial state", () => {
    it("has correct initial state", () => {
      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.token).toBeNull();
      expect(state.isAuthenticated).toBe(false);
      expect(state.isLoading).toBe(false);
      expect(state.error).toBeNull();
    });
  });

  describe("login", () => {
    it("successfully logs in user", async () => {
      const mockUser = {
        id: "1",
        email: "test@example.com",
        name: "Test User",
        role: "admin" as const,
        createdAt: "2024-01-01",
      };
      const mockToken = "test-token";

      mockedAuthAPI.login.mockResolvedValueOnce({
        user: mockUser,
        token: mockToken,
      });

      await act(async () => {
        await useAuthStore.getState().login("test@example.com", "password");
      });

      const state = useAuthStore.getState();
      expect(state.user).toEqual(mockUser);
      expect(state.token).toBe(mockToken);
      expect(state.isAuthenticated).toBe(true);
      expect(state.isLoading).toBe(false);
      expect(state.error).toBeNull();
      expect(mockedAPIClient.setAuthToken).toHaveBeenCalledWith(mockToken);
    });

    it("handles login error", async () => {
      mockedAuthAPI.login.mockRejectedValueOnce(new Error("Invalid credentials"));

      await act(async () => {
        try {
          await useAuthStore.getState().login("test@example.com", "wrong");
        } catch {
          // Expected
        }
      });

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(false);
      expect(state.error).toBe("Invalid credentials");
    });
  });

  describe("register", () => {
    it("successfully registers user", async () => {
      const mockUser = {
        id: "2",
        email: "new@example.com",
        name: "New User",
        role: "admin" as const,
        createdAt: "2024-01-01",
      };
      const mockToken = "register-token";

      mockedAuthAPI.register.mockResolvedValueOnce({
        user: mockUser,
        token: mockToken,
      });

      await act(async () => {
        await useAuthStore.getState().register("New User", "new@example.com", "password");
      });

      const state = useAuthStore.getState();
      expect(state.user).toEqual(mockUser);
      expect(state.isAuthenticated).toBe(true);
    });
  });

  describe("logout", () => {
    it("clears auth state on logout", async () => {
      // First set up authenticated state
      useAuthStore.setState({
        user: { id: "1", email: "test@example.com", name: "Test", role: "admin", createdAt: "2024-01-01" },
        token: "test-token",
        isAuthenticated: true,
      });

      mockedAuthAPI.logout.mockResolvedValueOnce();

      await act(async () => {
        await useAuthStore.getState().logout();
      });

      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.token).toBeNull();
      expect(state.isAuthenticated).toBe(false);
      expect(mockedAPIClient.clearAuthToken).toHaveBeenCalled();
    });
  });

  describe("setUser", () => {
    it("sets user and updates isAuthenticated", () => {
      const mockUser = {
        id: "1",
        email: "test@example.com",
        name: "Test",
        role: "admin" as const,
        createdAt: "2024-01-01",
      };

      act(() => {
        useAuthStore.getState().setUser(mockUser);
      });

      const state = useAuthStore.getState();
      expect(state.user).toEqual(mockUser);
      expect(state.isAuthenticated).toBe(true);
    });
  });

  describe("clearError", () => {
    it("clears error state", () => {
      useAuthStore.setState({ error: "Some error" });

      act(() => {
        useAuthStore.getState().clearError();
      });

      expect(useAuthStore.getState().error).toBeNull();
    });
  });
});

describe("Variant Store", () => {
  beforeEach(() => {
    useVariantStore.setState({
      selectedVariant: null,
      variantConfig: null,
      availableVariants: [],
      isLoading: false,
      error: null,
    });
    vi.clearAllMocks();
  });

  describe("initial state", () => {
    it("has correct initial state", () => {
      const state = useVariantStore.getState();
      expect(state.selectedVariant).toBeNull();
      expect(state.variantConfig).toBeNull();
      expect(state.availableVariants).toEqual([]);
      expect(state.isLoading).toBe(false);
    });
  });

  describe("initialize", () => {
    it("loads default variant configs", () => {
      act(() => {
        useVariantStore.getState().initialize();
      });

      const state = useVariantStore.getState();
      expect(state.availableVariants).toHaveLength(3);
      expect(mockedGetDefaultConfigs).toHaveBeenCalled();
    });
  });

  describe("selectVariant", () => {
    it("selects a variant locally when API fails", async () => {
      // First initialize with defaults
      act(() => {
        useVariantStore.getState().initialize();
      });

      mockedVariantsAPI.selectVariant.mockRejectedValueOnce(new Error("Not authenticated"));
      mockedVariantsAPI.getVariantConfig.mockRejectedValueOnce(new Error("Not authenticated"));

      await act(async () => {
        try {
          await useVariantStore.getState().selectVariant("mini");
        } catch {
          // Expected to fail when config not found
        }
      });

      // Check that local selection still works
      const state = useVariantStore.getState();
      // The variant should be set if config was found locally
      expect(state.selectedVariant).toBe("mini");
    });
  });

  describe("clearVariant", () => {
    it("clears selected variant", () => {
      useVariantStore.setState({
        selectedVariant: "mini",
        variantConfig: { id: "mini", name: "Mini" } as any,
      });

      act(() => {
        useVariantStore.getState().clearVariant();
      });

      const state = useVariantStore.getState();
      expect(state.selectedVariant).toBeNull();
      expect(state.variantConfig).toBeNull();
    });
  });

  describe("setLocalVariant", () => {
    it("sets variant locally without API call", () => {
      // Initialize with defaults
      act(() => {
        useVariantStore.getState().initialize();
      });

      act(() => {
        useVariantStore.getState().setLocalVariant("parwa");
      });

      const state = useVariantStore.getState();
      expect(state.selectedVariant).toBe("parwa");
    });
  });
});

describe("UI Store", () => {
  beforeEach(() => {
    useUIStore.setState({
      sidebarOpen: true,
      sidebarCollapsed: false,
      theme: "system",
      activeModal: null,
      modalStack: [],
      toasts: [],
      globalLoading: false,
      loadingMessage: null,
      activeNavItem: null,
      breadcrumbs: [],
    });
  });

  describe("initial state", () => {
    it("has correct initial state", () => {
      const state = useUIStore.getState();
      expect(state.sidebarOpen).toBe(true);
      expect(state.sidebarCollapsed).toBe(false);
      expect(state.theme).toBe("system");
      expect(state.activeModal).toBeNull();
      expect(state.toasts).toEqual([]);
    });
  });

  describe("sidebar actions", () => {
    it("toggles sidebar open state", () => {
      act(() => {
        useUIStore.getState().toggleSidebar();
      });

      expect(useUIStore.getState().sidebarOpen).toBe(false);

      act(() => {
        useUIStore.getState().toggleSidebar();
      });

      expect(useUIStore.getState().sidebarOpen).toBe(true);
    });

    it("sets sidebar open state", () => {
      act(() => {
        useUIStore.getState().setSidebarOpen(false);
      });

      expect(useUIStore.getState().sidebarOpen).toBe(false);
    });

    it("toggles sidebar collapsed state", () => {
      act(() => {
        useUIStore.getState().toggleSidebarCollapsed();
      });

      expect(useUIStore.getState().sidebarCollapsed).toBe(true);
    });
  });

  describe("theme actions", () => {
    it("sets theme", () => {
      act(() => {
        useUIStore.getState().setTheme("dark");
      });

      expect(useUIStore.getState().theme).toBe("dark");
    });

    it("toggles theme between light and dark", () => {
      act(() => {
        useUIStore.getState().setTheme("light");
      });

      act(() => {
        useUIStore.getState().toggleTheme();
      });

      expect(useUIStore.getState().theme).toBe("dark");
    });
  });

  describe("modal actions", () => {
    it("opens a modal", () => {
      act(() => {
        useUIStore.getState().openModal("test-modal", { foo: "bar" });
      });

      const state = useUIStore.getState();
      expect(state.activeModal).toEqual({
        id: "test-modal",
        data: { foo: "bar" },
      });
    });

    it("closes modal", () => {
      act(() => {
        useUIStore.getState().openModal("test-modal");
      });

      act(() => {
        useUIStore.getState().closeModal();
      });

      expect(useUIStore.getState().activeModal).toBeNull();
    });

    it("manages modal stack", () => {
      act(() => {
        useUIStore.getState().openModal("modal-1");
      });

      act(() => {
        useUIStore.getState().openModal("modal-2");
      });

      const state = useUIStore.getState();
      expect(state.activeModal?.id).toBe("modal-2");
      expect(state.modalStack).toHaveLength(1);
      expect(state.modalStack[0].id).toBe("modal-1");

      act(() => {
        useUIStore.getState().closeModal();
      });

      const stateAfterClose = useUIStore.getState();
      expect(stateAfterClose.activeModal?.id).toBe("modal-1");
    });

    it("closes all modals", () => {
      act(() => {
        useUIStore.getState().openModal("modal-1");
        useUIStore.getState().openModal("modal-2");
      });

      act(() => {
        useUIStore.getState().closeAllModals();
      });

      const state = useUIStore.getState();
      expect(state.activeModal).toBeNull();
      expect(state.modalStack).toEqual([]);
    });
  });

  describe("toast actions", () => {
    it("adds a toast", () => {
      let toastId: string;

      act(() => {
        toastId = useUIStore.getState().addToast({
          title: "Test Toast",
          variant: "success",
        });
      });

      const state = useUIStore.getState();
      expect(state.toasts).toHaveLength(1);
      expect(state.toasts[0].title).toBe("Test Toast");
      expect(state.toasts[0].variant).toBe("success");
    });

    it("removes a toast", () => {
      let toastId: string = "";

      act(() => {
        toastId = useUIStore.getState().addToast({
          title: "Test Toast",
          variant: "default",
        });
      });

      act(() => {
        useUIStore.getState().removeToast(toastId);
      });

      expect(useUIStore.getState().toasts).toHaveLength(0);
    });

    it("clears all toasts", () => {
      act(() => {
        useUIStore.getState().addToast({ title: "Toast 1", variant: "default" });
        useUIStore.getState().addToast({ title: "Toast 2", variant: "success" });
      });

      act(() => {
        useUIStore.getState().clearToasts();
      });

      expect(useUIStore.getState().toasts).toHaveLength(0);
    });
  });

  describe("loading actions", () => {
    it("sets global loading state", () => {
      act(() => {
        useUIStore.getState().setGlobalLoading(true, "Loading...");
      });

      const state = useUIStore.getState();
      expect(state.globalLoading).toBe(true);
      expect(state.loadingMessage).toBe("Loading...");
    });
  });

  describe("navigation actions", () => {
    it("sets active nav item", () => {
      act(() => {
        useUIStore.getState().setActiveNavItem("dashboard");
      });

      expect(useUIStore.getState().activeNavItem).toBe("dashboard");
    });

    it("sets breadcrumbs", () => {
      const breadcrumbs = [
        { label: "Home", href: "/" },
        { label: "Dashboard" },
      ];

      act(() => {
        useUIStore.getState().setBreadcrumbs(breadcrumbs);
      });

      expect(useUIStore.getState().breadcrumbs).toEqual(breadcrumbs);
    });
  });

  describe("resetUIState", () => {
    it("resets UI state to defaults", () => {
      // Set some state
      act(() => {
        useUIStore.getState().setSidebarOpen(false);
        useUIStore.getState().setActiveNavItem("settings");
        useUIStore.getState().addToast({ title: "Test", variant: "default" });
      });

      // Reset
      act(() => {
        useUIStore.getState().resetUIState();
      });

      const state = useUIStore.getState();
      expect(state.sidebarOpen).toBe(true);
      expect(state.activeNavItem).toBeNull();
      expect(state.toasts).toEqual([]);
      // Theme should be preserved
      expect(state.theme).toBe("system");
    });
  });
});

describe("Store Integration", () => {
  it("all stores can be used together", () => {
    // Simulate user flow
    act(() => {
      // Initialize variant store
      useVariantStore.getState().initialize();

      // Open sidebar
      useUIStore.getState().setSidebarOpen(true);

      // Select a variant
      useVariantStore.getState().setLocalVariant("mini");
    });

    const variantState = useVariantStore.getState();
    const uiState = useUIStore.getState();

    expect(variantState.selectedVariant).toBe("mini");
    expect(uiState.sidebarOpen).toBe(true);
  });
});
