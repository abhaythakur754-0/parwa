/**
 * API Client Tests
 *
 * Unit tests for the PARWA API client.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { APIClient, APIError, createAPIClient } from "../services/api/client";

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe("APIClient", () => {
  let client: APIClient;

  beforeEach(() => {
    client = new APIClient("http://test-api.local");
    mockFetch.mockReset();
  });

  afterEach(() => {
    client.clearAuthToken();
  });

  describe("constructor", () => {
    it("creates client with custom base URL", () => {
      const customClient = new APIClient("https://custom.api.com");
      expect(customClient).toBeDefined();
    });

    it("uses default base URL when not provided", () => {
      const defaultClient = createAPIClient("/api");
      expect(defaultClient).toBeDefined();
    });
  });

  describe("auth token management", () => {
    it("sets and gets auth token", () => {
      client.setAuthToken("test-token");
      expect(client.getAuthToken()).toBe("test-token");
    });

    it("clears auth token", () => {
      client.setAuthToken("test-token");
      client.clearAuthToken();
      expect(client.getAuthToken()).toBeNull();
    });
  });

  describe("GET requests", () => {
    it("makes successful GET request", async () => {
      const mockData = { id: 1, name: "Test" };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        statusText: "OK",
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => mockData,
      });

      const response = await client.get("/test");

      expect(response.data).toEqual(mockData);
      expect(response.status).toBe(200);
      expect(mockFetch).toHaveBeenCalledWith(
        "http://test-api.local/test",
        expect.objectContaining({
          method: "GET",
        })
      );
    });

    it("includes auth token when set", async () => {
      client.setAuthToken("secret-token");
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        statusText: "OK",
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({}),
      });

      await client.get("/protected");

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: "Bearer secret-token",
          }),
        })
      );
    });

    it("handles query parameters", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        statusText: "OK",
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({}),
      });

      await client.get("/search", { q: "test", page: "1" });

      expect(mockFetch).toHaveBeenCalledWith(
        "http://test-api.local/search?q=test&page=1",
        expect.any(Object)
      );
    });
  });

  describe("POST requests", () => {
    it("makes successful POST request with body", async () => {
      const requestBody = { name: "Test" };
      const mockData = { id: 1, name: "Test" };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        statusText: "Created",
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => mockData,
      });

      const response = await client.post("/create", requestBody);

      expect(response.data).toEqual(mockData);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify(requestBody),
        })
      );
    });
  });

  describe("PUT requests", () => {
    it("makes successful PUT request", async () => {
      const requestBody = { name: "Updated" };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        statusText: "OK",
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => requestBody,
      });

      const response = await client.put("/update/1", requestBody);

      expect(response.data).toEqual(requestBody);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          method: "PUT",
        })
      );
    });
  });

  describe("PATCH requests", () => {
    it("makes successful PATCH request", async () => {
      const requestBody = { name: "Patched" };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        statusText: "OK",
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => requestBody,
      });

      const response = await client.patch("/patch/1", requestBody);

      expect(response.data).toEqual(requestBody);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          method: "PATCH",
        })
      );
    });
  });

  describe("DELETE requests", () => {
    it("makes successful DELETE request", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 204,
        statusText: "No Content",
        headers: new Headers(),
        text: async () => "",
      });

      const response = await client.delete("/delete/1");

      expect(response.status).toBe(204);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          method: "DELETE",
        })
      );
    });
  });

  describe("error handling", () => {
    it("throws APIError on non-ok response", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: "Not Found",
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({ message: "Resource not found" }),
      });

      await expect(client.get("/not-found")).rejects.toThrow(APIError);
    });

    it("includes error details in APIError", async () => {
      const errorData = { message: "Validation failed", errors: ["name is required"] };
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        statusText: "Bad Request",
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => errorData,
      });

      try {
        await client.get("/invalid");
        expect.fail("Should have thrown");
      } catch (error) {
        expect(error).toBeInstanceOf(APIError);
        const apiError = error as APIError;
        expect(apiError.status).toBe(400);
        expect(apiError.message).toBe("Validation failed");
        expect(apiError.data).toEqual(errorData);
      }
    });
  });
});

describe("APIError", () => {
  it("creates error with all properties", () => {
    const error = new APIError(500, "Internal Server Error", "Something went wrong", {
      detail: "Database connection failed",
    });

    expect(error.status).toBe(500);
    expect(error.statusText).toBe("Internal Server Error");
    expect(error.message).toBe("Something went wrong");
    expect(error.data).toEqual({ detail: "Database connection failed" });
    expect(error.name).toBe("APIError");
  });
});
