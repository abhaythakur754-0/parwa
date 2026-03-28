/**
 * PARWA v2 - Mutation Helpers Tests
 *
 * Unit tests for mutation helper functions.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";
import {
  useOptimisticMutation,
  useListMutation,
  useRetryableMutation,
  useDebouncedMutation,
} from "../lib/react-query/mutation-helpers";

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);
};

describe("useOptimisticMutation", () => {
  it("should create a mutation hook", () => {
    const wrapper = createWrapper();

    const { result } = renderHook(
      () =>
        useOptimisticMutation({
          mutationFn: vi.fn(),
          queryKey: ["test"],
          optimisticUpdate: (old, variables) => variables as unknown as undefined,
        }),
      { wrapper }
    );

    expect(result.current.mutate).toBeDefined();
    expect(result.current.mutateAsync).toBeDefined();
    expect(result.current.isPending).toBe(false);
  });
});

describe("useListMutation", () => {
  it("should create a list mutation hook", () => {
    const wrapper = createWrapper();

    const { result } = renderHook(
      () =>
        useListMutation({
          mutationFn: vi.fn(),
          queryKey: ["items"],
          operation: "add",
          getItemId: (item) => item.id,
        }),
      { wrapper }
    );

    expect(result.current.mutate).toBeDefined();
    expect(result.current.isPending).toBe(false);
  });
});

describe("useRetryableMutation", () => {
  it("should create a retryable mutation hook", () => {
    const wrapper = createWrapper();

    const { result } = renderHook(
      () =>
        useRetryableMutation({
          mutationFn: vi.fn(),
        }),
      { wrapper }
    );

    expect(result.current.mutate).toBeDefined();
    expect(result.current.retry).toBeDefined();
    expect(result.current.isPending).toBe(false);
  });

  it("should track last variables for retry", async () => {
    const mutationFn = vi.fn().mockResolvedValue({ success: true });
    const wrapper = createWrapper();

    const { result } = renderHook(
      () =>
        useRetryableMutation({
          mutationFn,
        }),
      { wrapper }
    );

    await act(async () => {
      result.current.mutate({ test: "data" });
    });

    expect(mutationFn).toHaveBeenCalledTimes(1);
  });
});

describe("useDebouncedMutation", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  it("should create a debounced mutation hook", () => {
    const wrapper = createWrapper();

    const { result } = renderHook(
      () =>
        useDebouncedMutation(vi.fn(), 300),
      { wrapper }
    );

    expect(result.current.mutate).toBeDefined();
    expect(result.current.flush).toBeDefined();
    expect(result.current.cancel).toBeDefined();
  });

  it("should debounce mutation calls", async () => {
    const mutationFn = vi.fn().mockResolvedValue({ success: true });
    const wrapper = createWrapper();

    const { result } = renderHook(
      () => useDebouncedMutation(mutationFn, 300),
      { wrapper }
    );

    act(() => {
      result.current.mutate("first");
      result.current.mutate("second");
      result.current.mutate("third");
    });

    expect(mutationFn).not.toHaveBeenCalled();

    await act(async () => {
      vi.advanceTimersByTime(300);
    });

    expect(mutationFn).toHaveBeenCalledTimes(1);
    expect(mutationFn).toHaveBeenCalledWith("third");
  });
});
