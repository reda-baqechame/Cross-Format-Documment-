import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import type { ReactNode } from "react";

import { Providers } from "@/app/providers";
import "@/styles/globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "DocOS — client packet readiness & document trust",
  description:
    "Upload proposals, SOWs, contracts, and invoices. DocOS checks scope, payment, signature, and export risks before you send.",
  manifest: "/manifest.webmanifest",
  icons: { icon: "/icon.svg" },
  appleWebApp: {
    capable: true,
    title: "DocOS",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  themeColor: "#2451e6",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
