import { z } from "zod";

export const commentSchema = z.object({
  body: z
    .string()
    .min(1, "Write a comment first")
    .max(5000, "Use at most 5000 characters"),
});

export type CommentValues = z.infer<typeof commentSchema>;
