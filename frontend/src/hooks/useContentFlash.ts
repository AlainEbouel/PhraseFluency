import { useEffect, useRef, useState } from "react";

/**
 * Returns true for a brief moment whenever `value` changes (by reference),
 * skipping the initial mount. Meant to drive a CSS "new content" flash on
 * panels that can re-render with visually identical content (e.g. Réévaluer
 * returning the same verdict), so the user still sees that something happened.
 */
export function useContentFlash(value: unknown, durationMs = 500): boolean {
  const [flashing, setFlashing] = useState(false);
  const isFirstRender = useRef(true);

  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    if (value == null) return;
    setFlashing(true);
    const timeout = setTimeout(() => setFlashing(false), durationMs);
    return () => clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  return flashing;
}
