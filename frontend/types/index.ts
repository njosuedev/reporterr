export interface GenerateReportPayload {
  company_name: string;
  tin: string;
  period_start: string;
  period_end: string;
  previous_remaining_refund?: number;
  sales_file: File;
  purchase_file: File;
}

export interface MissingReceiptGroup {
  prefix: string;
  lowest: number;
  highest: number;
  present_count: number;
  missing_count: number;
  missing_receipts: string[];
}

export interface GenerateReportResponse {
  company_name: string;
  tin: string;
  period_start: string;
  period_end: string;
  total_taxable_sales: number;
  output_vat: number;
  total_taxable_purchases: number;
  input_vat: number;
  vat_difference: number;
  vat_payable: number;
  refund: number;
  remaining_refund: number;
  required_sales_to_clear_refund: number;
  required_purchases_to_clear_vat_payable: number;
  missing_sales_receipts: MissingReceiptGroup[];
  whatsapp_text: string;
  pdf_base64: string;
}

export interface ApiErrorPayload {
  detail: string;
}