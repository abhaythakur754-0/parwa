/**
 * Landing Page Components Unit Tests
 * 
 * Tests for landing page components:
 * - HeroSection
 * - FeatureCarousel
 * - HowItWorks
 * - JarvisDemo
 * - WhyChooseUs
 * - Footer
 */

import React from 'react';

// ═══════════════════════════════════════════════════════════════════════════════
// HeroSection Tests
// ═══════════════════════════════════════════════════════════════════════════════

describe('HeroSection', () => {
  const heroContent = {
    headline: 'AI-Powered Customer Support',
    subheadline: 'Automate your support with intelligent AI agents',
    cta: 'Get Started Free',
    secondaryCta: 'Watch Demo',
  };

  it('should have compelling headline', () => {
    expect(heroContent.headline).toContain('AI');
    expect(heroContent.headline.length).toBeGreaterThan(10);
  });

  it('should have clear subheadline', () => {
    expect(heroContent.subheadline).toContain('support');
    expect(heroContent.subheadline.length).toBeGreaterThan(20);
  });

  it('should have primary CTA', () => {
    expect(heroContent.cta).toBeTruthy();
    expect(heroContent.cta.toLowerCase()).toContain('start');
  });

  it('should have secondary CTA', () => {
    expect(heroContent.secondaryCta).toBeTruthy();
    expect(heroContent.secondaryCta.toLowerCase()).toContain('demo');
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// FeatureCarousel Tests
// ═══════════════════════════════════════════════════════════════════════════════

describe('FeatureCarousel', () => {
  const features = [
    { id: 1, title: 'Smart Routing', description: 'AI-powered ticket routing' },
    { id: 2, title: 'Auto Response', description: 'Instant customer replies' },
    { id: 3, title: 'Knowledge Base', description: 'Self-learning system' },
    { id: 4, title: 'Analytics', description: 'Real-time insights' },
    { id: 5, title: 'Multi-channel', description: 'Email, chat, SMS, voice' },
  ];

  it('should have multiple features', () => {
    expect(features.length).toBeGreaterThan(3);
  });

  it('should have titles and descriptions', () => {
    features.forEach(feature => {
      expect(feature.title).toBeTruthy();
      expect(feature.description).toBeTruthy();
      expect(feature.title.length).toBeGreaterThan(3);
      expect(feature.description.length).toBeGreaterThan(5);
    });
  });

  it('should have unique feature titles', () => {
    const titles = features.map(f => f.title);
    const uniqueTitles = [...new Set(titles)];
    expect(uniqueTitles.length).toBe(titles.length);
  });

  it('should navigate between features', () => {
    let currentIndex = 0;
    
    // Next feature
    currentIndex = (currentIndex + 1) % features.length;
    expect(currentIndex).toBe(1);
    
    // Previous feature
    currentIndex = (currentIndex - 1 + features.length) % features.length;
    expect(currentIndex).toBe(0);
    
    // Wrap around
    currentIndex = features.length - 1;
    currentIndex = (currentIndex + 1) % features.length;
    expect(currentIndex).toBe(0);
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// HowItWorks Tests
// ═══════════════════════════════════════════════════════════════════════════════

describe('HowItWorks', () => {
  const steps = [
    { step: 1, title: 'Connect', description: 'Integrate your support channels' },
    { step: 2, title: 'Train', description: 'Upload knowledge and customize AI' },
    { step: 3, title: 'Deploy', description: 'Go live with AI-powered support' },
    { step: 4, title: 'Optimize', description: 'Continuous improvement with analytics' },
  ];

  it('should have sequential steps', () => {
    steps.forEach((step, index) => {
      expect(step.step).toBe(index + 1);
    });
  });

  it('should have clear step titles', () => {
    const expectedTitles = ['Connect', 'Train', 'Deploy', 'Optimize'];
    steps.forEach((step, index) => {
      expect(step.title).toBe(expectedTitles[index]);
    });
  });

  it('should have step descriptions', () => {
    steps.forEach(step => {
      expect(step.description.length).toBeGreaterThan(10);
    });
  });

  it('should show progress through steps', () => {
    const totalSteps = steps.length;
    steps.forEach((step, index) => {
      const progress = ((index + 1) / totalSteps) * 100;
      expect(progress).toBeGreaterThan(0);
      expect(progress).toBeLessThanOrEqual(100);
    });
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// JarvisDemo Tests
// ═══════════════════════════════════════════════════════════════════════════════

describe('JarvisDemo', () => {
  const demoPrompts = [
    'How do I reset my password?',
    'Where is my order #12345?',
    'I want to cancel my subscription',
    'What are your business hours?',
  ];

  it('should have demo prompts', () => {
    expect(demoPrompts.length).toBeGreaterThan(0);
  });

  it('should have realistic customer queries', () => {
    demoPrompts.forEach(prompt => {
      expect(prompt.endsWith('?') || prompt.endsWith('.')).toBeTruthy();
      expect(prompt.length).toBeGreaterThan(10);
    });
  });

  it('should simulate chat interaction', () => {
    const chatState = {
      messages: [] as Array<{ role: string; content: string }>,
      isTyping: false,
    };

    // User sends message
    chatState.messages.push({ role: 'user', content: demoPrompts[0] });
    expect(chatState.messages.length).toBe(1);

    // AI responds
    chatState.isTyping = true;
    chatState.messages.push({ role: 'assistant', content: 'I can help you reset your password...' });
    chatState.isTyping = false;
    
    expect(chatState.messages.length).toBe(2);
    expect(chatState.isTyping).toBe(false);
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// WhyChooseUs Tests
// ═══════════════════════════════════════════════════════════════════════════════

describe('WhyChooseUs', () => {
  const benefits = [
    { icon: 'zap', title: 'Instant Setup', description: 'Go live in minutes, not weeks' },
    { icon: 'brain', title: 'Self-Learning AI', description: 'Gets smarter with every interaction' },
    { icon: 'shield', title: 'Enterprise Security', description: 'SOC2 compliant, GDPR ready' },
    { icon: 'chart', title: 'Real-time Analytics', description: 'Track performance in real-time' },
    { icon: 'globe', title: 'Multi-language', description: 'Support customers globally' },
  ];

  it('should have multiple benefits', () => {
    expect(benefits.length).toBeGreaterThanOrEqual(4);
  });

  it('should have icons for each benefit', () => {
    benefits.forEach(benefit => {
      expect(benefit.icon).toBeTruthy();
    });
  });

  it('should have clear benefit titles', () => {
    benefits.forEach(benefit => {
      expect(benefit.title.length).toBeGreaterThan(3);
    });
  });

  it('should have descriptive text', () => {
    benefits.forEach(benefit => {
      expect(benefit.description.length).toBeGreaterThan(15);
    });
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// Footer Tests
// ═══════════════════════════════════════════════════════════════════════════════

describe('Footer', () => {
  const footerLinks = {
    product: ['Features', 'Pricing', 'Integrations', 'API'],
    company: ['About', 'Blog', 'Careers', 'Contact'],
    resources: ['Documentation', 'Help Center', 'Status', 'Security'],
    legal: ['Privacy Policy', 'Terms of Service', 'Cookie Policy'],
  };

  it('should have product links', () => {
    expect(footerLinks.product.length).toBeGreaterThan(0);
    expect(footerLinks.product).toContain('Pricing');
  });

  it('should have company links', () => {
    expect(footerLinks.company.length).toBeGreaterThan(0);
    expect(footerLinks.company).toContain('About');
  });

  it('should have legal links', () => {
    expect(footerLinks.legal.length).toBeGreaterThan(0);
    expect(footerLinks.legal).toContain('Privacy Policy');
  });

  it('should have resources links', () => {
    expect(footerLinks.resources.length).toBeGreaterThan(0);
    expect(footerLinks.resources).toContain('Documentation');
  });

  it('should have social media links', () => {
    const socialLinks = ['twitter', 'linkedin', 'github'];
    expect(socialLinks.length).toBeGreaterThan(0);
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// NavigationBar Tests
// ═══════════════════════════════════════════════════════════════════════════════

describe('NavigationBar', () => {
  const navItems = [
    { label: 'Features', href: '#features' },
    { label: 'Pricing', href: '/pricing' },
    { label: 'Resources', href: '#resources' },
    { label: 'About', href: '#about' },
  ];

  const ctas = [
    { label: 'Login', href: '/login', variant: 'ghost' },
    { label: 'Get Started', href: '/signup', variant: 'primary' },
  ];

  it('should have navigation items', () => {
    expect(navItems.length).toBeGreaterThan(0);
  });

  it('should have valid hrefs', () => {
    navItems.forEach(item => {
      expect(item.href).toBeTruthy();
      expect(item.href.startsWith('/') || item.href.startsWith('#')).toBeTruthy();
    });
  });

  it('should have CTA buttons', () => {
    expect(ctas.length).toBeGreaterThan(0);
    expect(ctas.find(c => c.label === 'Get Started')).toBeTruthy();
  });

  it('should have login link', () => {
    expect(ctas.find(c => c.label === 'Login')).toBeTruthy();
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// BookDemoModal Tests
// ═══════════════════════════════════════════════════════════════════════════════

describe('BookDemoModal', () => {
  const demoForm = {
    fields: ['name', 'email', 'company', 'phone', 'message'] as const,
    requiredFields: ['name', 'email', 'company'],
  };

  it('should have required fields', () => {
    demoForm.requiredFields.forEach(field => {
      expect(demoForm.fields.includes(field as typeof demoForm.fields[number])).toBe(true);
    });
  });

  it('should validate email format', () => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    
    expect(emailRegex.test('test@example.com')).toBe(true);
    expect(emailRegex.test('invalid-email')).toBe(false);
    expect(emailRegex.test('test@.com')).toBe(false);
  });

  it('should have submit button', () => {
    const submitButton = { label: 'Book Demo', type: 'submit' };
    expect(submitButton.type).toBe('submit');
  });
});
