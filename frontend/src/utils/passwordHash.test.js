import { webcrypto } from "crypto";

import { hashPassword } from "./passwordHash";

beforeAll(() => {
  if (!globalThis.crypto?.subtle) {
    globalThis.crypto = webcrypto;
  }
});

test("hashPassword returns stable SHA-256 hex output", async () => {
  await expect(hashPassword("Password1")).resolves.toBe(
    "19513fdc9da4fb72a4a05eb66917548d3c90ff94d5419e1f2363eea89dfee1dd",
  );
});
