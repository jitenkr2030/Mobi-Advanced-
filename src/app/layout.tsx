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
  title: "Mobi Invoice - AI-Powered Business Management Platform",
  description: "Complete AI-powered invoice and business management platform. Mobile-responsive design with advanced features including OCR, fraud detection, predictive analytics, and automation. Built for modern businesses.",
  keywords: ["Mobi Invoice", "AI-powered", "Business Management", "Mobile Responsive", "Invoice OCR", "Fraud Detection", "Predictive Analytics", "Next.js", "TypeScript", "Tailwind CSS", "React"],
  authors: [{ name: "Mobi Invoice Team" }],
  icons: {
    icon: "https://z-cdn.chatglm.cn/z-ai/static/logo.svg",
    apple: "https://z-cdn.chatglm.cn/z-ai/static/logo.svg",
  },
  openGraph: {
    title: "Mobi Invoice - AI-Powered Business Platform",
    description: "Mobile-responsive AI-powered invoice and business management platform with advanced automation features",
    url: "https://chat.z.ai",
    siteName: "Mobi Invoice",
    type: "website",
    images: [
      {
        url: "https://z-cdn.chatglm.cn/z-ai/static/logo.svg",
        width: 1200,
        height: 630,
        alt: "Mobi Invoice - AI-Powered Business Platform",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Mobi Invoice - AI-Powered Business Platform",
    description: "Mobile-responsive AI-powered invoice and business management platform",
    images: ["https://z-cdn.chatglm.cn/z-ai/static/logo.svg"],
  },
  viewport: {
    width: "device-width",
    initialScale: 1,
    maximumScale: 5,
    userScalable: true,
  },
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#09090b" },
  ],
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "Mobi Invoice",
  },
  formatDetection: {
    telephone: false,
  },
  metadataBase: new URL("https://chat.z.ai"),
  alternates: {
    canonical: "https://chat.z.ai",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
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
