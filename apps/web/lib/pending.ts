let pending: File[] = [];

/** Photos chosen on the home page, handed to the studio. Several photos are combined into one. */
export function setPendingFiles(files: File[]) {
  pending = files;
}

export function setPendingFile(file: File) {
  pending = [file];
}

export function takePendingFiles(): File[] {
  const files = pending;
  pending = [];
  return files;
}

/** Most combined sets are a laptop lid photographed in a few overlapping close-ups. */
export const MAX_COMBINED_PHOTOS = 12;

/** Returns an error message, or null when every file is a usable photo. */
export function checkPhotos(files: File[]): string | null {
  if (!files.length) return null;
  if (files.length > MAX_COMBINED_PHOTOS) return `Choose up to ${MAX_COMBINED_PHOTOS} photos to combine at once.`;
  for (const file of files) {
    if (!file.type.startsWith("image/") && !/\.(heic|heif)$/i.test(file.name)) {
      return `${file.name} is not a photo. Use JPG, PNG, WebP, or HEIC images.`;
    }
    if (file.size > 25 * 1024 * 1024) return `${file.name} is over 25 MB. Export a smaller photo and try again.`;
  }
  return null;
}
