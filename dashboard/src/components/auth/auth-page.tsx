'use client';

import { useState } from 'react';
import { useAppStore } from '@/lib/store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Zap, Mail, Lock, User, Building2, Eye, EyeOff } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export function AuthPage() {
  const { login, signup, loginWithGoogle, isLoading } = useAppStore();
  const [isSignUp, setIsSignUp] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [company, setCompany] = useState('');
  const [forgotPassword, setForgotPassword] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (forgotPassword) {
      // Simulate forgot password
      setForgotPassword(false);
      return;
    }
    if (isSignUp) {
      await signup(name, email, password, company);
    } else {
      await login(email, password);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-emerald-50 via-white to-amber-50 dark:from-gray-950 dark:via-gray-900 dark:to-gray-950 p-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md"
      >
        <div className="flex items-center justify-center gap-3 mb-8">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-600 text-white shadow-lg">
            <Zap className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Parwa</h1>
            <p className="text-sm text-muted-foreground">Variant Engine Dashboard</p>
          </div>
        </div>

        <Card className="shadow-xl border-border/50">
          <AnimatePresence mode="wait">
            <motion.div
              key={forgotPassword ? 'forgot' : isSignUp ? 'signup' : 'login'}
              initial={{ opacity: 0, x: isSignUp ? 20 : -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: isSignUp ? -20 : 20 }}
              transition={{ duration: 0.2 }}
            >
              <CardHeader className="text-center">
                <CardTitle className="text-xl">
                  {forgotPassword ? 'Reset Password' : isSignUp ? 'Create Account' : 'Welcome Back'}
                </CardTitle>
                <CardDescription>
                  {forgotPassword
                    ? 'Enter your email to receive a reset link'
                    : isSignUp
                    ? 'Set up your Parwa account'
                    : 'Sign in to your Parwa dashboard'}
                </CardDescription>
              </CardHeader>

              <form onSubmit={handleSubmit}>
                <CardContent className="space-y-4">
                  {forgotPassword ? (
                    <div className="space-y-2">
                      <Label htmlFor="reset-email">Email</Label>
                      <div className="relative">
                        <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                        <Input
                          id="reset-email"
                          type="email"
                          placeholder="admin@parwa.ai"
                          value={email}
                          onChange={e => setEmail(e.target.value)}
                          className="pl-10"
                          required
                        />
                      </div>
                    </div>
                  ) : (
                    <>
                      {isSignUp && (
                        <>
                          <div className="space-y-2">
                            <Label htmlFor="name">Full Name</Label>
                            <div className="relative">
                              <User className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                              <Input
                                id="name"
                                placeholder="Sarah Chen"
                                value={name}
                                onChange={e => setName(e.target.value)}
                                className="pl-10"
                                required
                              />
                            </div>
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="company">Company Name</Label>
                            <div className="relative">
                              <Building2 className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                              <Input
                                id="company"
                                placeholder="Parwa Corp"
                                value={company}
                                onChange={e => setCompany(e.target.value)}
                                className="pl-10"
                                required
                              />
                            </div>
                          </div>
                        </>
                      )}
                      <div className="space-y-2">
                        <Label htmlFor="email">Email</Label>
                        <div className="relative">
                          <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                          <Input
                            id="email"
                            type="email"
                            placeholder="admin@parwa.ai"
                            value={email}
                            onChange={e => setEmail(e.target.value)}
                            className="pl-10"
                            required
                          />
                        </div>
                      </div>
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <Label htmlFor="password">Password</Label>
                          {!isSignUp && (
                            <button
                              type="button"
                              onClick={() => setForgotPassword(true)}
                              className="text-xs text-emerald-600 hover:text-emerald-700 dark:text-emerald-400"
                            >
                              Forgot password?
                            </button>
                          )}
                        </div>
                        <div className="relative">
                          <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                          <Input
                            id="password"
                            type={showPassword ? 'text' : 'password'}
                            placeholder="••••••••"
                            value={password}
                            onChange={e => setPassword(e.target.value)}
                            className="pl-10 pr-10"
                            required
                          />
                          <button
                            type="button"
                            onClick={() => setShowPassword(!showPassword)}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                          >
                            {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                          </button>
                        </div>
                      </div>
                    </>
                  )}
                </CardContent>

                <CardFooter className="flex flex-col gap-3">
                  <Button
                    type="submit"
                    className="w-full bg-emerald-600 hover:bg-emerald-700 text-white"
                    disabled={isLoading}
                  >
                    {isLoading ? (
                      <div className="flex items-center gap-2">
                        <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                        {forgotPassword ? 'Sending...' : isSignUp ? 'Creating Account...' : 'Signing In...'}
                      </div>
                    ) : (
                      forgotPassword ? 'Send Reset Link' : isSignUp ? 'Create Account' : 'Sign In'
                    )}
                  </Button>

                  {!forgotPassword && (
                    <>
                      <div className="relative w-full">
                        <div className="absolute inset-0 flex items-center">
                          <span className="w-full border-t" />
                        </div>
                        <div className="relative flex justify-center text-xs uppercase">
                          <span className="bg-card px-2 text-muted-foreground">or</span>
                        </div>
                      </div>

                      <Button
                        type="button"
                        variant="outline"
                        className="w-full"
                        onClick={loginWithGoogle}
                        disabled={isLoading}
                      >
                        <svg className="mr-2 h-4 w-4" viewBox="0 0 24 24">
                          <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
                          <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                          <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                          <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
                        </svg>
                        Continue with Google
                      </Button>
                    </>
                  )}

                  {forgotPassword ? (
                    <button
                      type="button"
                      onClick={() => setForgotPassword(false)}
                      className="text-sm text-emerald-600 hover:text-emerald-700 dark:text-emerald-400"
                    >
                      Back to Sign In
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setIsSignUp(!isSignUp)}
                      className="text-sm text-muted-foreground"
                    >
                      {isSignUp ? 'Already have an account? ' : "Don't have an account? "}
                      <span className="text-emerald-600 hover:text-emerald-700 dark:text-emerald-400 font-medium">
                        {isSignUp ? 'Sign In' : 'Sign Up'}
                      </span>
                    </button>
                  )}
                </CardFooter>
              </form>
            </motion.div>
          </AnimatePresence>
        </Card>

        <p className="text-center text-xs text-muted-foreground mt-4">
          By continuing, you agree to Parwa&apos;s Terms of Service and Privacy Policy
        </p>
      </motion.div>
    </div>
  );
}
