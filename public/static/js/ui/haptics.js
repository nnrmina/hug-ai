// Subtle vibration feedback (Android). No-op where unsupported or when motion is reduced.
const PATTERNS = {
  tap: 12,
  start: [10, 40, 18],
  success: [14, 60, 24],
  warning: [30, 50, 30],
  error: [60, 40, 60]
};

export function haptic(kind = "tap") {
  try {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    navigator.vibrate?.(PATTERNS[kind] ?? PATTERNS.tap);
  } catch (_) {}
}
