/**
 * Frame-driven, deterministic motion for ONNELLAB product films.
 * A small entrance follows a real state change; no autonomous decoration.
 * @param {number} frame
 * @param {number} startFrame
 * @param {number} frames
 * @param {number} travelPx
 */
export function reveal(frame, startFrame, frames = 10, travelPx = 20) {
  if (![frame, startFrame, frames, travelPx].every(Number.isFinite) || frames <= 0 || travelPx < 0) {
    throw new Error('Invalid motion timing');
  }
  const progress = Math.max(0, Math.min(1, (frame - startFrame) / frames));
  const eased = 1 - Math.pow(1 - progress, 3);
  return {
    opacity: eased,
    transform: `translateY(${(1 - eased) * travelPx}px)`,
  };
}
