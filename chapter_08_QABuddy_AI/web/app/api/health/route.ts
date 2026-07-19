import { NextResponse } from "next/server";

const BACKEND_URL = (process.env.BACKEND_URL ?? "http://localhost/api").replace(/\/+$/, "");
const BACKEND_KEY = process.env.BACKEND_KEY ?? "";

export const dynamic = "force-dynamic";

export async function GET() {
  const headers: Record<string, string> = {};
  if (BACKEND_KEY) headers["X-QAB-Key"] = BACKEND_KEY;

  try {
    const res = await fetch(`${BACKEND_URL}/health`, {
      headers,
      signal: AbortSignal.timeout(15_000),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    return NextResponse.json(
      { healthy: false, services: {}, error: (err as Error).message },
      { status: 502 },
    );
  }
}
