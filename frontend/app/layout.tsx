import type { Metadata, Viewport } from "next";
import { Google_Sans_Flex } from "next/font/google";

import "@copilotkit/react-core/v2/styles.css";
import "./brand.css";
import "./globals.css";
import { Providers } from "./providers";

// App-wide typeface: Google Sans Flex (variable font, self-hosted by next/font). The brand pack's
// "Inter, Helvetica, Arial, sans-serif" stays as the fallback stack via --font.
const appFont = Google_Sans_Flex({ subsets: ["latin"], display: "swap", variable: "--font-app" });

export const metadata: Metadata = {
  title: "Ceylon Compass Holidays",
  description: "Plan, price and book your Sri Lanka trip with Mira.",
  // Favicon: the standard logo on light browser chrome, the white one when the browser is dark.
  icons: {
    icon: [
      { url: "/brand/CeylonCompassHolidays.svg", type: "image/svg+xml", media: "(prefers-color-scheme: light)" },
      { url: "/brand/CeylonCompassHolidays-white.svg", type: "image/svg+xml", media: "(prefers-color-scheme: dark)" },
    ],
  },
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={appFont.variable}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
