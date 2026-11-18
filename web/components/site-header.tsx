"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function SiteHeader() {
  const path = usePathname();
  const here = (p: string) => (path === p || path === p.replace(/\/$/, "") ? "page" : undefined);
  return (
    <header className="top">
      <Link href="/" className="mark">SPET</Link>
      <nav aria-label="Site">
        <Link href="/runs/" aria-current={here("/runs/")}>Runs</Link>
        <Link href="/method/" aria-current={here("/method/")}>Method</Link>
        <a href="https://windesheim.co" className="who">Richard Windesheim</a>
      </nav>
    </header>
  );
}
