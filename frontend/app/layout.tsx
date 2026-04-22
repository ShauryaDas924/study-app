"use client";

import "@/styles/globals.css";
import "katex/dist/katex.min.css";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/lib/queryClient";
import Navbar from "@/components/Navbar";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="app-shell antialiased">
        <QueryClientProvider client={queryClient}>
          <div className="min-h-screen">
            <Navbar />
            <main className="mx-auto max-w-5xl px-6 py-10">
              {children}
            </main>
          </div>
        </QueryClientProvider>
      </body>
    </html>
  );
}