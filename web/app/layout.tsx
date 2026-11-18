import type { Metadata } from "next";
import { Geist, Source_Serif_4 } from "next/font/google";
import { Providers } from "@/components/providers";
import { SiteHeader } from "@/components/site-header";
import "./globals.css";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist", display: "swap" });
const serif = Source_Serif_4({ subsets: ["latin"], axes: ["opsz"], variable: "--font-serif-4", display: "swap" });

export const metadata: Metadata = {
  title: { default: "SPET: what each part of a system prompt changes", template: "%s · SPET" },
  description:
    "Take each part of a system prompt out in turn, ask the model the same questions again, and see which habits change.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geist.variable} ${serif.variable}`}>
      <body>
        <Providers>
          <div className="stage">
            <SiteHeader />
            <main>{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
