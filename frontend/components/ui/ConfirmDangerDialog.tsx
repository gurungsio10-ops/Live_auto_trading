"use client";

import { useEffect, useId, useRef, useState } from "react";
import { Button } from "./Button";

export function ConfirmDangerDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  requireText,
  onConfirm,
  onClose,
  pending = false,
}: {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  requireText?: string;
  onConfirm: () => void;
  onClose: () => void;
  pending?: boolean;
}) {
  const titleId = useId();
  const [typed, setTyped] = useState("");
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) {
      setTyped("");
      return;
    }
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panelRef.current?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      document.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  if (!open) return null;
  const canConfirm = requireText ? typed.trim() === requireText : true;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-4 sm:items-center">
      <button type="button" className="absolute inset-0" aria-label="Close dialog" onClick={onClose} />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className="relative z-10 w-full max-w-md rounded-card border border-border bg-surface p-5 shadow-soft animate-fade-in"
      >
        <h2 id={titleId} className="text-lg font-semibold text-foreground">
          {title}
        </h2>
        <p className="mt-2 text-[14px] leading-relaxed text-secondary">{description}</p>
        {requireText ? (
          <label className="mt-4 block text-[13px] text-secondary">
            Type <span className="font-mono text-foreground">{requireText}</span> to confirm
            <input
              className="mt-2 w-full min-h-touch rounded-control border border-border bg-surface-raised px-3 text-foreground outline-none focus:border-primary"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              autoComplete="off"
            />
          </label>
        ) : null}
        <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button type="button" variant="ghost" onClick={onClose} disabled={pending}>
            Cancel
          </Button>
          <Button
            type="button"
            variant="dangerOutline"
            disabled={!canConfirm || pending}
            onClick={onConfirm}
          >
            {pending ? "Working…" : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
