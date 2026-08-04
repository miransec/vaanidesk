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
  description: "Multilingual AI support across chat, voice and images",
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
          <nav className="mx-auto flex w-full max-w-5xl items-center justify-between px-4 py-4">
            <Link href="/" className="font-display text-xl text-slate-900">
              VaaniDesk
            </Link>
            <div className="flex gap-4 text-sm text-slate-700">
              <Link href="/">Home</Link>
              <Link href="/chat">Chat</Link>
              <Link href="/knowledge">Knowledge</Link>
              <Link href="/channels">Channels</Link>
              <Link href="/admin/evaluations">Evaluations</Link>
              <Link href="/admin/observability">Observability</Link>
              <Link href="/admin/audit">Audit</Link>
            </div>
          </nav>
          {children}
        </div>
      </body>
    </html>
  );
}
