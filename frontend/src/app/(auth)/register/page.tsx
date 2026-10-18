"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { UserPlus } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api-client";
import { registerSchema, type RegisterValues } from "@/schemas/auth";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";

export default function RegisterPage() {
  const router = useRouter();
  const { register: registerUser } = useAuth();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterValues>({ resolver: zodResolver(registerSchema) });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await registerUser(values.full_name, values.email, values.password);
      router.replace("/tickets");
    } catch (error) {
      setFormError(
        error instanceof ApiError ? error.message : "Unable to create your account. Try again.",
      );
    }
  });

  return (
    <Card className="w-full max-w-md">
      <div className="mb-6 flex flex-col items-center gap-3 text-center">
        <div className="flex size-12 items-center justify-center rounded-card bg-accent text-white">
          <UserPlus className="size-6" aria-hidden />
        </div>
        <h1 className="text-2xl font-extrabold tracking-tight text-ink">Create your account</h1>
        <p className="text-sm text-ink-muted">Requesters start here — admins can assign roles.</p>
      </div>

      <form className="flex flex-col gap-4" onSubmit={onSubmit} noValidate>
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-ink" htmlFor="full_name">
            Full name
          </label>
          <Input id="full_name" autoComplete="name" {...register("full_name")} />
          {errors.full_name ? (
            <p className="text-xs text-negative">{errors.full_name.message}</p>
          ) : null}
        </div>

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
            autoComplete="new-password"
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
          Create account
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-ink-muted">
        Already have an account?{" "}
        <Link className="font-semibold text-accent hover:text-accent-hover" href="/login">
          Sign in
        </Link>
      </p>
    </Card>
  );
}
