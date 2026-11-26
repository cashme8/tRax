"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { ErrorBanner } from "@/components/error-banner";
import { FormField, invalidProps } from "@/components/form-field";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth";
import { applyApiErrors, zodResolver } from "@/lib/forms";

import { RedirectIfLoggedIn } from "../redirect-if-logged-in";

const schema = z.object({
  full_name: z.string().trim().min(1, "Enter your name."),
  email: z.email("Enter a valid email address."),
  // The server applies the full password rules (not common, not all digits...).
  password: z.string().min(8, "At least 8 characters."),
});
type Values = z.infer<typeof schema>;

export default function RegisterPage() {
  const { register: registerUser } = useAuth();
  const router = useRouter();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { full_name: "", email: "", password: "" },
  });

  async function onSubmit(values: Values) {
    setFormError(null);
    try {
      await registerUser(values);
      router.replace("/dashboard");
    } catch (error) {
      const message = applyApiErrors(error, setError, Object.keys(schema.shape));
      if (message !== "Please fix the highlighted fields.") setFormError(message);
    }
  }

  return (
    <Card>
      <RedirectIfLoggedIn />
      <CardHeader>
        <CardTitle>Create your account</CardTitle>
        <CardDescription>You can add your company right after.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="grid gap-4" noValidate>
          <ErrorBanner message={formError} />
          <FormField id="full_name" label="Full name" error={errors.full_name?.message}>
            <Input
              id="full_name"
              autoComplete="name"
              {...invalidProps("full_name", errors.full_name?.message)}
              {...register("full_name")}
            />
          </FormField>
          <FormField id="email" label="Email" error={errors.email?.message}>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              {...invalidProps("email", errors.email?.message)}
              {...register("email")}
            />
          </FormField>
          <FormField
            id="password"
            label="Password"
            error={errors.password?.message}
            hint="At least 8 characters; not a common password."
          >
            <Input
              id="password"
              type="password"
              autoComplete="new-password"
              {...invalidProps("password", errors.password?.message)}
              {...register("password")}
            />
          </FormField>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Creating account…" : "Create account"}
          </Button>
          <p className="text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link href="/login" className="text-foreground underline underline-offset-4">
              Log in
            </Link>
          </p>
        </form>
      </CardContent>
    </Card>
  );
}
