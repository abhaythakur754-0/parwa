'use client';

import { useState } from 'react';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { CheckCircle, Circle, ArrowLeft, ArrowRight, AlertCircle } from 'lucide-react';

/**
 * SSO Configuration Wizard Component
 * 
 * A step-by-step wizard for configuring SSO with identity providers.
 */

const steps = [
  { id: 1, title: 'Select Provider', description: 'Choose your identity provider' },
  { id: 2, title: 'Configure IdP', description: 'Enter identity provider settings' },
  { id: 3, title: 'Attribute Mapping', description: 'Map user attributes' },
  { id: 4, title: 'Test & Enable', description: 'Verify and activate SSO' }
];

const identityProviders = [
  { id: 'okta', name: 'Okta' },
  { id: 'azure', name: 'Azure Active Directory' },
  { id: 'google', name: 'Google Workspace' },
  { id: 'onelogin', name: 'OneLogin' },
  { id: 'saml', name: 'Custom SAML 2.0' }
];

interface SSOConfigWizardProps {
  onComplete?: () => void;
  onCancel?: () => void;
}

export function SSOConfigWizard({ onComplete, onCancel }: SSOConfigWizardProps) {
  const [currentStep, setCurrentStep] = useState(1);
  const [selectedProvider, setSelectedProvider] = useState<string>('');
  const [config, setConfig] = useState({
    entityId: '',
    ssoUrl: '',
    certificate: '',
    emailAttr: 'email',
    firstNameAttr: 'firstName',
    lastNameAttr: 'lastName'
  });
  const [testResult, setTestResult] = useState<'pending' | 'success' | 'error'>('pending');

  const progress = ((currentStep - 1) / (steps.length - 1)) * 100;

  const handleNext = () => {
    if (currentStep < steps.length) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleTestConnection = () => {
    // Simulate test
    setTestResult('success');
  };

  const handleComplete = () => {
    onComplete?.();
  };

  return (
    <div className="space-y-6">
      {/* Progress */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          {steps.map((step, index) => (
            <div key={step.id} className="flex items-center">
              <div className="flex flex-col items-center">
                <div
                  className={`rounded-full h-10 w-10 flex items-center justify-center border-2 ${
                    currentStep > step.id
                      ? 'bg-green-500 border-green-500'
                      : currentStep === step.id
                      ? 'border-primary bg-primary text-primary-foreground'
                      : 'border-muted'
                  }`}
                >
                  {currentStep > step.id ? (
                    <CheckCircle className="h-5 w-5 text-white" />
                  ) : (
                    <span>{step.id}</span>
                  )}
                </div>
                <div className="mt-2 text-center">
                  <p className="text-sm font-medium">{step.title}</p>
                  <p className="text-xs text-muted-foreground">{step.description}</p>
                </div>
              </div>
              {index < steps.length - 1 && (
                <div
                  className={`h-0.5 w-20 mx-4 ${
                    currentStep > step.id ? 'bg-green-500' : 'bg-muted'
                  }`}
                />
              )}
            </div>
          ))}
        </div>
        <Progress value={progress} className="h-2" />
      </div>

      {/* Step Content */}
      <Card>
        {currentStep === 1 && (
          <>
            <CardHeader>
              <CardTitle>Select Identity Provider</CardTitle>
              <CardDescription>
                Choose the identity provider your organization uses for authentication
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {identityProviders.map((provider) => (
                  <button
                    key={provider.id}
                    onClick={() => setSelectedProvider(provider.id)}
                    className={`p-4 rounded-lg border-2 text-left transition-colors ${
                      selectedProvider === provider.id
                        ? 'border-primary bg-primary/5'
                        : 'border-muted hover:border-primary/50'
                    }`}
                  >
                    <p className="font-medium">{provider.name}</p>
                  </button>
                ))}
              </div>
            </CardContent>
          </>
        )}

        {currentStep === 2 && (
          <>
            <CardHeader>
              <CardTitle>Configure Identity Provider</CardTitle>
              <CardDescription>
                Enter your identity provider's SAML configuration
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="entityId">Entity ID / Issuer</Label>
                <Input
                  id="entityId"
                  placeholder="https://idp.example.com/saml"
                  value={config.entityId}
                  onChange={(e) => setConfig({ ...config, entityId: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="ssoUrl">SSO URL</Label>
                <Input
                  id="ssoUrl"
                  placeholder="https://idp.example.com/sso"
                  value={config.ssoUrl}
                  onChange={(e) => setConfig({ ...config, ssoUrl: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="certificate">X.509 Certificate</Label>
                <Textarea
                  id="certificate"
                  placeholder="-----BEGIN CERTIFICATE-----"
                  className="font-mono text-sm h-32"
                  value={config.certificate}
                  onChange={(e) => setConfig({ ...config, certificate: e.target.value })}
                />
              </div>
            </CardContent>
          </>
        )}

        {currentStep === 3 && (
          <>
            <CardHeader>
              <CardTitle>Attribute Mapping</CardTitle>
              <CardDescription>
                Map identity provider attributes to PARWA user fields
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="emailAttr">Email Attribute</Label>
                  <Input
                    id="emailAttr"
                    value={config.emailAttr}
                    onChange={(e) => setConfig({ ...config, emailAttr: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="firstNameAttr">First Name Attribute</Label>
                  <Input
                    id="firstNameAttr"
                    value={config.firstNameAttr}
                    onChange={(e) => setConfig({ ...config, firstNameAttr: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="lastNameAttr">Last Name Attribute</Label>
                  <Input
                    id="lastNameAttr"
                    value={config.lastNameAttr}
                    onChange={(e) => setConfig({ ...config, lastNameAttr: e.target.value })}
                  />
                </div>
              </div>
              <Alert>
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Tip</AlertTitle>
                <AlertDescription>
                  These attribute names should match what your IdP sends in the SAML assertion.
                </AlertDescription>
              </Alert>
            </CardContent>
          </>
        )}

        {currentStep === 4 && (
          <>
            <CardHeader>
              <CardTitle>Test & Enable SSO</CardTitle>
              <CardDescription>
                Verify your configuration and enable SSO for your organization
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Button onClick={handleTestConnection} className="w-full">
                Test SSO Connection
              </Button>

              {testResult === 'success' && (
                <Alert className="bg-green-50 border-green-200">
                  <CheckCircle className="h-4 w-4 text-green-600" />
                  <AlertTitle className="text-green-800">Connection Successful</AlertTitle>
                  <AlertDescription className="text-green-700">
                    SSO configuration is valid. You can now enable SSO for your organization.
                  </AlertDescription>
                </Alert>
              )}

              {testResult === 'error' && (
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <AlertTitle>Connection Failed</AlertTitle>
                  <AlertDescription>
                    Unable to connect to your identity provider. Please check your configuration.
                  </AlertDescription>
                </Alert>
              )}
            </CardContent>
          </>
        )}

        <CardFooter className="flex justify-between">
          <Button
            variant="outline"
            onClick={currentStep === 1 ? onCancel : handleBack}
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            {currentStep === 1 ? 'Cancel' : 'Back'}
          </Button>
          {currentStep < steps.length ? (
            <Button onClick={handleNext}>
              Next
              <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          ) : (
            <Button onClick={handleComplete} disabled={testResult !== 'success'}>
              Enable SSO
            </Button>
          )}
        </CardFooter>
      </Card>
    </div>
  );
}
