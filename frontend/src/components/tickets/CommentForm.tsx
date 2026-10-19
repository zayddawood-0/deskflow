"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ApiError } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { useAddComment } from "@/hooks/use-comments";
import { commentSchema, type CommentValues } from "@/schemas/comment";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Textarea";

export interface CommentFormProps {
  ticketId: string;
  canPostInternal: boolean;
}

export function CommentForm({ ticketId, canPostInternal }: CommentFormProps) {
  const addComment = useAddComment(ticketId);
  const [isPublic, setIsPublic] = useState(true);
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<CommentValues>({
    resolver: zodResolver(commentSchema),
    defaultValues: { body: "" },
  });

  const onSubmit = handleSubmit((values) => {
    setFormError(null);
    addComment.mutate(
      { body: values.body, is_public: canPostInternal ? isPublic : true },
      {
        onSuccess: () => {
          reset({ body: "" });
          setIsPublic(true);
        },
        onError: (error) => {
          setFormError(
            error instanceof ApiError ? error.message : "Could not post the comment.",
          );
        },
      },
    );
  });

  return (
    <form className="flex flex-col gap-3" onSubmit={onSubmit} noValidate>
      <Textarea
        placeholder={isPublic ? "Write a reply…" : "Add an internal note (agents only)…"}
        aria-label="Comment"
        {...register("body")}
      />
      {errors.body ? <p className="text-xs text-negative">{errors.body.message}</p> : null}

      {formError ? (
        <p className="rounded-xl bg-accent-soft px-3 py-2 text-xs text-negative" role="alert">
          {formError}
        </p>
      ) : null}

      <div className="flex items-center justify-between gap-3">
        {canPostInternal ? (
          <div className="inline-flex rounded-control border border-line bg-surface-muted p-0.5 text-xs font-semibold">
            <button
              type="button"
              onClick={() => setIsPublic(true)}
              className={cn(
                "rounded-control px-3 py-1.5 transition-colors",
                isPublic ? "bg-surface text-ink shadow-card" : "text-ink-muted",
              )}
            >
              Public
            </button>
            <button
              type="button"
              onClick={() => setIsPublic(false)}
              className={cn(
                "rounded-control px-3 py-1.5 transition-colors",
                !isPublic ? "bg-accent text-white" : "text-ink-muted",
              )}
            >
              Internal note
            </button>
          </div>
        ) : (
          <span className="text-xs text-ink-muted">Visible to the support team.</span>
        )}
        <Button type="submit" size="sm" loading={isSubmitting || addComment.isPending}>
          Post comment
        </Button>
      </div>
    </form>
  );
}
