import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Kanen Coffee — FedEx Dashboard",
  description: "Shipment tracking and billing audit for Kanen Coffee",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-50 text-gray-900 antialiased">
        {/* Nav */}
        <header className="bg-brand-700 text-white shadow-md">
          <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-6">
            <span className="font-bold text-lg tracking-tight">☕ Kanen Coffee</span>
            <nav className="flex gap-4 text-sm font-medium">
              <Link href="/" className="hover:text-brand-100 transition-colors">Dashboard</Link>
              <Link href="/shipments" className="hover:text-brand-100 transition-colors">Shipments</Link>
              <Link href="/billing" className="hover:text-brand-100 transition-colors">Billing Audit</Link>
            </nav>
          </div>
        </header>

        <main className="max-w-6xl mx-auto px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
