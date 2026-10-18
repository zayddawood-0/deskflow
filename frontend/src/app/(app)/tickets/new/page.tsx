"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ApiError } from "@/lib/api-client";
import { PRIORITY_LABELS, TICKET_PRIORITIES } from "@/lib/constants";
import { useCategories } from "@/hooks/use-categories";
import { useCreateTicket } from "@/hooks/use-tickets";
import { createTicketSchema, type CreateTicketValues } from "@/schemas/ticket";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";

export default function NewTicketPage() {
  const router = useRouter();
  const categories = useCategories();
  const createTicket = useCreateTicket();
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<CreateTicketValues>({
    resolver: zodResolver(createTicketSchema),
    defaultValues: {
      title: "",
      description: "",
      category_id: "",
      priority: "MEDIUM",
      auto_assign: true,
    },
  });

  const onSubmit = handleSubmit((values) => {
    setFormError(null);
    createTicket.mutate(values, {
      onSuccess: (ticket) => router.push(`/tickets/${ticket.id}`),
      onError: (error) => {
        setFormError(error instanceof ApiError ? error.message : "Could not create the ticket.");
      },
    });
  });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight text-ink">New ticket</h1>
        <p className="text-sm text-ink-muted">Tell us what&apos;s going on and we&apos;ll route it.</p>
      </div>

      <Card>
        <form className="flex flex-col gap-5" onSubmit={onSubmit} noValidate>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-ink" htmlFor="title">
              Title
            </label>
            <Input id="title" placeholder="Short summary of the issue" {...register("title")} />
            {errors.title ? (
              <p className="text-xs text-negative">{errors.title.message}</p>
            ) : null}
          </div>

          <div className="grid gap-5 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-ink" htmlFor="category_id">
                Category
              </label>
              <Select id="category_id" {...register("category_id")}>
                <option value="">Select a category…</option>
                {(categories.data ?? []).map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </Select>
              {errors.category_id ? (
                <p className="text-xs text-negative">{errors.category_id.message}</p>
              ) : null}
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-ink" htmlFor="priority">
                Priority
              </label>
              <Select id="priority" {...register("priority")}>
                {TICKET_PRIORITIES.map((priority) => (
                  <option key={priority} value={priority}>
                    {PRIORITY_LABELS[priority]}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-ink" htmlFor="description">
              Description
            </label>
            <Textarea
              id="description"
              placeholder="What happened? Include any error messages or steps to reproduce."
              {...register("description")}
            />
            {errors.description ? (
              <p className="text-xs text-negative">{errors.description.message}</p>
            ) : null}
          </div>

          <label className="flex items-center gap-2 text-sm text-ink">
            <input type="checkbox" className="size-4 accent-accent" {...register("auto_assign")} />
            Automatically assign to the least-loaded agent
          </label>

          {formError ? (
            <p className="rounded-xl bg-accent-soft px-3 py-2 text-xs text-negative" role="alert">
              {formError}
            </p>
          ) : null}

          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => router.back()}
              disabled={isSubmitting || createTicket.isPending}
            >
              Cancel
            </Button>
            <Button type="submit" loading={isSubmitting || createTicket.isPending}>
              Create ticket
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
