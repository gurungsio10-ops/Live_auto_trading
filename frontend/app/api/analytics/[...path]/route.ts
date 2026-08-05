import { NextRequest, NextResponse } from "next/server";
import { backendBaseUrl, envelope } from "@/lib/backend";

export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  const suffix = path.join("/");
  const url = new URL(req.url);
  const qs = url.searchParams.toString();
  const target = `${backendBaseUrl()}/analytics/${suffix}${qs ? `?${qs}` : ""}`;
  try {
    const res = await fetch(target, {
      cache: "no-store",
      headers: { Accept: "*/*", "X-Correlation-ID": crypto.randomUUID() },
    });
    if (!res.ok) {
      const body = await res.text().catch(() => "");
      return NextResponse.json(
        envelope(null, false, `Backend ${res.status}: ${body.slice(0, 200)}`),
        { status: 503 },
      );
    }
    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("text/csv") || suffix.startsWith("export/")) {
      const text = await res.text();
      // JSON export returns application/json; CSV returns text/csv.
      if (contentType.includes("application/json")) {
        try {
          return NextResponse.json(envelope(JSON.parse(text), false));
        } catch {
          return NextResponse.json(envelope({ content: text }, false));
        }
      }
      return new NextResponse(text, {
        status: 200,
        headers: {
          "Content-Type": contentType || "text/csv",
          "Content-Disposition":
            res.headers.get("content-disposition") ||
            "attachment; filename=export.csv",
        },
      });
    }
    const data = await res.json();
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    return NextResponse.json(
      envelope(
        null,
        false,
        err instanceof Error ? err.message : "backend down",
      ),
      { status: 503 },
    );
  }
}
