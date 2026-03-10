import { NextRequest } from "next/server";
import { getAssetBucketName, getSupabaseAdmin } from "@/lib/supabase-admin";
import { isAdminRequestAuthorized } from "@/lib/admin-auth";

function sanitizeFilename(filename: string) {
  return filename.replace(/[^a-zA-Z0-9._-]/g, "_");
}

export async function POST(request: NextRequest) {
  if (!isAdminRequestAuthorized(request)) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const supabase = getSupabaseAdmin();
  if (!supabase) {
    return Response.json({ error: "Supabase is not configured" }, { status: 500 });
  }

  const contentType = request.headers.get("content-type") || "";
  const bucket = getAssetBucketName();

  // Preferred flow: request signed upload URL, then upload file directly from browser.
  if (contentType.includes("application/json")) {
    let body: unknown;
    try {
      body = await request.json();
    } catch {
      return Response.json({ error: "Invalid JSON" }, { status: 400 });
    }
    const payload = body as { filename?: string; contentType?: string; folder?: string };
    const filename = sanitizeFilename(payload.filename || "upload.bin");
    const folder = sanitizeFilename((payload.folder || "products").replace(/\//g, "-"));
    const path = `${folder}/${Date.now()}-${Math.random().toString(36).slice(2)}-${filename}`;
    const { data, error } = await supabase.storage.from(bucket).createSignedUploadUrl(path);
    if (error || !data?.signedUrl) {
      return Response.json({ error: error?.message ?? "Failed to create signed upload URL" }, { status: 500 });
    }
    const { data: publicData } = supabase.storage.from(bucket).getPublicUrl(path);
    return Response.json({
      success: true,
      mode: "signed",
      signedUrl: data.signedUrl,
      path,
      url: publicData.publicUrl,
      contentType: payload.contentType || "application/octet-stream",
    });
  }

  // Backward compatibility: small files via multipart through function.
  const formData = await request.formData();
  const file = formData.get("file");
  if (!(file instanceof File)) {
    return Response.json({ error: "File is required" }, { status: 400 });
  }
  const bytes = await file.arrayBuffer();
  const buffer = Buffer.from(bytes);
  const extSafeName = sanitizeFilename(file.name || "upload.bin");
  const path = `products/${Date.now()}-${Math.random().toString(36).slice(2)}-${extSafeName}`;

  const { error } = await supabase.storage.from(bucket).upload(path, buffer, {
    contentType: file.type || "application/octet-stream",
    upsert: false,
  });
  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  const { data } = supabase.storage.from(bucket).getPublicUrl(path);
  return Response.json({ success: true, mode: "multipart", url: data.publicUrl, path });
}

