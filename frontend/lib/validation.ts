import { z } from "zod";

export const generateReportSchema = z
  .object({
    company_name: z.string().min(2, "Business name is too short"),
    tin: z.string().regex(/^\d{9}$/, "TIN must be exactly 9 digits"),
    period_start: z.string().min(1, "Period start date is required"),
    period_end: z.string().min(1, "Period end date is required"),
    previous_remaining_refund: z.coerce.number().min(0, "Must be zero or greater").optional(),
  })
  .refine((data) => data.period_end >= data.period_start, {
    message: "Period end date must be on or after the period start date",
    path: ["period_end"],
  });

export type GenerateReportFormValues = z.infer<typeof generateReportSchema>;
