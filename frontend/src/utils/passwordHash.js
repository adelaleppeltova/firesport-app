export async function hashPassword(password) {
  const cryptoApi =
    typeof window !== "undefined" ? window.crypto : undefined;

  if (!cryptoApi?.subtle) {
    throw new Error("Web Crypto API is not available.");
  }

  const encoder = new TextEncoder();
  const data = encoder.encode(password);
  const digest = await cryptoApi.subtle.digest("SHA-256", data);

  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}
