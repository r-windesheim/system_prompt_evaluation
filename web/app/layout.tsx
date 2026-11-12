import type { Metadata } from "next";
import { Instrument_Sans, JetBrains_Mono } from "next/font/google";
import Link from "next/link";
import { Providers } from "@/components/providers";
import { hasApi } from "@/lib/api";
import { REPO_URL } from "@/lib/site";
import "./globals.css";

const sans = Instrument_Sans({ subsets: ["latin"], variable: "--font-instrument", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jetbrains", display: "swap" });

export const metadata: Metadata = {
  title: { default: "SPET: which part of your system prompt did that?", template: "%s · SPET" },
  description:
    "Remove one section of a system prompt at a time, regenerate, and measure which stylistic quirks move, with confidence intervals.",
};



export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`}>
      <body className="min-h-dvh">
        <Providers>
          <header className="mx-auto flex max-w-[1240px] items-baseline justify-between px-6 pt-6 pb-4">
            <Link href="/" className="text-[15px] font-semibold tracking-tight">
              spet
            </Link>
            <nav className="flex gap-6 text-[14px] text-graphite">
              <Link href="/analyze/" className={hasApi ? "font-medium text-ink" : "hover:text-ink"}>Analyse a prompt</Link>
              <Link href="/" className="hover:text-ink">Runs</Link>
              <Link href="/method/" className="hover:text-ink">Method</Link>
              <a href={REPO_URL} className="hover:text-ink">Source</a>
            </nav>
          </header>
          <main className="mx-auto max-w-[1240px] px-6 pb-24">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
