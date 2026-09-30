/**
 * Sandbox self-test for the local auth fallback machinery.
 * Exercises: Google claims → local user upsert → token minting →
 * token verification (access + refresh) → local user resolution.
 */
import {
  upsertLocalGoogleUser,
  mintLocalTokens,
  getLocalUserFromToken,
  verifyGoogleIdTokenLocally,
} from "@/lib/local-auth";

async function main() {
  const exp = String(Math.floor(Date.now() / 1000) + 3600);
  const claims = {
    aud: process.env.GOOGLE_CLIENT_ID || "test-aud",
    email: "sandbox.tester@gmail.com",
    email_verified: "true" as const,
    exp,
    sub: "sandbox-sub-12345",
    name: "Sandbox Tester",
  };

  // 1. Verify the tokeninfo verifier REJECTS a forged token (real network call)
  const forged =
    "eyJhbGciOiJSUzI1NiJ9.eyJhdWQiOiJ4IiwiZW1haWwiOiJ0QHQuY29tIiwiZXhwIjo5OTk5OTk5OTk5fQ.fakesig";
  const rejected = await verifyGoogleIdTokenLocally(forged);
  console.log("1. forged token rejected:", rejected === null ? "PASS" : "FAIL");

  // 2. Upsert local user (simulating verified Google claims)
  const user = await upsertLocalGoogleUser(claims as never);
  console.log(
    "2. user upsert:",
    user ? `PASS (${user.id.slice(0, 8)}… ${user.email} verified=${user.is_verified})` : "FAIL"
  );
  if (!user) process.exit(1);

  // 3. Mint local session tokens
  const tokens = await mintLocalTokens(user.id, user.email);
  console.log(
    "3. tokens minted:",
    tokens.accessToken.length > 50 && tokens.refreshToken.length > 50 ? "PASS" : "FAIL"
  );

  // 4. Resolve access token → user
  const me = await getLocalUserFromToken(tokens.accessToken, "access");
  console.log(
    "4. access token resolves:",
    me && me.email === claims.email ? `PASS (${me.email}, role=${me.role})` : "FAIL"
  );

  // 5. Refresh token resolves only as refresh type
  const asRefresh = await getLocalUserFromToken(tokens.refreshToken, "refresh");
  const accessAsRefresh = await getLocalUserFromToken(tokens.accessToken, "refresh");
  console.log(
    "5. refresh semantics:",
    asRefresh && !accessAsRefresh ? "PASS" : "FAIL"
  );

  // 6. User persists in DB (findUnique by email)
  const { db } = await import("@/lib/db");
  const again = await db.user.findUnique({ where: { email: claims.email } });
  console.log("6. user persisted:", again && again.emailVerified ? "PASS" : "FAIL");

  process.exit(0);
}

main().catch((e) => {
  console.error("TEST ERROR:", e);
  process.exit(1);
});
