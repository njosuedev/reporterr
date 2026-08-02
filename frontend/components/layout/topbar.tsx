"use client";

import { LogOut, Receipt } from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";

export function Topbar() {
  const router = useRouter();

  const handleLogout = async () => {
    await fetch("/api/logout", { method: "POST" });
    toast.success("Signed out");
    router.push("/login");
    router.refresh();
  };

  return (
    <header className="border-b border-border bg-gradient-to-r from-primary to-primary/85 px-6 py-4 text-primary-foreground shadow-sm">
      <div className="mx-auto flex max-w-4xl items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/15">
            <Receipt className="h-5 w-5" />
          </span>
          <div>
            <p className="text-lg font-bold leading-tight">Reporterr Generator</p>
            <p className="text-xs text-primary-foreground/75">Rwanda EBM VAT Reports</p>
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleLogout}
          className="text-primary-foreground hover:bg-white/15 hover:text-primary-foreground"
        >
          <LogOut className="mr-2 h-4 w-4" /> Sign out
        </Button>
      </div>
    </header>
  );
}
