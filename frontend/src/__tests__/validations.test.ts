import {
  loginSchema,
  registerSchema,
  forgotPasswordSchema,
  resetPasswordSchema,
  changePasswordSchema,
  profileSchema,
  validateFormData,
  checkPasswordStrength,
} from "@/validations/auth";

describe("Auth Validation Schemas", () => {
  // Login Schema Tests
  describe("loginSchema", () => {
    it("validates valid login data", () => {
      const result = loginSchema.safeParse({
        email: "test@example.com",
        password: "password123",
      });
      expect(result.success).toBe(true);
    });

    it("requires email", () => {
      const result = loginSchema.safeParse({
        email: "",
        password: "password123",
      });
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.errors[0].message).toContain("required");
      }
    });

    it("requires valid email format", () => {
      const result = loginSchema.safeParse({
        email: "invalid-email",
        password: "password123",
      });
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.errors[0].message).toContain("valid email");
      }
    });

    it("requires password", () => {
      const result = loginSchema.safeParse({
        email: "test@example.com",
        password: "",
      });
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.errors[0].message).toContain("required");
      }
    });

    it("requires password minimum length", () => {
      const result = loginSchema.safeParse({
        email: "test@example.com",
        password: "short",
      });
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.errors[0].message).toContain("8 characters");
      }
    });
  });

  // Register Schema Tests
  describe("registerSchema", () => {
    it("validates valid registration data", () => {
      const result = registerSchema.safeParse({
        name: "John Doe",
        email: "john@example.com",
        password: "Password123",
        confirmPassword: "Password123",
        acceptTerms: true,
      });
      expect(result.success).toBe(true);
    });

    it("requires name", () => {
      const result = registerSchema.safeParse({
        name: "",
        email: "john@example.com",
        password: "Password123",
        confirmPassword: "Password123",
        acceptTerms: true,
      });
      expect(result.success).toBe(false);
    });

    it("requires name minimum length", () => {
      const result = registerSchema.safeParse({
        name: "J",
        email: "john@example.com",
        password: "Password123",
        confirmPassword: "Password123",
        acceptTerms: true,
      });
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.errors[0].message).toContain("2 characters");
      }
    });

    it("validates name format", () => {
      const result = registerSchema.safeParse({
        name: "John123",
        email: "john@example.com",
        password: "Password123",
        confirmPassword: "Password123",
        acceptTerms: true,
      });
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.errors[0].message).toContain("letters");
      }
    });

    it("transforms email to lowercase", () => {
      const result = registerSchema.safeParse({
        name: "John Doe",
        email: "JOHN@EXAMPLE.COM",
        password: "Password123",
        confirmPassword: "Password123",
        acceptTerms: true,
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.email).toBe("john@example.com");
      }
    });

    it("requires password with uppercase, lowercase, and number", () => {
      const result = registerSchema.safeParse({
        name: "John Doe",
        email: "john@example.com",
        password: "password",
        confirmPassword: "password",
        acceptTerms: true,
      });
      expect(result.success).toBe(false);
    });

    it("requires password confirmation to match", () => {
      const result = registerSchema.safeParse({
        name: "John Doe",
        email: "john@example.com",
        password: "Password123",
        confirmPassword: "Different123",
        acceptTerms: true,
      });
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.errors[0].message).toContain("match");
      }
    });

    it("requires terms acceptance", () => {
      const result = registerSchema.safeParse({
        name: "John Doe",
        email: "john@example.com",
        password: "Password123",
        confirmPassword: "Password123",
        acceptTerms: false,
      });
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.errors[0].message).toContain("accept");
      }
    });
  });

  // Forgot Password Schema Tests
  describe("forgotPasswordSchema", () => {
    it("validates valid email", () => {
      const result = forgotPasswordSchema.safeParse({
        email: "test@example.com",
      });
      expect(result.success).toBe(true);
    });

    it("requires email", () => {
      const result = forgotPasswordSchema.safeParse({
        email: "",
      });
      expect(result.success).toBe(false);
    });

    it("requires valid email format", () => {
      const result = forgotPasswordSchema.safeParse({
        email: "invalid-email",
      });
      expect(result.success).toBe(false);
    });

    it("transforms email to lowercase", () => {
      const result = forgotPasswordSchema.safeParse({
        email: "TEST@EXAMPLE.COM",
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.email).toBe("test@example.com");
      }
    });
  });

  // Reset Password Schema Tests
  describe("resetPasswordSchema", () => {
    it("validates valid reset data", () => {
      const result = resetPasswordSchema.safeParse({
        token: "reset-token-123",
        password: "NewPassword123",
        confirmPassword: "NewPassword123",
      });
      expect(result.success).toBe(true);
    });

    it("requires token", () => {
      const result = resetPasswordSchema.safeParse({
        token: "",
        password: "NewPassword123",
        confirmPassword: "NewPassword123",
      });
      expect(result.success).toBe(false);
    });

    it("requires matching passwords", () => {
      const result = resetPasswordSchema.safeParse({
        token: "reset-token-123",
        password: "NewPassword123",
        confirmPassword: "Different123",
      });
      expect(result.success).toBe(false);
    });
  });

  // Change Password Schema Tests
  describe("changePasswordSchema", () => {
    it("validates valid change password data", () => {
      const result = changePasswordSchema.safeParse({
        currentPassword: "OldPassword123",
        newPassword: "NewPassword456",
        confirmPassword: "NewPassword456",
      });
      expect(result.success).toBe(true);
    });

    it("requires new password to be different from current", () => {
      const result = changePasswordSchema.safeParse({
        currentPassword: "Password123",
        newPassword: "Password123",
        confirmPassword: "Password123",
      });
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.errors[0].message).toContain("different");
      }
    });

    it("requires matching confirm password", () => {
      const result = changePasswordSchema.safeParse({
        currentPassword: "OldPassword123",
        newPassword: "NewPassword456",
        confirmPassword: "Different789",
      });
      expect(result.success).toBe(false);
    });
  });

  // Profile Schema Tests
  describe("profileSchema", () => {
    it("validates valid profile data", () => {
      const result = profileSchema.safeParse({
        name: "John Doe",
        email: "john@example.com",
        company: "Acme Corp",
        phone: "+1-555-123-4567",
      });
      expect(result.success).toBe(true);
    });

    it("validates optional fields", () => {
      const result = profileSchema.safeParse({});
      expect(result.success).toBe(true);
    });

    it("validates phone format", () => {
      const result = profileSchema.safeParse({
        phone: "invalid-phone-abc",
      });
      expect(result.success).toBe(false);
    });

    it("transforms email to lowercase", () => {
      const result = profileSchema.safeParse({
        email: "JOHN@EXAMPLE.COM",
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.email).toBe("john@example.com");
      }
    });
  });
});

