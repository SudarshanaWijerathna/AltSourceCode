import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";

import "@copilotkit/react-core/v2/styles.css";
import "./brand.css";
import "./globals.css";
import { Providers } from "./providers";

// Brand pack font: "Inter, Helvetica, Arial, sans-serif" (Inter self-hosted by next/font).
const inter = Inter({ subsets: ["latin"], weight: ["400", "600", "700"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Ceylon Compass Holidays",
  description: "Plan, price and book your Sri Lanka trip with Mira.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
