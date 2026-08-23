import { Metadata } from 'next';
import Link from 'next/link';
import AppLogo from '@/components/ui/app-logo';

export const metadata: Metadata = {
  title: 'Privacy Policy | Knowtis',
  description: 'Knowtis Privacy Policy - How we collect, use, and protect your information.',
};

export default function PrivacyPage() {
  return (
    <main className="min-h-dvh bg-[#FBFBFA] text-[#171717] flex flex-col">
      <header className="px-6 pt-6 pb-4 flex items-center justify-between shrink-0">
        <div className="w-10" />
        <Link href="/" className="inline-flex items-baseline gap-1 text-[18px] font-extrabold tracking-[-0.05em] lowercase mx-auto">
          <span>know</span>
          <span className="text-[#FF5A36]">tis</span>
        </Link>
        <div className="w-10" />
      </header>

      <div className="flex-1 flex flex-col justify-start px-6 pb-24 overflow-y-auto">
        <div className="w-full max-w-[420px] mx-auto pt-4">
          <h1 className="text-[28px] sm:text-[32px] font-black leading-[1.1] tracking-tight text-[#171717] mb-6">
            Privacy Policy
          </h1>
          
          <p className="text-[14px] font-medium leading-relaxed text-[#686862] mb-8">
            Effective date: June 30, 2026. Knowtis helps students filter noisy university WhatsApp groups and surface relevant academic updates.
          </p>

          <div className="space-y-6 text-[14px] font-medium text-[#686862] leading-relaxed">
            <section>
              <h2 className="text-[16px] font-black text-[#171717] mb-2">1. Information We Collect</h2>
              <p>When you register, we collect your email address, username, password, and any optional WhatsApp number you choose to add. We also process data connected to your use of the service, including linked WhatsApp group references, academic events, reminders, notification activity, subscription status, and messages you send through Knowtis AI features.</p>
            </section>

            <section>
              <h2 className="text-[16px] font-black text-[#171717] mb-2">2. How We Use Your Information</h2>
              <p>We use your data to create and secure your account, personalize your dashboard, identify relevant class updates, send reminders and notifications, support WhatsApp-related features, provide AI summaries or chat responses, process billing where applicable, and maintain or improve the service.</p>
            </section>

            <section>
              <h2 className="text-[16px] font-black text-[#171717] mb-2">3. How Your Information Is Stored and Shared</h2>
              <p>Your information is stored on systems used to operate Knowtis. We do not sell your personal information. We may share data only with service providers needed to run the app, such as hosting, authentication, notifications, analytics, payments, and AI processing tools, or when disclosure is required by law or necessary to protect the service and its users.</p>
            </section>

            <section>
              <h2 className="text-[16px] font-black text-[#171717] mb-2">4. WhatsApp and Academic Content</h2>
              <p>If you connect WhatsApp-related features, Knowtis may process group metadata, invite links, and academic messages or updates needed to detect deadlines, tests, class changes, or other relevant school information. You should only connect groups you are authorized to use.</p>
            </section>

            <section>
              <h2 className="text-[16px] font-black text-[#171717] mb-2">5. Your Choices</h2>
              <p>You can update profile details, remove your optional WhatsApp number, or delete your account from the app when those features are available. You may also choose not to use optional features such as AI chat, reminders, billing, or WhatsApp integrations.</p>
            </section>

            <section>
              <h2 className="text-[16px] font-black text-[#171717] mb-2">6. Security and Retention</h2>
              <p>We use reasonable technical and organizational measures to protect your information, but no system is completely secure. We keep information for as long as needed to provide Knowtis, comply with legal obligations, resolve disputes, and enforce our agreements.</p>
            </section>

            <section>
              <h2 className="text-[16px] font-black text-[#171717] mb-2">7. Contact</h2>
              <p>If you have privacy questions or requests, contact the Knowtis team through the official support channel listed in the app or on the project website.</p>
            </section>
          </div>

          <div className="mt-10 pt-6 border-t border-[#E9E9E6] text-center">
            <Link href="/register" className="text-[14px] font-bold text-[#FF5A36] hover:underline">
              Back to Sign Up
            </Link>
          </div>
        </div>
      </div>

      <footer className="shrink-0 px-6 pb-6 text-center">
        <p className="text-xs font-medium text-[#9A9A94]">
          © 2026 Knowtis. All rights reserved.
        </p>
      </footer>
    </main>
  );
}