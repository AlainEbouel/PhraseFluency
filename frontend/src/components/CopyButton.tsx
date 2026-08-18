import { useState } from "react";
import { Check, Copy } from "lucide-react";

export function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);

  async function handleClick() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard access denied or unavailable — silently do nothing,
      // the user can still select and copy the text manually.
    }
  }

  return (
    <button
      type="button"
      className="copy-button-control"
      onClick={handleClick}
      aria-label={`Copier : ${label}`}
    >
      {copied ? <Check /> : <Copy />}
    </button>
  );
}
