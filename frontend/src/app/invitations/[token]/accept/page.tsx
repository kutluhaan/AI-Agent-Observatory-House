"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useParams } from "next/navigation";
import { Building2, UserCheck, AlertCircle } from "lucide-react";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/contexts/auth";

interface InvitationInfo {
  org_name: string;
  org_slug: string;
  invited_by: string;
  role: string;
}

type PageState = "loading" | "ready" | "accepting" | "done" | "error";

export default function AcceptInvitationPage() {
  const { token } = useParams<{ token: string }>();
  const router = useRouter();
  const { user, refresh } = useAuth();

  const [state, setState] = useState<PageState>("loading");
  const [invitation, setInvitation] = useState<InvitationInfo | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) return;
    api
      .get<InvitationInfo>(`/invitations/${token}`)
      .then((info) => {
        setInvitation(info);
        setState("ready");
      })
      .catch((err: unknown) => {
        setError(
          err instanceof ApiError
            ? err.message
            : "This invitation link is invalid or has expired.",
        );
        setState("error");
      });
  }, [token]);

  async function handleAccept() {
    setState("accepting");
    try {
      await api.post(`/invitations/${token}/accept`);
      await refresh();
      setState("done");
      setTimeout(() => router.replace("/"), 1500);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not accept invitation.",
      );
      setState("error");
    }
  }

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center px-4 py-16">
      <div className="w-full max-w-[380px] animate-slide-up">
        <Link href="/" className="mb-10 flex justify-center">
          <Logo showWordmark wordmarkSize="md" />
        </Link>

        {state === "loading" && (
          <div className="flex justify-center py-8">
            <span className="h-5 w-5 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
          </div>
        )}

        {state === "error" && (
          <>
            <AlertCircle className="mb-4 text-red-400" size={32} />
            <h1 className="text-xl font-semibold text-zinc-100">
              Invalid invitation
            </h1>
            <p className="mt-2 text-sm text-zinc-500">{error}</p>
            <Button
              variant="outline"
              size="lg"
              className="mt-7 w-full"
              onClick={() => router.push("/")}
            >
              Go to dashboard
            </Button>
          </>
        )}

        {state === "done" && (
          <>
            <UserCheck className="mb-4 text-green-400" size={32} />
            <h1 className="text-xl font-semibold text-zinc-100">
              Joined successfully
            </h1>
            <p className="mt-2 text-sm text-zinc-500">
              Redirecting to your new workspace…
            </p>
          </>
        )}

        {(state === "ready" || state === "accepting") && invitation && (
          <>
            <div className="mb-6 flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-zinc-800">
                <Building2 size={20} className="text-zinc-300" />
              </div>
              <div>
                <p className="font-medium text-zinc-100">{invitation.org_name}</p>
                <p className="text-xs text-zinc-600">{invitation.org_slug}</p>
              </div>
            </div>

            <h1 className="text-xl font-semibold text-zinc-100">
              You&apos;ve been invited
            </h1>
            <p className="mt-2 text-sm text-zinc-400 leading-relaxed">
              <span className="text-zinc-200">{invitation.invited_by}</span> has
              invited you to join{" "}
              <span className="text-zinc-200">{invitation.org_name}</span> as{" "}
              <span className="text-indigo-400">{invitation.role}</span>.
            </p>

            {!user && (
              <Alert variant="info" className="mt-4">
                You need to sign in or create an account before accepting.
              </Alert>
            )}

            <div className="mt-7 flex flex-col gap-2">
              {user ? (
                <Button
                  size="lg"
                  loading={state === "accepting"}
                  onClick={handleAccept}
                  className="w-full"
                >
                  Accept invitation
                </Button>
              ) : (
                <>
                  <Button
                    size="lg"
                    onClick={() =>
                      router.push(`/login?next=/invitations/${token}/accept`)
                    }
                    className="w-full"
                  >
                    Sign in to accept
                  </Button>
                  <Button
                    variant="outline"
                    size="lg"
                    onClick={() =>
                      router.push(
                        `/register?next=/invitations/${token}/accept`,
                      )
                    }
                    className="w-full"
                  >
                    Create account
                  </Button>
                </>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
