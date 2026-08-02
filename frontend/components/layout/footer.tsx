import { ShieldCheck } from "lucide-react";

export function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer className="mt-12 border-t border-border bg-card">
      <div className="h-1 bg-gradient-to-r from-primary via-accent to-primary" />
      <div className="mx-auto flex max-w-4xl flex-col items-center gap-2 px-6 py-8 text-center">
        <span className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
          <ShieldCheck className="h-4 w-4 text-primary" />
          Product of <span className="text-primary">A&amp;T Consultants</span>
        </span>
        <p className="text-xs text-muted-foreground">
          &copy; {year} A&amp;T Consultants. All rights reserved.
        </p>
      </div>
    </footer>
  );
}
