import type { Metadata, Viewport } from 'next';
import { Barlow_Condensed, Source_Sans_3 } from 'next/font/google';
import './globals.css';

const display = Barlow_Condensed({
  subsets: ['latin'],
  variable: '--font-display',
  weight: ['600', '700'],
});
const body = Source_Sans_3({ subsets: ['latin'], variable: '--font-body' });

export const metadata: Metadata = {
  title: 'March Madness AI Bracket',
  description: 'Build and predict your NCAA bracket with AI',
  manifest: '/manifest.json',
  appleWebApp: { capable: true, title: 'MM Bracket' },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  themeColor: '#0033A0',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable}`}>
      <body className="font-body antialiased min-h-screen bg-ncaa-cream text-ncaa-dark">
        {children}
      </body>
    </html>
  );
}
