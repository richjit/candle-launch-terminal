// frontend/src/components/layout/PageLayout.tsx
import { ReactNode } from "react";

interface PageLayoutProps {
  title: string;
  children: ReactNode;
}

export default function PageLayout({ title, children }: PageLayoutProps) {
  return (
    <div className="max-w-7xl mx-auto">
      <h1 className="text-2xl font-bold text-terminal-accent mb-6">{title}</h1>
      {children}
    </div>
  );
}
