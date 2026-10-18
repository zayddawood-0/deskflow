"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Ticket } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api-client";
import { loginSchema, type LoginValues } from "@/schemas/auth";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await login(values.email, values.password);
      router.replace("/tickets");
    } catch (error) {
      setFormError(error instanceof ApiError ? error.message : "Unable to sign in. Try again.");
    }
  });

  return (
    <Card className="w-full max-w-md">
      <div className="mb-6 flex flex-col items-center gap-3 text-center">
        <div className="flex size-12 items-center justify-center rounded-card bg-accent text-white">
          <Ticket className="size-6" aria-hidden />
        </div>
        <h1 className="text-2xl font-extrabold tracking-tight text-ink">Welcome back</h1>
        <p className="text-sm text-ink-muted">Sign in to your DeskFlow workspace.</p>
      </div>

      <form className="flex flex-col gap-4" onSubmit={onSubmit} noValidate>
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-ink" htmlFor="email">
            Email
          </label>
          <Input id="email" type="email" autoComplete="email" {...register("email")} />
          {errors.email ? <p className="text-xs text-negative">{errors.email.message}</p> : null}
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-ink" htmlFor="password">
            Password
          </label>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            {...register("password")}
          />
          {errors.password ? (
            <p className="text-xs text-negative">{errors.password.message}</p>
          ) : null}
        </div>

        {formError ? (
          <p className="rounded-xl bg-accent-soft px-3 py-2 text-xs text-negative" role="alert">
            {formError}
          </p>
        ) : null}

        <Button type="submit" size="lg" loading={isSubmitting}>
          Sign in
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-ink-muted">
        No account yet?{" "}
        <Link className="font-semibold text-accent hover:text-accent-hover" href="/register">
          Create one
        </Link>
      </p>
    </Card>
  );
}
