"use client";

import * as React from "react";
import { cn } from "@/utils/utils";
import { Button } from "@/components/ui/button";

interface Step3IntegrationsProps {
  integrations: {
    shopify: boolean;
    zendesk: boolean;
    twilio: boolean;
    email: boolean;
  };
  updateData: (updates: { integrations: Step3IntegrationsProps["integrations"] }) => void;
  onValidate?: (isValid: boolean) => void;
}

interface Integration {
  id: keyof Step3IntegrationsProps["integrations"];
  name: string;
  description: string;
  icon: React.ReactNode;
  category: "E-commerce" | "Support" | "Communication" | "Email";
  setupUrl?: string;
  setupTime: string;
}

const integrationsList: Integration[] = [
  {
    id: "shopify",
    name: "Shopify",
    description: "Connect your Shopify store for order management and refunds",
    icon: (
      <svg className="w-6 h-6" viewBox="0 0 24 24" fill="currentColor">
        <path d="M15.337 23.979l7.216-1.561s-2.604-17.613-2.625-17.73c-.018-.116-.114-.192-.211-.192s-1.929-.136-1.929-.136-1.275-1.274-1.439-1.411c-.035-.028-.074-.046-.116-.056l-.857 19.086zm-2.489-14.094c-.219-.111-1.283-.586-1.283-.586s-2.243-2.563-2.489-2.844c-.028-.031-.057-.054-.088-.073l1.152 12.921 7.216-1.561s-2.604-17.613-2.625-17.73c-.018-.116-.114-.192-.211-.192s-1.929-.136-1.929-.136-.401-.401-.659-.589c-.037-.027-.08-.046-.124-.057-.074-.018-.153-.012-.22.02-.089.042-.157.125-.185.225-.093.35-.258 1.168-.258 1.168s-1.166-.454-1.48-.587c-.069-.029-.144-.042-.218-.042-.196 0-.383.1-.483.27-.204.343-.476.924-.476.924s-.015-.011-.039-.025c-.089-.05-.19-.074-.29-.074-.195 0-.383.099-.483.27-.203.343-.476.924-.476.924s.864.403 1.083.514l.021.011c-.103.347-.363 1.213-.363 1.213s.864.403 1.083.514l.021.011c-.103.347-.363 1.213-.363 1.213s1.072.501 1.283.586z" />
      </svg>
    ),
    category: "E-commerce",
    setupTime: "2 min",
  },
  {
    id: "zendesk",
    name: "Zendesk",
    description: "Sync tickets between Zendesk and PARWA seamlessly",
    icon: (
      <svg className="w-6 h-6" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm0 4.5c1.657 0 3 1.343 3 3s-1.343 3-3 3-3-1.343-3-3 1.343-3 3-3zm-6 12v-1.5c0-2.485 2.686-4.5 6-4.5s6 2.015 6 4.5v1.5H6z" />
      </svg>
    ),
    category: "Support",
    setupTime: "5 min",
  },
  {
    id: "twilio",
    name: "Twilio",
    description: "Enable voice calls and SMS notifications for customers",
    icon: (
      <svg className="w-6 h-6" viewBox="0 0 24 24" fill="currentColor">
        <path d="M10.4 7.2c-.4-.4-.6-.9-.6-1.4 0-.5.2-1 .6-1.4.4-.4.9-.6 1.4-.6.5 0 1 .2 1.4.6.4.4.6.9.6 1.4 0 .5-.2 1-.6 1.4-.4.4-.9.6-1.4.6-.5 0-1-.2-1.4-.6zm-4 4c-.4-.4-.6-.9-.6-1.4 0-.5.2-1 .6-1.4.4-.4.9-.6 1.4-.6.5 0 1 .2 1.4.6.4.4.6.9.6 1.4 0 .5-.2 1-.6 1.4-.4.4-.9.6-1.4.6-.5 0-1-.2-1.4-.6zm8 0c-.4-.4-.6-.9-.6-1.4 0-.5.2-1 .6-1.4.4-.4.9-.6 1.4-.6.5 0 1 .2 1.4.6.4.4.6.9.6 1.4 0 .5-.2 1-.6 1.4-.4.4-.9.6-1.4.6-.5 0-1-.2-1.4-.6zm-4 4c-.4-.4-.6-.9-.6-1.4 0-.5.2-1 .6-1.4.4-.4.9-.6 1.4-.6.5 0 1 .2 1.4.6.4.4.6.9.6 1.4 0 .5-.2 1-.6 1.4-.4.4-.9.6-1.4.6-.5 0-1-.2-1.4-.6zM12 24C5.373 24 0 18.627 0 12S5.373 0 12 0s12 5.373 12 12-5.373 12-12 12z" />
      </svg>
    ),
    category: "Communication",
    setupTime: "3 min",
  },
  {
    id: "email",
    name: "Email Provider",
    description: "Connect your SMTP for outbound notifications",
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    ),
    category: "Email",
    setupTime: "2 min",
  },
];

