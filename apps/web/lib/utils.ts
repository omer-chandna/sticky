import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export const STAGE_LABELS: Record<string, string> = {
  queued: "Starting",
  loading: "Loading photo",
  "correcting perspective": "Correcting perspective",
  "removing background": "Removing background",
  "cleaning image": "Cleaning image",
  "vectorizing artwork": "Vectorizing artwork",
  "preparing export": "Preparing export",
  done: "Done",
  cancelled: "Cancelled",
  failed: "Could not finish",
};
