# PARWA — AI-Powered Customer Support Platform

## Quick Start

```bash
# 1. Install dependencies
npm install

# 2. Create environment file
cp .env.example .env.local
# Edit .env.local with your API URL and Google Client ID

# 3. Run development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Project Structure

```
src/
├── app/                    # Next.js App Router pages
│   ├── page.tsx            # Landing page (Home)
│   ├── pricing/            # Pricing page with 3 plan tiers
│   ├── models/             # AI Models showcase
│   ├── welcome/            # Post-payment onboarding
│   └── (auth)/             # Login, Signup, Forgot/Reset Password
├── components/
│   ├── landing/            # Landing page components
│   │   ├── NavigationBar   # Sticky nav with mobile menu
│   │   ├── FeatureCarousel # 5-slide Netflix-style carousel
│   │   ├── HeroSection     # Human Support vs PARWA AI
│   │   ├── HowItWorks      # 5-step timeline
│   │   ├── JarvisDemo      # Auto-playing chat demo
│   │   ├── WhyChooseUs     # 6 feature cards
│   │   └── Footer          # Dark footer with links
│   ├── pricing/            # Pricing components
│   ├── auth/               # Login/Signup forms
│   └── onboarding/         # Post-payment onboarding
├── contexts/               # React contexts (Auth)
├── hooks/                  # Custom hooks
├── lib/                    # Utilities and API client
└── types/                  # TypeScript type definitions
```

## Features

- **3 Pricing Tiers**: mini parwa, parwa, high parwa
- **5 Industry Variants**: E-commerce, SaaS, Logistics, Others
- **Full-Slide Animations**: Vivid background animations on every carousel slide
- **Auto-Playing Chat Demo**: Jarvis AI demo that loops automatically
- **Dark/Light Theme**: Parrot green → dark green with black and white
- **Responsive Design**: Mobile-first with sm/md/lg breakpoints
- **Scroll Animations**: Reveal-on-scroll, stagger, fade effects
- **Authentication**: Email/password + Google OAuth
- **Security**: XSS prevention, safe API parsing, input sanitization

## Build for Production

```bash
npm run build
npm start
```

## Tech Stack

- **Next.js 14** (App Router)
- **React 18**
- **TypeScript 5**
- **Tailwind CSS 3.4**
- **Lucide React** (icons)
- **React Hook Form** + **Zod** (validation)
- **Axios** (API client)
- **React Hot Toast** (notifications)
