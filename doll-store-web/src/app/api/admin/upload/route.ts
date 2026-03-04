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

  const formData = await request.formData();
  const file = formData.get("file");
  if (!(file instanceof File)) {
    return Response.json({ error: "File is required" }, { status: 400 });
  }

  const bytes = await file.arrayBuffer();
  const buffer = Buffer.from(bytes);
  const extSafeName = sanitizeFilename(file.name || "upload.bin");
  const path = `products/${Date.now()}-${Math.random().toString(36).slice(2)}-${extSafeName}`;
  const bucket = getAssetBucketName();

  const { error } = await supabase.storage.from(bucket).upload(path, buffer, {
    contentType: file.type || "application/octet-stream",
    upsert: false,
  });
  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  const { data } = supabase.storage.from(bucket).getPublicUrl(path);
  return Response.json({ success: true, url: data.publicUrl, path });
}

