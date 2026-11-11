let pending: File | null = null;

export function setPendingFile(file: File) {
  pending = file;
}

export function takePendingFile(): File | null {
  const file = pending;
  pending = null;
  return file;
}
