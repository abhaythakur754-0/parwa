import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import { AuthProvider, useAuth } from '@/contexts/AuthContext';

// Mock the authApi
jest.mock('@/lib/api', () => ({
  authApi: {
    login: jest.fn(),
    register: jest.fn(),
    googleAuth: jest.fn(),
    logout: jest.fn(),
    refresh: jest.fn(),
    getMe: jest.fn(),
    checkEmail: jest.fn().mockResolvedValue({ email: 'test@example.com', available: true }),
  },
  getErrorMessage: jest.fn((error: unknown) => {
    if (error instanceof Error) return error.message;
    return 'An error occurred';
  }),
}));

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: jest.fn((key: string) => store[key] || null),
    setItem: jest.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: jest.fn((key: string) => {
      delete store[key];
    }),
    clear: jest.fn(() => {
      store = {};
    }),
  };
})();

Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// Test component to access auth context
function TestComponent() {
  const {
    user,
    isAuthenticated,
    isLoading,
    login,
    logout,
    checkEmailAvailability,
  } = useAuth();

  return (
    <div>
      <p data-testid="loading">{isLoading.toString()}</p>
      <p data-testid="authenticated">{isAuthenticated.toString()}</p>
      <p data-testid="user">{user ? user.email : 'null'}</p>
      <button
        data-testid="login-btn"
        onClick={() => login('test@example.com', 'password')}
      >
        Login
      </button>
      <button
        data-testid="logout-btn"
        onClick={() => logout()}
      >
        Logout
      </button>
      <button
        data-testid="check-email-btn"
        onClick={async () => {
          const result = await checkEmailAvailability('test@example.com');
          console.log('Email available:', result);
        }}
      >
        Check Email
      </button>
    </div>
  );
}

describe('AuthContext', () => {
  const mockUser = {
    id: 'user-123',
    email: 'test@example.com',
    full_name: 'Test User',
    phone: null,
    avatar_url: null,
    role: 'owner',
    is_active: true,
    is_verified: true,
    company_id: 'company-123',
    created_at: '2024-01-01T00:00:00Z',
  };

  const mockAuthResponse = {
    user: mockUser,
    tokens: {
      access_token: 'mock-access-token',
      refresh_token: 'mock-refresh-token',
      token_type: 'bearer',
      expires_in: 3600,
    },
    is_new_user: false,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    localStorageMock.clear();
  });

  it('should provide initial unauthenticated state', async () => {
    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    // Wait for initialization to complete
    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('false');
    });

    expect(screen.getByTestId('authenticated')).toHaveTextContent('false');
    expect(screen.getByTestId('user')).toHaveTextContent('null');
  });

  it('should authenticate user on login', async () => {
    const { authApi } = require('@/lib/api');
    authApi.login.mockResolvedValueOnce(mockAuthResponse);

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    // Wait for initialization
    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('false');
    });

    // Click login button
    await act(async () => {
      screen.getByTestId('login-btn').click();
    });

    // Check authenticated state
    await waitFor(() => {
      expect(screen.getByTestId('authenticated')).toHaveTextContent('true');
      expect(screen.getByTestId('user')).toHaveTextContent('test@example.com');
    });

    // Verify API was called correctly
    expect(authApi.login).toHaveBeenCalledWith({
      email: 'test@example.com',
      password: 'password',
    });
  });

  it('should clear auth state on logout', async () => {
    const { authApi } = require('@/lib/api');
    authApi.login.mockResolvedValueOnce(mockAuthResponse);
    authApi.logout.mockResolvedValueOnce({ message: 'Logged out' });

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    // Login first
    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('false');
    });

    await act(async () => {
      screen.getByTestId('login-btn').click();
    });

    await waitFor(() => {
      expect(screen.getByTestId('authenticated')).toHaveTextContent('true');
    });

    // Then logout
    await act(async () => {
      screen.getByTestId('logout-btn').click();
    });

    // Check unauthenticated state
    await waitFor(() => {
      expect(screen.getByTestId('authenticated')).toHaveTextContent('false');
      expect(screen.getByTestId('user')).toHaveTextContent('null');
    });
  });

  it('should check email availability', async () => {
    const { authApi } = require('@/lib/api');
    authApi.checkEmail.mockResolvedValueOnce({
      email: 'test@example.com',
      available: true,
    });

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('false');
    });

    await act(async () => {
      screen.getByTestId('check-email-btn').click();
    });

    expect(authApi.checkEmail).toHaveBeenCalledWith('test@example.com');
  });
});

describe('useAuth hook', () => {
  it('should throw error when used outside AuthProvider', () => {
    // Suppress console.error for this test
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

    function TestComponentWithoutProvider() {
      useAuth();
      return null;
    }

    expect(() => render(<TestComponentWithoutProvider />)).toThrow(
      'useAuth must be used within an AuthProvider'
    );

    consoleSpy.mockRestore();
  });
});
