import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "PARWA - AI-Powered Customer Support Platform",
  description: "Transform your customer support with PARWA. AI-powered ticket routing, knowledge base search, and 30+ integrations. Save up to 70% compared to hiring human agents.",
  keywords: ["PARWA", "AI", "Customer Support", "Helpdesk", "Automation", "Next.js", "TypeScript"],
  authors: [{ name: "PARWA Team" }],
  icons: {
    icon: "/logo.svg",
  },
  openGraph: {
    title: "PARWA - AI-Powered Customer Support",
    description: "Transform your customer support with intelligent AI",
    siteName: "PARWA",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "PARWA - AI-Powered Customer Support",
    description: "Transform your customer support with intelligent AI",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-background text-foreground`}
      >
        {children}
        <Toaster />
      </body>
    </html>
  );
}
