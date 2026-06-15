import { create } from "zustand";

interface OnboardingState {
  currentStep: number;
  industry: string | null;
  variant: string | null;
  legalAccepted: boolean;
  integrations: string[];
  kbUploaded: boolean;
  aiConfigured: boolean;
  paymentDone: boolean;
  isLoading: boolean;
  error: string | null;

  setIndustry: (industry: string) => void;
  setVariant: (variant: string) => void;
  setLegalAccepted: (accepted: boolean) => void;
  setIntegrations: (integrations: string[]) => void;
  setKbUploaded: (uploaded: boolean) => void;
  setAiConfigured: (configured: boolean) => void;
  setPaymentDone: (done: boolean) => void;
  nextStep: () => void;
  prevStep: () => void;
  setStep: (step: number) => void;
  loadState: () => Promise<void>;
  reset: () => void;
}

const initialState = {
  currentStep: 0,
  industry: null,
  variant: null,
  legalAccepted: false,
  integrations: [],
  kbUploaded: false,
  aiConfigured: false,
  paymentDone: false,
  isLoading: false,
  error: null,
};

export const useOnboardingStore = create<OnboardingState>((set, get) => ({
  ...initialState,

  setIndustry: (industry) => set({ industry }),
  setVariant: (variant) => set({ variant }),
  setLegalAccepted: (accepted) => set({ legalAccepted: accepted }),
  setIntegrations: (integrations) => set({ integrations }),
  setKbUploaded: (uploaded) => set({ kbUploaded: uploaded }),
  setAiConfigured: (configured) => set({ aiConfigured: configured }),
  setPaymentDone: (done) => set({ paymentDone: done }),

  nextStep: () => set((s) => ({ currentStep: Math.min(s.currentStep + 1, 6) })),
  prevStep: () => set((s) => ({ currentStep: Math.max(s.currentStep - 1, 0) })),
  setStep: (step) => set({ currentStep: step }),

  loadState: async () => {
    set({ isLoading: true });
    try {
      const res = await fetch("/api/onboarding");
      if (res.ok) {
        const data = await res.json();
        set({
          currentStep: data.current_step || 0,
          industry: data.industry || null,
          variant: data.variant || null,
          legalAccepted: data.legal_accepted || false,
          integrations: data.integrations || [],
          kbUploaded: data.kb_uploaded || false,
          aiConfigured: data.ai_configured || false,
          paymentDone: data.payment_done || false,
          isLoading: false,
        });
      } else {
        set({ isLoading: false });
      }
    } catch {
      set({ isLoading: false, error: "Failed to load onboarding state" });
    }
  },

  reset: () => set(initialState),
}));
