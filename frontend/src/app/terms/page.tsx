import { Metadata } from 'next';
import Link from 'next/link';
import AppLogo from '@/components/ui/app-logo';

export const metadata: Metadata = {
  title: 'Terms of Use | Knowtis',
  description: 'Knowtis Terms of Use - Please read before using our service.',
};

export default function TermsPage() {
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
            Terms of Use
          </h1>
          
          <p className="text-[14px] font-medium leading-relaxed text-[#686862] mb-8">
            Effective date: June 30, 2026. Please read these terms carefully before using Knowtis.
          </p>

          <div className="space-y-6 text-[14px] font-medium text-[#686862] leading-relaxed">
            <section>
              <h2 className="text-[16px] font-black text-[#171717] mb-2">1. Acceptance of Terms</h2>
              <p>By creating an account and using Knowtis, you agree to these Terms of Use. If you do not agree, do not use the service.</p>
            </section>

            <section>
              <h2 className="text-[16px] font-black text-[#171717] mb-2">2. Eligibility</h2>
              <p>You must be at least 13 years old (or the minimum age in your jurisdiction) to use Knowtis. By registering, you represent that you meet this requirement.</p>
            </section>

            <section>
              <h2 className="text-[16px] font-black text-[#171717] mb-2">3. Account Responsibilities</h2>
              <p>You are responsible for maintaining the confidentiality of your account credentials and for all activity under your account. Notify us immediately of any unauthorized use.</p>
            </section>

            <section>
              <h2 className="text-[16px] font-black text-[#171717] mb-2">4. Acceptable Use</h2>
              <p>You agree not to use Knowtis for any unlawful purpose, to impersonate others, to spam or harass users, to reverse-engineer the service, or to interfere with the platform's operation.</p>
            </section>

            <section>
              <h2 className="text-[16px] font-black text-[#171717] mb-2">5. WhatsApp Integration</h2>
              <p>If you connect WhatsApp groups, you must have authorization to do so. Knowtis processes group metadata and academic messages to detect deadlines and announcements. You are responsible for compliance with WhatsApp's Terms of Service.</p>
            </section>

            <section>
              <h2 className="text-[16px] font-black text-[#171717] mb-2">6. Intellectual Property</h2>
              <p>Knowtis and its original content, features, and functionality are owned by Knowtis and protected by international copyright, trademark, and other intellectual property laws.</p>
            </section>

            <section>
              <h2 className="text-[16px] font-black text-[#171717] mb-2">7. Disclaimers</h2>
              <p>Knowtis is provided "as is" without warranties of any kind. We do not guarantee uninterrupted or error-free service, or that extracted academic information is always accurate.</p>
            </section>

            <section>
              <h2 className="text-[16px] font-black text-[#171717] mb-2">8. Limitation of Liability</h2>
              <p>To the maximum extent permitted by law, Knowtis shall not be liable for any indirect, incidental, special, or consequential damages arising from your use of the service.</p>
            </section>

            <section>
              <h2 className="text-[16px] font-black text-[#171717] mb-2">9. Termination</h2>
              <p>We may suspend or terminate your account for violation of these terms. You may delete your account at any time through the app settings.</p>
            </section>

            <section>
              <h2 className="text-[16px] font-black text-[#171717] mb-2">10. Changes to Terms</h2>
              <p>We may update these terms periodically. Continued use after changes constitutes acceptance. We will notify you of material changes via the app or email.</p>
            </section>

            <section>
              <h2 className="text-[16px] font-black text-[#171717] mb-2">11. Governing Law</h2>
              <p>These terms are governed by the laws of the jurisdiction where Knowtis operates, without regard to conflict of law principles.</p>
            </section>

            <section>
              <h2 className="text-[16px] font-black text-[#171717] mb-2">12. Contact</h2>
              <p>For questions about these terms, contact the Knowtis team through the official support channel in the app or on the project website.</p>
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