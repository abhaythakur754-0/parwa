export const APP_NAME = "PARWA";

export const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export const PADDLE_KEY = process.env.NEXT_PUBLIC_PADDLE_KEY || "";

export const PRICES = {
  mini_parwa: {
    monthly: 999,
    annual: 9990,
    paddle_id: "pri_01krxm4r0kcm6mm5fc84pp9bj0",
  },
  parwa: {
    monthly: 2499,
    annual: 24990,
    paddle_id: "pri_01krxm4ra529ry7bzr9z73pza1",
  },
  parwa_high: {
    monthly: 4999,
    annual: 49990,
    paddle_id: "pri_01krxm4rjx1bfgg1w9z4qr3dd8",
  },
};

export const VARIANT_LIMITS = {
  mini: { tickets: 500, ai_steps: 3, concurrent: 2 },
  parwa: { tickets: 2000, ai_steps: 6, concurrent: 3 },
  parwa_high: { tickets: 10000, ai_steps: 9, concurrent: 5 },
};

export const ADD_ONS = {
  voice: { price: 199, label: "Voice Add-on" },
  custom_api: { price: 49, label: "Custom API Add-on" },
};

export const OVERAGE_RATE = 0.1; // $0.10 per ticket beyond limit

export const INDUSTRIES = [
  { id: "saas", name: "SaaS", icon: "Cloud", description: "Software-as-a-Service companies" },
  { id: "ecommerce", name: "E-commerce", icon: "ShoppingCart", description: "Online retail and stores" },
  { id: "logistics", name: "Logistics", icon: "Truck", description: "Shipping and supply chain" },
  { id: "other", name: "Other", icon: "Building2", description: "Other industries" },
] as const;
