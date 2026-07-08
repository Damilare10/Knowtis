import type { Metadata, Viewport } from "next";
import "./globals.css";
import LayoutWrapper from "@/components/layout/layout-wrapper";
import AIChatPopup from "@/components/layout/ai-chat-popup";

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
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">
        <LayoutWrapper>
          {children}
        </LayoutWrapper>
        <AIChatPopup />
      </body>
    </html>
  );
}
