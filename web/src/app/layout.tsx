import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
  display: "swap",
  preload: true,
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  display: "swap",
  preload: true,
});

export const viewport: Viewport = {
  themeColor: "#060611",
  width: "device-width",
  initialScale: 1,
};

export const metadata: Metadata = {
  title: "CyberSim Monitor — Nimbus Threat Range",
  description:
    "Real-time cloud infrastructure monitoring and cyber attack simulation dashboard. " +
    "Visualize VMs, containers, IDS alerts, firewall rules, and network topology in a premium dark-mode interface.",
  keywords: [
    "cloud simulator",
    "cybersecurity",
    "IDS",
    "intrusion detection",
    "firewall",
    "attack simulation",
    "dashboard",
    "SOC",
    "security operations",
    "network topology",
  ],
  authors: [{ name: "Cloud Simulator Team" }],
  robots: "noindex, nofollow",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className={`${inter.variable} ${jetbrainsMono.variable} antialiased`}>
        {children}
      </body>
    </html>
  );
}
