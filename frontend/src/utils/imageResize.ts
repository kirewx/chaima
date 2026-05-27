/**
 * Resize an image File to fit within `maxDim` on the longer edge, encoding as JPEG.
 *
 * HEIC images and anything the browser can't decode are returned unchanged —
 * the server validates regardless.
 */
export async function resizeImage(
  file: File,
  maxDim = 2048,
  quality = 0.85,
): Promise<File> {
  if (file.type === "image/heic") return file;
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    return file;
  }

  const longest = Math.max(bitmap.width, bitmap.height);
  if (longest <= maxDim) {
    bitmap.close?.();
    return file;
  }

  const scale = maxDim / longest;
  const w = Math.round(bitmap.width * scale);
  const h = Math.round(bitmap.height * scale);

  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    bitmap.close?.();
    return file;
  }
  ctx.drawImage(bitmap, 0, 0, w, h);
  bitmap.close?.();

  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, "image/jpeg", quality),
  );
  if (!blob) return file;
  return new File([blob], file.name.replace(/\.[^.]+$/, ".jpg"), {
    type: "image/jpeg",
    lastModified: Date.now(),
  });
}
