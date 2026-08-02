"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { AlertTriangle, Copy, Download, FileSpreadsheet, MessageCircle, RefreshCw } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { Footer } from "@/components/layout/footer";
import { Topbar } from "@/components/layout/topbar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useGenerateReport } from "@/hooks/use-generate-report";
import { getApiErrorMessage } from "@/lib/api-client";
import { formatDate, formatRwf } from "@/lib/utils";
import { generateReportSchema, type GenerateReportFormValues } from "@/lib/validation";
import { buildWhatsAppShareUrl, copyToClipboard } from "@/lib/whatsapp";
import type { GenerateReportResponse } from "@/types";

const ALLOWED_EXTENSIONS = [".xlsx", ".xls"];

function hasAllowedExtension(file: File): boolean {
  const name = file.name.toLowerCase();
  return ALLOWED_EXTENSIONS.some((ext) => name.endsWith(ext));
}

function downloadPdf(pdfBase64: string, filename: string) {
  const byteChars = atob(pdfBase64);
  const byteNumbers = new Array(byteChars.length);
  for (let i = 0; i < byteChars.length; i++) byteNumbers[i] = byteChars.charCodeAt(i);
  const blob = new Blob([new Uint8Array(byteNumbers)], { type: "application/pdf" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function FileField({
  label,
  file,
  onChange,
}: {
  label: string;
  file: File | null;
  onChange: (file: File | null) => void;
}) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <Input type="file" accept=".xlsx,.xls" onChange={(e) => onChange(e.target.files?.[0] ?? null)} />
      {file && <p className="text-xs text-muted-foreground">{file.name}</p>}
    </div>
  );
}

function ReportResults({ result }: { result: GenerateReportResponse }) {
  const [showText, setShowText] = useState(false);

  const handleCopy = async () => {
    const ok = await copyToClipboard(result.whatsapp_text);
    toast[ok ? "success" : "error"](ok ? "Copied to clipboard" : "Failed to copy");
  };

  const handleShare = () => window.open(buildWhatsAppShareUrl(result.whatsapp_text), "_blank");

  const handleDownload = () => downloadPdf(result.pdf_base64, `vat-report-${result.period_start}-${result.period_end}.pdf`);

  const stats: { label: string; value: string; highlight?: "warning" | "success" }[] = [
    { label: "Taxable Sales", value: formatRwf(result.total_taxable_sales) },
    { label: "VAT on Sales", value: formatRwf(result.output_vat) },
    { label: "Taxable Purchases", value: formatRwf(result.total_taxable_purchases) },
    { label: "VAT on Purchase", value: formatRwf(result.input_vat) },
    {
      label: "VAT Payable",
      value: formatRwf(result.vat_payable),
      highlight: result.vat_payable > 0 ? "warning" : undefined,
    },
    { label: "Refund", value: formatRwf(result.refund), highlight: result.refund > 0 ? "success" : undefined },
    { label: "Remaining Refund", value: formatRwf(result.remaining_refund) },
    { label: "Sales Needed to Clear Refund", value: formatRwf(result.required_sales_to_clear_refund) },
    {
      label: "Purchases Needed to Clear VAT Payable",
      value: formatRwf(result.required_purchases_to_clear_vat_payable),
    },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>{result.company_name}</CardTitle>
        <CardDescription>
          TIN: {result.tin} &middot; Period: {formatDate(result.period_start)} &ndash; {formatDate(result.period_end)}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {stats.map((s) => (
            <div key={s.label} className="rounded-lg border border-border p-4">
              <p className="text-xs text-muted-foreground">{s.label}</p>
              <p
                className={
                  "mt-1 text-lg font-semibold " +
                  (s.highlight === "warning"
                    ? "text-amber-600"
                    : s.highlight === "success"
                      ? "text-emerald-600"
                      : "")
                }
              >
                {s.value}
              </p>
            </div>
          ))}
        </div>

        {result.missing_sales_receipts.some((g) => g.missing_count > 0) && (
          <div className="space-y-3 rounded-lg border border-amber-300 bg-amber-50 p-4 dark:border-amber-900 dark:bg-amber-950">
            <p className="flex items-center gap-2 text-sm font-semibold text-amber-800 dark:text-amber-300">
              <AlertTriangle className="h-4 w-4" /> Missing sales receipts detected
            </p>
            {result.missing_sales_receipts
              .filter((g) => g.missing_count > 0)
              .map((g) => (
                <div key={g.prefix}>
                  <p className="text-sm text-muted-foreground">
                    {g.prefix}: {g.missing_count} missing (receipts {g.lowest}&ndash;{g.highest})
                  </p>
                  <p className="mt-1 break-words font-mono text-xs">{g.missing_receipts.join(", ")}</p>
                </div>
              ))}
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <Button onClick={handleDownload}>
            <Download className="mr-2 h-4 w-4" /> Download PDF
          </Button>
          <Button variant="outline" onClick={() => setShowText(true)}>
            <FileSpreadsheet className="mr-2 h-4 w-4" /> View report text
          </Button>
          <Button variant="outline" onClick={handleShare}>
            <MessageCircle className="mr-2 h-4 w-4" /> Share on WhatsApp
          </Button>
        </div>
      </CardContent>

      <Dialog open={showText} onOpenChange={setShowText}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Report summary</DialogTitle>
          </DialogHeader>
          <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-md bg-secondary p-4 text-sm">
            {result.whatsapp_text}
          </pre>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={handleCopy}>
              <Copy className="mr-2 h-4 w-4" /> Copy
            </Button>
            <Button onClick={handleShare}>
              <MessageCircle className="mr-2 h-4 w-4" /> Share on WhatsApp
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

export default function Home() {
  const [salesFile, setSalesFile] = useState<File | null>(null);
  const [purchaseFile, setPurchaseFile] = useState<File | null>(null);
  const [result, setResult] = useState<GenerateReportResponse | null>(null);
  const generateReport = useGenerateReport();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<GenerateReportFormValues>({
    resolver: zodResolver(generateReportSchema),
    defaultValues: { company_name: "", tin: "", period_start: "", period_end: "", previous_remaining_refund: 0 },
  });

  const onSubmit = async (values: GenerateReportFormValues) => {
    if (!salesFile || !purchaseFile) {
      toast.error("Please select both the Sales and Purchase files");
      return;
    }
    if (!hasAllowedExtension(salesFile) || !hasAllowedExtension(purchaseFile)) {
      toast.error("Files must be .xlsx or .xls");
      return;
    }

    try {
      const report = await generateReport.mutateAsync({
        ...values,
        sales_file: salesFile,
        purchase_file: purchaseFile,
      });
      setResult(report);
      toast.success("Report generated");
    } catch (error) {
      toast.error(getApiErrorMessage(error));
    }
  };

  const handleReset = () => {
    reset();
    setSalesFile(null);
    setPurchaseFile(null);
    setResult(null);
  };

  return (
    <div className="flex min-h-screen flex-col">
      <Topbar />
      <main className="mx-auto w-full max-w-4xl flex-1 space-y-6 p-6">
        <Card>
          <CardHeader>
            <CardTitle>Generate VAT report</CardTitle>
            <CardDescription>
              Enter your business details, pick the report period, and upload the EBM Sales and
              Purchase exports. Nothing is saved &mdash; each report is generated fresh.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="company_name">Business name</Label>
                  <Input id="company_name" {...register("company_name")} />
                  {errors.company_name && <p className="text-sm text-destructive">{errors.company_name.message}</p>}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="tin">TIN</Label>
                  <Input id="tin" {...register("tin")} />
                  {errors.tin && <p className="text-sm text-destructive">{errors.tin.message}</p>}
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-3">
                <div className="space-y-2">
                  <Label htmlFor="period_start">Period start</Label>
                  <Input id="period_start" type="date" {...register("period_start")} />
                  {errors.period_start && <p className="text-sm text-destructive">{errors.period_start.message}</p>}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="period_end">Period end</Label>
                  <Input id="period_end" type="date" {...register("period_end")} />
                  {errors.period_end && <p className="text-sm text-destructive">{errors.period_end.message}</p>}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="previous_remaining_refund">Previous remaining refund (optional)</Label>
                  <Input
                    id="previous_remaining_refund"
                    type="number"
                    min="0"
                    {...register("previous_remaining_refund")}
                  />
                  {errors.previous_remaining_refund && (
                    <p className="text-sm text-destructive">{errors.previous_remaining_refund.message}</p>
                  )}
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <FileField label="Sales file" file={salesFile} onChange={setSalesFile} />
                <FileField label="Purchase file" file={purchaseFile} onChange={setPurchaseFile} />
              </div>

              <div className="flex gap-2">
                <Button type="submit" disabled={generateReport.isPending}>
                  {generateReport.isPending ? "Generating..." : "Generate report"}
                </Button>
                {result && (
                  <Button type="button" variant="outline" onClick={handleReset}>
                    <RefreshCw className="mr-2 h-4 w-4" /> Start a new report
                  </Button>
                )}
              </div>
            </form>
          </CardContent>
        </Card>

        {result && <ReportResults result={result} />}
      </main>
      <Footer />
    </div>
  );
}
