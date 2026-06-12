import { PADDLE_KEY } from "./config";

declare global {
  interface Window {
    Paddle?: {
      Setup: (options: { vendor: number; eventCallback?: (data: unknown) => void }) => void;
      Checkout: {
        open: (options: {
          product: number;
          email?: string;
          passthrough?: string;
          successCallback?: () => void;
          closeCallback?: () => void;
        }) => void;
      };
    };
  }
}

export function initializePaddle(): void {
  if (!PADDLE_KEY || typeof window === "undefined") return;

  const existingScript = document.querySelector('script[src*="paddle.js"]');
  if (existingScript) return;

  const script = document.createElement("script");
  script.src = "https://cdn.paddle.com/paddle/paddle.js";
  script.async = true;
  script.onload = () => {
    if (window.Paddle) {
      const vendorId = parseInt(PADDLE_KEY, 10);
      if (!isNaN(vendorId)) {
        window.Paddle.Setup({ vendor: vendorId });
      }
    }
  };
  document.head.appendChild(script);
}

export function openCheckout(priceId: string, email?: string): void {
  if (!window.Paddle) {
    initializePaddle();
    setTimeout(() => {
      if (window.Paddle) {
        window.Paddle.Checkout.open({
          product: parseInt(priceId, 10),
          email,
          successCallback: () => {
            window.location.href = "/dashboard";
          },
        });
      }
    }, 1000);
    return;
  }

  window.Paddle.Checkout.open({
    product: parseInt(priceId, 10),
    email,
    successCallback: () => {
      window.location.href = "/dashboard";
    },
  });
}
