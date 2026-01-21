import "./globals.css";

import AppShell from "../components/AppShell";

export const metadata = {
  title: "ContentZavod Admin",
  description: "Админка универсального контент-завода",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
