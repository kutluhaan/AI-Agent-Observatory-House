"use client";

import { useEffect, useRef, useState } from "react";
import { LogOut, UserPlus, ChevronDown, Mail, Check } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/contexts/auth";
import { Modal } from "@/components/ui/modal";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { cn } from "@/lib/utils";

/** Navbar sağ kümesinde "Profilim" menüsü: kullanıcı bilgisi + organizasyona davet + çıkış. */
export function ProfileMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [inviteOpen, setInviteOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  if (!user) return null;
  const letter = (user.email?.[0] ?? "?").toUpperCase();
  const isOwner = user.role === "owner";

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 rounded-md px-1.5 py-1 text-zinc-400 transition-colors hover:bg-zinc-900 hover:text-zinc-200"
        title="Profilim"
      >
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-indigo-500/20 text-[11px] font-semibold text-indigo-300">{letter}</span>
        <ChevronDown size={12} className={cn("transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-1.5 w-60 overflow-hidden rounded-lg border border-zinc-800 bg-zinc-950 shadow-xl">
          <div className="border-b border-zinc-800 px-3 py-2.5">
            <p className="truncate text-xs font-medium text-zinc-200">{user.email}</p>
            {user.role && <p className="mt-0.5 text-[10px] uppercase tracking-wide text-zinc-600">{user.role}</p>}
          </div>
          {isOwner && (
            <button
              onClick={() => { setOpen(false); setInviteOpen(true); }}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-zinc-300 transition-colors hover:bg-zinc-900"
            >
              <UserPlus size={13} className="text-indigo-400" />
              Organizasyona davet et
            </button>
          )}
          <button
            onClick={() => { setOpen(false); logout(); }}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-zinc-400 transition-colors hover:bg-zinc-900 hover:text-zinc-200"
          >
            <LogOut size={13} />
            Çıkış yap
          </button>
        </div>
      )}

      <InviteModal open={inviteOpen} onClose={() => setInviteOpen(false)} orgId={user.org_id ?? ""} />
    </div>
  );
}

function InviteModal({ open, onClose, orgId }: { open: boolean; onClose: () => void; orgId: string }) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState<string | null>(null);

  function reset() { setEmail(""); setRole("member"); setError(""); setSent(null); }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim() || !orgId) return;
    setBusy(true); setError("");
    try {
      await api.post(`/organizations/${orgId}/invitations`, { email: email.trim(), role });
      setSent(email.trim());
      setEmail("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Davet gönderilemedi.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} title="Organizasyona davet et" onClose={() => { reset(); onClose(); }} className="max-w-md">
      <form onSubmit={submit} className="flex flex-col gap-3">
        <p className="text-xs text-zinc-500">Davet edilen kişiye e-posta ile bir katılım linki gönderilir (7 gün geçerli).</p>
        {error && <Alert variant="error">{error}</Alert>}
        {sent && (
          <Alert variant="success">
            <span className="flex items-center gap-1.5"><Check size={13} />{sent} adresine davet gönderildi.</span>
          </Alert>
        )}
        <div className="relative">
          <Mail size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-600" />
          <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
            placeholder="kisi@ornek.com" className="pl-9" />
        </div>
        <div>
          <label className="mb-1 block text-xs text-zinc-500">Rol</label>
          <select value={role} onChange={(e) => setRole(e.target.value)}
            className="w-full rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-sm text-zinc-100 focus:border-indigo-500 focus:outline-none">
            <option value="member">Member — agent/ekip kullanır</option>
            <option value="admin">Admin — üye yönetimi dahil</option>
          </select>
        </div>
        <div className="mt-1 flex justify-end gap-2">
          <Button type="button" variant="ghost" size="sm" onClick={() => { reset(); onClose(); }}>Kapat</Button>
          <Button type="submit" size="sm" loading={busy} disabled={!email.trim()}><UserPlus size={13} />Davet gönder</Button>
        </div>
      </form>
    </Modal>
  );
}
