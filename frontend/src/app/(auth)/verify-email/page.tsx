"use client";

import { useEffect, useState, useRef, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Mail, CheckCircle2, XCircle } from "lucide-react";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";

type Status = "pending" | "verifying" | "success" | "error";

function VerifyEmailContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const email = searchParams.get("email");

  const [status, setStatus] = useState<Status>(token ? "verifying" : "pending");
  const [errorMsg, setErrorMsg] = useState("");
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);
  const verifiedRef = useRef(false);

  useEffect(() => {
    if (!token || verifiedRef.current) return;
    verifiedRef.current = true;

    api
      .post("/auth/verify-email", { token })
      .then(() => setStatus("success"))
      .catch((err: unknown) => {
        setErrorMsg(
          err instanceof ApiError
            ? err.message
            : "Verification failed. The link may have expired.",
        );
        setStatus("error");
      });
  }, [token]);

  async function handleResend() {
    if (!email) return;
    setResending(true);
    try {
      await api.post("/auth/resend-verification", { email });
      setResent(true);
    } catch {
      // silently fail — user sees the same UI
    } finally {
      setResending(false);
    }
  }

  // ── Verifying (token in URL) ─────────────────────────────
  if (status === "verifying") {
    return (
      <div className="flex flex-col items-center gap-3 text-center">
        <span className="h-5 w-5 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
        <p className="text-sm text-zinc-400">Verifying your email…</p>
      </div>
    );
  }

  // ── Success ──────────────────────────────────────────────
  if (status === "success") {
    return (
      <div className="w-full max-w-[360px] animate-slide-up text-center">
        <Link href="/" className="mb-10 flex justify-center">
          <Logo showWordmark wordmarkSize="md" />
        </Link>
        <CheckCircle2 className="mx-auto mb-4 text-green-400" size={36} />
        <h1 className="text-xl font-semibold text-zinc-100">
          Email verified
        </h1>
        <p className="mt-2 text-sm text-zinc-500">
          Your account is ready. Sign in to get started.
        </p>
        <Button
          size="lg"
          className="mt-7 w-full"
          onClick={() => router.push("/login")}
        >
          Continue to sign in
        </Button>
      </div>
    );
  }

  // ── Error ────────────────────────────────────────────────
  if (status === "error") {
    return (
      <div className="w-full max-w-[360px] animate-slide-up text-center">
        <Link href="/" className="mb-10 flex justify-center">
          <Logo showWordmark wordmarkSize="md" />
        </Link>
        <XCircle className="mx-auto mb-4 text-red-400" size={36} />
        <h1 className="text-xl font-semibold text-zinc-100">Link expired</h1>
        <p className="mt-2 text-sm text-zinc-500">{errorMsg}</p>
        {email && (
          <Button
            variant="outline"
            size="lg"
            loading={resending}
            disabled={resent}
            onClick={handleResend}
            className="mt-7 w-full"
          >
            {resent ? "New link sent" : "Resend verification email"}
          </Button>
        )}
        <p className="mt-4 text-sm text-zinc-600">
          <Link
            href="/login"
            className="text-indigo-400 hover:text-indigo-300 transition-colors"
          >
            Back to sign in
          </Link>
        </p>
      </div>
    );
  }

  // ── Pending (just registered, no token yet) ──────────────
  return (
    <div className="w-full max-w-[360px] animate-slide-up">
      <Link href="/" className="mb-10 flex justify-center">
        <Logo showWordmark wordmarkSize="md" />
      </Link>
      <Mail
        className="mb-4 text-indigo-400"
        size={36}
        strokeWidth={1.5}
      />
      <h1 className="text-xl font-semibold text-zinc-100">Check your email</h1>
      <p className="mt-2 text-sm text-zinc-400 leading-relaxed">
        We sent a verification link
        {email && (
          <>
            {" "}to <span className="text-zinc-200">{email}</span>
          </>
        )}
        . Click it to activate your account.
      </p>

      <div className="mt-8 flex flex-col gap-3">
        {email && (
          <Button
            variant="outline"
            size="lg"
            loading={resending}
            disabled={resent}
            onClick={handleResend}
            className="w-full"
          >
            {resent ? "Link sent again" : "Resend link"}
          </Button>
        )}
        <p className="text-center text-xs text-zinc-600">
          Wrong email?{" "}
          <Link
            href="/register"
            className="text-indigo-400 hover:text-indigo-300 transition-colors"
          >
            Start over
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={
        <span className="h-5 w-5 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
      }
    >
      <VerifyEmailContent />
    </Suspense>
  );
}
