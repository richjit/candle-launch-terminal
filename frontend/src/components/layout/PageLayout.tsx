// frontend/src/components/layout/PageLayout.tsx
import { ReactNode } from "react";

interface PageLayoutProps {
  title: string;
  children: ReactNode;
}

export default function PageLayout({ title, children }: PageLayoutProps) {
  return (
    <div className="w-full min-h-screen -m-6 p-5 relative">
      {/* Background mesh */}
      <div className="fixed inset-0 pointer-events-none -z-10">
        <div className="absolute -top-40 -left-40 w-[600px] h-[600px] bg-purple-900/[0.06] rounded-full blur-[140px]" />
        <div className="absolute -bottom-40 -right-40 w-[500px] h-[500px] bg-cyan-900/[0.04] rounded-full blur-[140px]" />
        <div className="absolute inset-0" style={{backgroundImage:"radial-gradient(rgba(255,255,255,0.015) 1px, transparent 1px)",backgroundSize:"28px 28px"}} />
      </div>
      <div className="max-w-5xl mx-auto">
        <h1 className="text-xl font-black text-white/90 mb-5 tracking-wide">{title}</h1>
        {children}
      </div>
    </div>
  );
}
