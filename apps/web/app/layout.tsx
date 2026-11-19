import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import "./globals.css";

const sans = Geist({ subsets: ["latin"], variable: "--font-sans" });
const mono = Geist_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "Sticky, bring your stickers to your next laptop",
  description:
    "Your photos and messages move to a new device. Your stickers can too. Photograph them on the old laptop, and Sticky exports print and cut files at their real size. Open source, no account.",
  openGraph: {
    title: "Sticky",
    description: "Your stickers, wherever you go. Photograph the stickers on your old laptop and print them for the new one.",
    images: ["/demo/before-matcha.png"],
  },
  icons: { icon: "/icon.svg" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`} suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `try{if(localStorage.getItem('sticky-theme')==='dark')document.documentElement.classList.add('dark')}catch(e){}`,
          }}
        />
      </head>
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
