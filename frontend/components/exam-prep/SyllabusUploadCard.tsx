"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type UploadExamPrepSyllabusOut, type UUID } from "@/lib/api";
import { Button } from "@/components/ui/Button";

export default function SyllabusUploadCard({
  classId,
  onUploaded,
}: {
  classId: UUID;
  onUploaded: (out: UploadExamPrepSyllabusOut) => void;
}) {
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);

  const uploadM = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("Choose a syllabus file first.");
      return api.uploadExamPrepSyllabus(classId, file);
    },
    onSuccess: async (data) => {
      onUploaded(data);
      setFile(null);
      await qc.invalidateQueries({ queryKey: ["exam-prep-syllabi", classId] });
    },
  });

  return (
    <div className="space-y-3">
      <div>
        <div className="text-xs text-slate-500 mb-1">Syllabus file</div>
        <input
          type="file"
          accept=".pdf,.txt,.md"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="block w-full text-sm text-slate-600"
        />
        <div className="mt-1 text-xs text-slate-500">
          PDF and TXT are supported for this first version.
        </div>
      </div>

      <Button onClick={() => uploadM.mutate()} disabled={!file || uploadM.isPending}>
        {uploadM.isPending ? "Uploading..." : "Upload Syllabus"}
      </Button>

      {uploadM.error ? (
        <div className="text-sm text-pink-600">{String(uploadM.error)}</div>
      ) : null}
    </div>
  );
}
