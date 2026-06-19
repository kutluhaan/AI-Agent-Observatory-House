"use client";

import { useState, useEffect, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert } from "@/components/ui/alert";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/contexts/auth";

function toSlug(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .slice(0, 48);
}

export default function CreateOrgPage() {
  const router = useRouter();
  const { user, refresh } = useAuth();

  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugEdited, setSlugEdited] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Auto-derive slug from name unless user edited it
  useEffect(() => {
    if (!slugEdited) {
      setSlug(toSlug(name));
    }
  }, [name, slugEdited]);

  // Redirect if user already has an org
  useEffect(() => {
    if (user?.org_id) {
      router.replace("/");
    }
  }, [user, router]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await api.post("/organizations", { name, slug });
      await refresh();
      router.replace("/");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Something went wrong. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4 py-16">
      <div className="w-full max-w-[360px] animate-slide-up">
        <div className="mb-10 flex justify-center">
          <Logo showWordmark wordmarkSize="md" />
        </div>

        <div className="mb-7">
          <h1 className="text-xl font-semibold text-zinc-100">
            Set up your workspace
          </h1>
          <p className="mt-1.5 text-sm text-zinc-500">
            You can rename or invite teammates later.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {error && <Alert variant="error">{error}</Alert>}

          <Input
            label="Organization name"
            type="text"
            placeholder="Acme Inc."
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            minLength={2}
          />

          <Input
            label="URL slug"
            type="text"
            placeholder="acme-inc"
            value={slug}
            onChange={(e) => {
              setSlug(e.target.value);
              setSlugEdited(true);
            }}
            hint={slug ? `observatory.app/${slug}` : undefined}
            required
            minLength={2}
            pattern="[a-z0-9-]+"
          />

          <Button
            type="submit"
            size="lg"
            loading={loading}
            disabled={!name || !slug}
            className="mt-2 w-full"
          >
            Create workspace
          </Button>
        </form>
      </div>
    </div>
  );
}
