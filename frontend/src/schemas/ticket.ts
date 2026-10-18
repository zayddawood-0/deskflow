import { z } from "zod";
import { TICKET_PRIORITIES } from "@/lib/constants";

export const createTicketSchema = z.object({
  title: z
    .string()
    .min(5, "Use at least 5 characters")
    .max(200, "Use at most 200 characters"),
  description: z
    .string()
    .min(10, "Describe the issue in at least 10 characters")
    .max(20000, "Use at most 20000 characters"),
  category_id: z.string().min(1, "Choose a category"),
  priority: z.enum(TICKET_PRIORITIES),
  auto_assign: z.boolean(),
});

export type CreateTicketValues = z.infer<typeof createTicketSchema>;
