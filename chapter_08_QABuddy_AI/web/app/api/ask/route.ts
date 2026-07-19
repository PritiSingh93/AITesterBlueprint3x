import { NextRequest, NextResponse } from "next/server";

// Server-side proxy: the browser calls same-origin /api/ask, this handler
// forwards to the FastAPI backend. Keeps the backend URL hidden, avoids CORS,
// and lets us attach the shared secret.
const BACKEND_URL = (process.env.BACKEND_URL ?? "http://localhost/api").replace(/\/+$/, "");
const BACKEND_KEY = process.env.BACKEND_KEY ?? "";

export const dynamic = "force-dynamic";
export const maxDuration = 60; // capped by the Vercel plan; generation can be slow

export async function POST(req: NextRequest) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (BACKEND_KEY) headers["X-QAB-Key"] = BACKEND_KEY;

  try {
    const res = await fetch(`${BACKEND_URL}/ask`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(55_000),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    return NextResponse.json(
      {
        answer:
          `Backend unreachable at ${BACKEND_URL} — ${(err as Error).message}. ` +
          "Set BACKEND_URL to your public droplet API once it's live (Phase B).",
        sources: [],
      },
      { status: 502 },
    );
  }
}
