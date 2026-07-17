/** Google research links for backfilling missing SDS. Pure CAS search found
 *  chemicals reliably in manual testing; the filetype:pdf variant often hits
 *  the SDS PDF directly for well-known substances. */
export function casSearchUrl(cas: string): string {
  return `https://www.google.com/search?q=${encodeURIComponent(`"${cas}"`)}`;
}

export function sdsPdfSearchUrl(cas: string): string {
  return `https://www.google.com/search?q=${encodeURIComponent(
    `"${cas}" sicherheitsdatenblatt filetype:pdf`,
  )}`;
}
