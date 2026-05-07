import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Toaster } from "react-hot-toast";
import { AuthProvider } from "@/contexts/AuthContext";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "PARWA — AI-Powered Customer Support",
  description: "PARWA replaces your human support team with intelligent AI agents. 92% cost reduction, 24/7/365 availability, instant from Day 1.",
  icons: {
    icon: "https://z-cdn.chatglm.cn/z-ai/static/logo.svg",
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
        className={`${inter.variable} antialiased`}
        style={{ background: '#0A0A0A' }}
      >
        <AuthProvider>
          {children}
          <Toaster
            position="top-right"
            toastOptions={{
              duration: 4000,
              style: {
                background: '#1A1A1A',
                color: '#fff',
                border: '1px solid rgba(255, 127, 17, 0.15)',
                borderRadius: '12px',
                fontSize: '14px',
                boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
              },
              success: {
                iconTheme: {
                  primary: '#FF7F11',
                  secondary: '#fff',
                },
              },
              error: {
                iconTheme: {
                  primary: '#ef4444',
                  secondary: '#fff',
                },
              },
            }}
          />
        </AuthProvider>
      </body>
    </html>
  );
}
