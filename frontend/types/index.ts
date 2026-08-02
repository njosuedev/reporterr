export type RoleName = "ADMIN" | "ACCOUNTANT" | "VIEWER";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: RoleName;
  is_active: boolean;
  created_at: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export interface Company {
  id: number;
  name: string;
  tin: string;
  address: string | null;
  phone: string | null;
  email: string | null;
  logo_path: string | null;
  owner_id: number;
  created_at: string;
  updated_at: string;
}

export type FileType = "SALES" | "PURCHASE";
export type UploadStatus = "PENDING" | "PROCESSING" | "PROCESSED" | "FAILED";

export interface Upload {
  id: number;
  company_id: number;
  uploaded_by: number;
  file_type: FileType;
  original_filename: string;
  status: UploadStatus;
  period_start: string | null;
  period_end: string | null;
  error_message: string | null;
  created_at: string;
}

export interface UploadPreview {
  upload: Upload;
  detected_company_name: string | null;
  detected_tin: string | null;
  row_count: number;
  sample_rows: Record<string, unknown>[];
  total_taxable_amount: number;
  total_vat_amount: number;
}

export interface Report {
  id: number;
  company_id: number;
  sales_upload_id: number;
  purchase_upload_id: number;
  generated_by: number;
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
  pdf_path: string | null;
  created_at: string;
}

export interface ApiErrorPayload {
  detail: string;
}

export interface RecentUpload {
  id: number;
  company_id: number;
  file_type: FileType;
  original_filename: string;
  status: UploadStatus;
  created_at: string;
}

export interface DashboardSummary {
  total_reports: number;
  total_companies: number;
  total_refund: number;
  total_vat_payable: number;
  recent_uploads: RecentUpload[];
}

export interface MonthlyTrendPoint {
  month: string;
  total_taxable_sales: number;
  output_vat: number;
  total_taxable_purchases: number;
  input_vat: number;
}
