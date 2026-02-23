import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI MKT Dashboard",
  description: "Tenant analytics and monitoring dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
