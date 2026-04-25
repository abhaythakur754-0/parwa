'use client';

import { useState, useEffect, useRef } from 'react';

// ── Types ────────────────────────────────────────────────────────────────

type DemoVariant = 'mini_parwa' | 'parwa' | 'high_parwa';
type Industry = 'ecommerce' | 'saas' | 'logistics' | 'healthcare';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  latency_ms?: number;
  features_used?: string[];
}

interface DemoSession {
  session_id: string;
  variant: DemoVariant;
  variant_display_name: string;
  industry: Industry;
  max_messages: number;
  features: string[];
  status: string;
  message: string;
}

interface DemoResult {
  success: boolean;
  ai_response: string;
  confidence: number;
  latency_ms: number;
  features_used: string[];
  remaining_messages: number;
  variant_capabilities: {
    variant: string;
    display_name: string;
    features: string[];
    voice_enabled: boolean;
    web_search_enabled: boolean;
    web_results?: Array<{ name: string; snippet: string; url: string }>;
  };
}

// ── Variant Capabilities ───────────────────────────────────────────────────

const VARIANT_INFO = {
  mini_parwa: {
    name: 'Mini Parwa',
    price: '$999/mo',
    color: 'bg-orange-500',
    borderColor: 'border-orange-500',
    description: 'Perfect for small businesses starting with AI support',
    features: ['Basic AI Chat', 'FAQ Handling', 'Simple Routing', 'Email Support'],
    maxMessages: 20,
    voiceEnabled: false,
    webSearchEnabled: false,
  },
  parwa: {
    name: 'Parwa',
    price: '$2,499/mo',
    color: 'bg-blue-500',
    borderColor: 'border-blue-500',
    description: 'Ideal for growing businesses with complex support needs',
    features: ['Advanced AI Chat', 'Multi-channel Support', 'Smart Routing', 'SMS Integration', 'Voice Preview', 'Knowledge Base'],
    maxMessages: 50,
    voiceEnabled: true,
    webSearchEnabled: true,
  },
  high_parwa: {
    name: 'High Parwa',
    price: '$3,999/mo',
    color: 'bg-purple-500',
    borderColor: 'border-purple-500',
    description: 'Enterprise-grade AI with full capabilities',
    features: ['Premium AI Chat', 'All Channels', 'Priority Routing', 'Full Voice Demo', 'Web Search', 'Image Generation', 'Advanced Analytics', 'Custom Guardrails', 'Brand Voice'],
    maxMessages: 100,
    voiceEnabled: true,
    webSearchEnabled: true,
  },
};

const INDUSTRIES = [
  { id: 'ecommerce', name: 'E-commerce', icon: '🛒' },
  { id: 'saas', name: 'SaaS', icon: '💻' },
  { id: 'logistics', name: 'Logistics', icon: '🚚' },
  { id: 'healthcare', name: 'Healthcare', icon: '🏥' },
];

// ── Main Demo Page Component ──────────────────────────────────────────────