export function Step3Integrations({ integrations, updateData, onValidate }: Step3IntegrationsProps) {
  const [connecting, setConnecting] = React.useState<string | null>(null);

  React.useEffect(() => {
    // Step is always valid since integrations are optional
    onValidate?.(true);
  }, [onValidate]);

  const toggleIntegration = (id: keyof typeof integrations) => {
    updateData({
      integrations: {
        ...integrations,
        [id]: !integrations[id],
      },
    });
  };

  const handleConnect = async (id: keyof typeof integrations) => {
    setConnecting(id);
    // Simulate connection process
    await new Promise((resolve) => setTimeout(resolve, 1000));
    toggleIntegration(id);
    setConnecting(null);
  };

  const connectedCount = Object.values(integrations).filter(Boolean).length;

  return (
    <div className="space-y-6">
      <div className="text-center mb-6">
        <h2 className="text-lg font-semibold">Connect your tools</h2>
        <p className="text-sm text-muted-foreground">
          Integrate with your existing tools for a seamless experience
        </p>
        {connectedCount > 0 && (
          <p className="text-sm text-primary mt-2">
            {connectedCount} integration{connectedCount !== 1 ? "s" : ""} connected
          </p>
        )}
      </div>

      <div className="space-y-3">
        {integrationsList.map((integration) => (
          <div
            key={integration.id}
            className={cn(
              "flex items-center justify-between p-4 rounded-lg border transition-all",
              integrations[integration.id]
                ? "border-primary bg-primary/5"
                : "border-border hover:border-primary/50"
            )}
          >
            <div className="flex items-center gap-4">
              <div
                className={cn(
                  "w-12 h-12 rounded-lg flex items-center justify-center",
                  integrations[integration.id]
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground"
                )}
              >
                {integration.icon}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h4 className="font-medium">{integration.name}</h4>
                  <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">
                    {integration.category}
                  </span>
                </div>
                <p className="text-sm text-muted-foreground">{integration.description}</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Setup time: ~{integration.setupTime}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {integrations[integration.id] ? (
                <div className="flex items-center gap-2 text-primary">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  <span className="text-sm font-medium">Connected</span>
                </div>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleConnect(integration.id)}
                  disabled={connecting === integration.id}
                >
                  {connecting === integration.id ? (
                    <>
                      <svg
                        className="animate-spin -ml-1 mr-2 h-4 w-4"
                        fill="none"
                        viewBox="0 0 24 24"
                      >
                        <circle
                          className="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="4"
                        />
                        <path
                          className="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                        />
                      </svg>
                      Connecting...
                    </>
                  ) : (
                    "Connect"
                  )}
                </Button>
              )}
            </div>
          </div>
        ))}
      </div>

      <p className="text-xs text-center text-muted-foreground">
        You can skip this step and connect integrations later from your dashboard settings.
      </p>
    </div>
  );
}

export default Step3Integrations;
