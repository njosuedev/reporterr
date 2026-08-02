import { apiClient } from "@/lib/api-client";
import type { GenerateReportPayload, GenerateReportResponse } from "@/types";

export const reportService = {
  async generate(payload: GenerateReportPayload): Promise<GenerateReportResponse> {
    const formData = new FormData();
    formData.append("company_name", payload.company_name);
    formData.append("tin", payload.tin);
    formData.append("period_start", payload.period_start);
    formData.append("period_end", payload.period_end);
    formData.append("previous_remaining_refund", String(payload.previous_remaining_refund ?? 0));
    formData.append("sales_file", payload.sales_file);
    formData.append("purchase_file", payload.purchase_file);

    const { data } = await apiClient.post<GenerateReportResponse>("/reports/generate", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  },
};