export default function DemoPage() {
  const [selectedVariant, setSelectedVariant] = useState<DemoVariant>('parwa');
  const [selectedIndustry, setSelectedIndustry] = useState<Industry>('ecommerce');
  const [session, setSession] = useState<DemoSession | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [remainingMessages, setRemainingMessages] = useState(0);
  const [showResults, setShowResults] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Create session when variant changes
  const createSession = async () => {
    try {
      const response = await fetch('/api/demo/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          variant: selectedVariant,
          industry: selectedIndustry,
        }),
      });

      const data = await response.json();
      setSession(data);
      setMessages([]);
      setRemainingMessages(data.max_messages);
      setShowResults(false);
    } catch (error) {
      console.error('Failed to create session:', error);
    }
  };

  // Send message
  const sendMessage = async () => {
    if (!inputMessage.trim() || !session || isLoading) return;

    const userMessage: Message = {
      role: 'user',
      content: inputMessage,
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await fetch('/api/demo/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: session.session_id,
          message: inputMessage,
        }),
      });

      const data: DemoResult = await response.json();

      if (data.success) {
        const assistantMessage: Message = {
          role: 'assistant',
          content: data.ai_response,
          timestamp: new Date().toISOString(),
          latency_ms: data.latency_ms,
          features_used: data.features_used,
        };

        setMessages(prev => [...prev, assistantMessage]);
        setRemainingMessages(data.remaining_messages);
      } else {
        // Handle error
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: 'Sorry, I encountered an error. Please try again.',
          timestamp: new Date().toISOString(),
        }]);
      }
    } catch (error) {
      console.error('Chat error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Complete demo and show results
  const completeDemo = async () => {
    if (!session) return;

    try {
      await fetch(`/api/demo/complete/${session.session_id}`, {
        method: 'POST',
      });
      setShowResults(true);
    } catch (error) {
      console.error('Failed to complete demo:', error);
    }
  };

  // Reset demo
  const resetDemo = () => {
    setSession(null);
    setMessages([]);
    setShowResults(false);
    setRemainingMessages(0);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="text-2xl font-bold text-gray-900">PARWA</div>
              <span className="px-3 py-1 text-sm font-medium bg-blue-100 text-blue-800 rounded-full">
                Demo Mode
              </span>
            </div>
            <a href="/pricing" className="text-blue-600 hover:text-blue-800 font-medium">
              View Pricing →
            </a>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        {/* Hero Section */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Experience PARWA AI Before You Buy
          </h1>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto">
            Test our AI assistant with different variant capabilities.
            See how PARWA can transform your customer support.
          </p>
        </div>

        {/* Variant Selector */}
        {!session && (
          <div className="mb-8">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Choose a Variant to Demo</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {(Object.keys(VARIANT_INFO) as DemoVariant[]).map((variant) => {
                const info = VARIANT_INFO[variant];
                return (
                  <button
                    key={variant}
                    onClick={() => setSelectedVariant(variant)}
                    className={`p-6 rounded-xl border-2 transition-all ${
                      selectedVariant === variant
                        ? `${info.borderColor} bg-white shadow-lg`
                        : 'border-gray-200 bg-white hover:border-gray-300'
                    }`}
                  >
                    <div className={`inline-block px-3 py-1 rounded-full text-white text-sm font-medium ${info.color} mb-3`}>
                      {info.price}
                    </div>
                    <h3 className="text-xl font-bold text-gray-900 mb-2">{info.name}</h3>
                    <p className="text-gray-600 text-sm mb-4">{info.description}</p>
                    <ul className="text-left space-y-2">
                      {info.features.slice(0, 4).map((feature, i) => (
                        <li key={i} className="flex items-center text-sm text-gray-700">
                          <span className="text-green-500 mr-2">✓</span>
                          {feature}
                        </li>
                      ))}
                      {info.features.length > 4 && (
                        <li className="text-sm text-gray-500">+{info.features.length - 4} more features</li>
                      )}
                    </ul>
                  </button>
                );
              })}
            </div>

            {/* Industry Selector */}
            <div className="mt-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-3">Select Your Industry</h3>
              <div className="flex flex-wrap gap-3">
                {INDUSTRIES.map((industry) => (
                  <button
                    key={industry.id}
                    onClick={() => setSelectedIndustry(industry.id as Industry)}
                    className={`px-4 py-2 rounded-lg border-2 transition-all ${
                      selectedIndustry === industry.id
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-gray-200 bg-white text-gray-700 hover:border-gray-300'
                    }`}
                  >
                    <span className="mr-2">{industry.icon}</span>
                    {industry.name}
                  </button>
                ))}
              </div>
            </div>

            {/* Start Demo Button */}
            <div className="mt-8 text-center">
              <button
                onClick={createSession}
                className="px-8 py-4 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 transition-all shadow-lg hover:shadow-xl text-lg"
              >
                Start {VARIANT_INFO[selectedVariant].name} Demo →
              </button>
            </div>
          </div>
        )}

        {/* Chat Interface */}
        {session && !showResults && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Chat Area */}
            <div className="lg:col-span-2">
              <div className="bg-white rounded-xl shadow-lg overflow-hidden">
                {/* Chat Header */}
                <div className={`${VARIANT_INFO[selectedVariant].color} px-6 py-4 text-white`}>
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-semibold">{VARIANT_INFO[selectedVariant].name} Demo</h3>
                      <p className="text-sm opacity-80">Industry: {selectedIndustry}</p>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-bold">{remainingMessages}</div>
                      <div className="text-sm opacity-80">messages left</div>
                    </div>
                  </div>
                </div>

                {/* Messages */}
                <div className="h-96 overflow-y-auto p-4 space-y-4">
                  {messages.length === 0 && (
                    <div className="text-center text-gray-500 py-8">
                      <p className="text-lg">Start chatting with our AI assistant!</p>
                      <p className="text-sm mt-2">Try asking about orders, refunds, or product recommendations.</p>
                    </div>
                  )}
                  {messages.map((msg, i) => (
                    <div
                      key={i}
                      className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`max-w-[80%] rounded-lg px-4 py-2 ${
                          msg.role === 'user'
                            ? 'bg-blue-600 text-white'
                            : 'bg-gray-100 text-gray-900'
                        }`}
                      >
                        <p>{msg.content}</p>
                        {msg.latency_ms && (
                          <p className="text-xs opacity-70 mt-1">
                            {msg.latency_ms.toFixed(0)}ms • {msg.features_used?.join(', ')}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                  {isLoading && (
                    <div className="flex justify-start">
                      <div className="bg-gray-100 rounded-lg px-4 py-2">
                        <div className="flex space-x-2">
                          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                        </div>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>

                {/* Input Area */}
                <div className="border-t border-gray-200 p-4">
                  <div className="flex space-x-3">
                    <input
                      type="text"
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                      placeholder="Type your message..."
                      className="flex-1 border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      disabled={isLoading || remainingMessages <= 0}
                    />
                    <button
                      onClick={sendMessage}
                      disabled={isLoading || !inputMessage.trim() || remainingMessages <= 0}
                      className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Send
                    </button>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="mt-4 flex justify-between">
                <button
                  onClick={resetDemo}
                  className="px-4 py-2 text-gray-600 hover:text-gray-800"
                >
                  ← Try Different Variant
                </button>
                {remainingMessages <= 0 && (
                  <button
                    onClick={completeDemo}
                    className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
                  >
                    View Demo Results →
                  </button>
                )}
              </div>
            </div>

            {/* Features Panel */}
            <div className="lg:col-span-1">
              <div className="bg-white rounded-xl shadow-lg p-6 sticky top-4">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">
                  Current Variant Features
                </h3>
                <ul className="space-y-3">
                  {VARIANT_INFO[selectedVariant].features.map((feature, i) => (
                    <li key={i} className="flex items-center text-gray-700">
                      <span className="text-green-500 mr-2">✓</span>
                      {feature}
                    </li>
                  ))}
                </ul>

                <div className="mt-6 pt-6 border-t border-gray-200">
                  <h4 className="font-medium text-gray-900 mb-3">Quick Stats</h4>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Messages Used:</span>
                      <span className="font-medium">
                        {VARIANT_INFO[selectedVariant].maxMessages - remainingMessages} / {VARIANT_INFO[selectedVariant].maxMessages}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Voice Enabled:</span>
                      <span className="font-medium">{VARIANT_INFO[selectedVariant].voiceEnabled ? '✓' : '✗'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Web Search:</span>
                      <span className="font-medium">{VARIANT_INFO[selectedVariant].webSearchEnabled ? '✓' : '✗'}</span>
                    </div>
                  </div>
                </div>

                <div className="mt-6">
                  <a
                    href="/pricing"
                    className="block w-full px-4 py-3 bg-blue-600 text-white text-center rounded-lg hover:bg-blue-700 font-medium"
                  >
                    Get {VARIANT_INFO[selectedVariant].name} - {VARIANT_INFO[selectedVariant].price}
                  </a>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Results Screen */}
        {showResults && (
          <div className="max-w-2xl mx-auto">
            <div className="bg-white rounded-xl shadow-lg p-8 text-center">
              <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <span className="text-3xl">🎉</span>
              </div>
              <h2 className="text-2xl font-bold text-gray-900 mb-4">Demo Complete!</h2>
              <p className="text-gray-600 mb-6">
                You experienced the power of {VARIANT_INFO[selectedVariant].name}.
                Ready to transform your customer support?
              </p>

              <div className="bg-gray-50 rounded-lg p-6 mb-6">
                <h3 className="font-semibold text-gray-900 mb-3">Your Demo Summary</h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <div className="text-gray-600">Variant Tested</div>
                    <div className="font-medium">{VARIANT_INFO[selectedVariant].name}</div>
                  </div>
                  <div>
                    <div className="text-gray-600">Messages Sent</div>
                    <div className="font-medium">{messages.filter(m => m.role === 'user').length}</div>
                  </div>
                  <div>
                    <div className="text-gray-600">Industry</div>
                    <div className="font-medium capitalize">{selectedIndustry}</div>
                  </div>
                  <div>
                    <div className="text-gray-600">Features Tested</div>
                    <div className="font-medium">AI Chat, {VARIANT_INFO[selectedVariant].webSearchEnabled ? 'Web Search' : 'Basic Routing'}</div>
                  </div>
                </div>
              </div>

              <div className="flex flex-col sm:flex-row gap-4">
                <button
                  onClick={resetDemo}
                  className="flex-1 px-6 py-3 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
                >
                  Try Another Variant
                </button>
                <a
                  href="/pricing"
                  className="flex-1 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium text-center"
                >
                  Start Free Trial →
                </a>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