// Password Strength Tests
describe("checkPasswordStrength", () => {
  it("rates weak password correctly", () => {
    const result = checkPasswordStrength("password");
    expect(result.score).toBeLessThan(5);
    expect(result.isStrong).toBe(false);
    expect(result.feedback.length).toBeGreaterThan(0);
  });

  it("rates strong password correctly", () => {
    const result = checkPasswordStrength("StrongP@ssw0rd!");
    expect(result.score).toBeGreaterThanOrEqual(5);
    expect(result.isStrong).toBe(true);
    expect(result.feedback.length).toBe(0);
  });

  it("gives feedback for missing uppercase", () => {
    const result = checkPasswordStrength("password123!");
    expect(result.feedback).toContain("Add uppercase letters");
  });

  it("gives feedback for missing lowercase", () => {
    const result = checkPasswordStrength("PASSWORD123!");
    expect(result.feedback).toContain("Add lowercase letters");
  });

  it("gives feedback for missing numbers", () => {
    const result = checkPasswordStrength("Password!");
    expect(result.feedback).toContain("Add numbers");
  });

  it("gives feedback for missing special characters", () => {
    const result = checkPasswordStrength("Password123");
    expect(result.feedback).toContain("Add special characters");
  });

  it("gives feedback for short password", () => {
    const result = checkPasswordStrength("Pass1!");
    expect(result.feedback).toContain("Use at least 8 characters");
  });

  it("rewards longer passwords", () => {
    const shortResult = checkPasswordStrength("Passw0rd!");
    const longResult = checkPasswordStrength("VeryLongPassw0rd!");

    expect(longResult.score).toBeGreaterThan(shortResult.score);
  });
});

// validateFormData helper Tests
describe("validateFormData", () => {
  it("returns success with parsed data for valid input", () => {
    const result = validateFormData(loginSchema, {
      email: "test@example.com",
      password: "password123",
    });

    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.email).toBe("test@example.com");
      expect(result.data.password).toBe("password123");
    }
  });

  it("returns errors for invalid input", () => {
    const result = validateFormData(loginSchema, {
      email: "invalid",
      password: "short",
    });

    expect(result.success).toBe(false);
    if (!result.success) {
      expect(Object.keys(result.errors).length).toBeGreaterThan(0);
    }
  });

  it("handles missing fields", () => {
    const result = validateFormData(loginSchema, {});

    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.errors.email).toBeDefined();
      expect(result.errors.password).toBeDefined();
    }
  });

  it("applies schema transformations", () => {
    const result = validateFormData(forgotPasswordSchema, {
      email: "TEST@EXAMPLE.COM",
    });

    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.email).toBe("test@example.com");
    }
  });
});
