"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { KeyRound } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { api, ApiError } from "@/lib/api-client";
import { ROLE_LABELS } from "@/lib/constants";
import { formatDate } from "@/lib/utils";
import { changePasswordSchema, type ChangePasswordValues } from "@/schemas/auth";
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";

export default function SettingsPage() {
  const { user } = useAuth();
  const [formError, setFormError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ChangePasswordValues>({ resolver: zodResolver(changePasswordSchema) });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    setSaved(false);
    try {
      await api<void>("/auth/change-password", {
        method: "POST",
        json: {
          current_password: values.current_password,
          new_password: values.new_password,
        },
      });
      reset();
      setSaved(true);
    } catch (error) {
      setFormError(error instanceof ApiError ? error.message : "Unable to update your password.");
    }
  });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-4xl font-extrabold tracking-tight text-ink">Settings</h1>
        <p className="text-sm text-ink-muted">Manage your profile and password.</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Profile" subtitle="Your account details.">
          <div className="flex items-center gap-4">
            <Avatar name={user?.full_name ?? "?"} />
            <div className="min-w-0">
              <p className="text-base font-semibold text-ink">{user?.full_name ?? "—"}</p>
              <p className="text-xs text-ink-muted">{user?.email ?? "—"}</p>
            </div>
          </div>
          <dl className="mt-6 grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-xs uppercase tracking-wide text-ink-muted">Role</dt>
              <dd className="font-medium text-ink">{user ? ROLE_LABELS[user.role] : "—"}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-ink-muted">Joined</dt>
              <dd className="font-medium text-ink">{user ? formatDate(user.created_at) : "—"}</dd>
            </div>
          </dl>
        </Card>

        <Card title="Change password" subtitle="Other sessions are signed out after a change.">
          <form className="flex flex-col gap-4" onSubmit={onSubmit} noValidate>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-ink" htmlFor="current_password">
                Current password
              </label>
              <Input
                id="current_password"
                type="password"
                autoComplete="current-password"
                {...register("current_password")}
              />
              {errors.current_password ? (
                <p className="text-xs text-negative">{errors.current_password.message}</p>
              ) : null}
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-ink" htmlFor="new_password">
                New password
              </label>
              <Input
                id="new_password"
                type="password"
                autoComplete="new-password"
                {...register("new_password")}
              />
              <p className="text-xs text-ink-muted">
                At least 8 characters with upper, lower case and a number.
              </p>
              {errors.new_password ? (
                <p className="text-xs text-negative">{errors.new_password.message}</p>
              ) : null}
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-ink" htmlFor="confirm_password">
                Confirm new password
              </label>
              <Input
                id="confirm_password"
                type="password"
                autoComplete="new-password"
                {...register("confirm_password")}
              />
              {errors.confirm_password ? (
                <p className="text-xs text-negative">{errors.confirm_password.message}</p>
              ) : null}
            </div>

            {formError ? (
              <p className="rounded-xl bg-accent-soft px-3 py-2 text-xs text-negative" role="alert">
                {formError}
              </p>
            ) : null}

            {saved ? (
              <p className="rounded-xl bg-surface-muted px-3 py-2 text-xs text-ink" role="status">
                Password updated — other sessions signed out.
              </p>
            ) : null}

            <Button type="submit" size="lg" loading={isSubmitting}>
              <KeyRound className="size-4" aria-hidden />
              Update password
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
}
