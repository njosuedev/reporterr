import { useMutation } from "@tanstack/react-query";

import { reportService } from "@/services/report-service";
import type { GenerateReportPayload } from "@/types";

export function useGenerateReport() {
  return useMutation({
    mutationFn: (payload: GenerateReportPayload) => reportService.generate(payload),
  });
}
