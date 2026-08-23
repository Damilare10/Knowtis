import type { Metadata, Viewport } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";
import LayoutWrapper from "@/components/layout/layout-wrapper";
import AIChatPopup from "@/components/layout/ai-chat-popup";

const plusJakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700", "800"],
  display: "swap",
  variable: "--font-display",
});

export const metadata: Metadata = {
  title: "Knowtis - AI Academic Assistant",
  description: "Stay informed by filtering noisy university WhatsApp groups and surfacing only relevant academic updates.",
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',
  themeColor: '#FBFBFA',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`h-full antialiased ${plusJakarta.variable}`}>
      <body className="min-h-full flex flex-col">
        <LayoutWrapper>
          {children}
        </LayoutWrapper>
        <AIChatPopup />
      </body>
    </html>
  );
}
