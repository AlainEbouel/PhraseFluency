import { useCallback, useRef } from "react";

export type SoundKind = "pending" | "natural" | "unnatural" | "incorrect";

interface Note {
  freq: number;
  start: number;
  duration: number;
  type?: OscillatorType;
}

const SOUND_NOTES: Record<SoundKind, Note[]> = {
  // A soft two-note blip: "here's a chance to adjust".
  pending: [
    { freq: 520, start: 0, duration: 0.09 },
    { freq: 620, start: 0.1, duration: 0.09 },
  ],
  // A bright ascending three-note chime.
  natural: [
    { freq: 523.25, start: 0, duration: 0.1 },
    { freq: 659.25, start: 0.1, duration: 0.1 },
    { freq: 783.99, start: 0.2, duration: 0.16 },
  ],
  // A short, neutral, slightly plain tone — correct but not perfect.
  unnatural: [{ freq: 440, start: 0, duration: 0.18, type: "triangle" }],
  // A brief descending tone — clearly negative but not harsh.
  incorrect: [
    { freq: 300, start: 0, duration: 0.12, type: "sawtooth" },
    { freq: 220, start: 0.1, duration: 0.16, type: "sawtooth" },
  ],
};

export function useSoundEffects() {
  const ctxRef = useRef<AudioContext | null>(null);

  const playSound = useCallback((kind: SoundKind) => {
    try {
      if (!ctxRef.current) {
        const AudioContextClass =
          window.AudioContext ||
          (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
        if (!AudioContextClass) return;
        ctxRef.current = new AudioContextClass();
      }
      const ctx = ctxRef.current;
      if (ctx.state === "suspended") {
        void ctx.resume();
      }
      const now = ctx.currentTime;
      for (const note of SOUND_NOTES[kind]) {
        const oscillator = ctx.createOscillator();
        const gain = ctx.createGain();
        oscillator.type = note.type ?? "sine";
        oscillator.frequency.value = note.freq;
        const startTime = now + note.start;
        const endTime = startTime + note.duration;
        gain.gain.setValueAtTime(0.0001, startTime);
        gain.gain.exponentialRampToValueAtTime(0.2, startTime + 0.015);
        gain.gain.exponentialRampToValueAtTime(0.0001, endTime);
        oscillator.connect(gain);
        gain.connect(ctx.destination);
        oscillator.start(startTime);
        oscillator.stop(endTime + 0.02);
      }
    } catch {
      // Sound effects are decorative — never let audio failures break the flow.
    }
  }, []);

  return { playSound };
}
