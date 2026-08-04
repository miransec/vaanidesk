import type { Metadata } from "next";
import { Fraunces, Source_Sans_3 } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const display = Fraunces({
  variable: "--font-display",
  subsets: ["latin"],
});

const sans = Source_Sans_3({
  variable: "--font-sans",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "VaaniDesk",
  description:
    "Multilingual AI customer support that answers policy questions, retrieves customer information, performs approved actions, and escalates safely.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${display.variable} ${sans.variable} min-h-screen antialiased`}>
        <div className="vd-shell min-h-screen">
          <nav className="mx-auto flex w-full max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-4">
            <Link href="/" className="font-display text-xl text-slate-900">
              VaaniDesk
            </Link>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-slate-700">
              <Link href="/chat">Chat</Link>
              <Link href="/account">My Account</Link>
              <Link href="/login">Login</Link>
              <span className="hidden h-4 w-px bg-slate-300 sm:inline-block" aria-hidden />
              <span className="w-full text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400 sm:w-auto">
                Engineering
              </span>
              <Link href="/knowledge" className="text-slate-500 hover:text-slate-800">
                Knowledge
              </Link>
              <Link href="/admin/evaluations" className="text-slate-500 hover:text-slate-800">
                Evaluations
              </Link>
              <Link href="/admin/observability" className="text-slate-500 hover:text-slate-800">
                Observability
              </Link>
              <Link href="/admin/audit" className="text-slate-500 hover:text-slate-800">
                Audit
              </Link>
              <Link href="/channels" className="text-slate-500 hover:text-slate-800">
                Channels
              </Link>
            </div>
          </nav>
          {children}
        </div>
      </body>
    </html>
  );
}
