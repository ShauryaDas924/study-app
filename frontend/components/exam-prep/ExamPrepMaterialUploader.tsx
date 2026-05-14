"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type ExamPrepMaterial, type ExamPrepMaterialType, type UUID } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";

const materialTypes: { value: ExamPrepMaterialType; label: string }[] = [
  { value: "syllabus", label: "Syllabus" },
  { value: "notes", label: "Notes" },
  { value: "past_exam", label: "Past exam" },
  { value: "past_homework", label: "Past homework" },
  { value: "practice_bank", label: "Practice bank" },
  { value: "review_sheet", label: "Review sheet" },
  { value: "professor_announcement", label: "Professor announcement" },
  { value: "answer_key", label: "Answer key" },
  { value: "solutions", label: "Solutions" },
  { value: "other", label: "Other" },
];

export default function ExamPrepMaterialUploader({
  classId,
  onUploaded,
}: {
  classId: UUID;
  onUploaded?: (material: ExamPrepMaterial) => void;
}) {
  const qc = useQueryClient();
  const [files, setFiles] = useState<File[]>([]);
  const [materialType, setMaterialType] = useState<ExamPrepMaterialType>("practice_bank");
  const [uploadStatus, setUploadStatus] = useState<Record<string, { status: string; message?: string }>>({});

  function fileKey(file: File) {
    return `${file.name}-${file.size}-${file.lastModified}`;
  }

  const uploadM = useMutation({
    mutationFn: async () => {
      if (!files.length) throw new Error("Choose one or more files first.");

      const uploaded: ExamPrepMaterial[] = [];
      const failures: string[] = [];

      for (const selectedFile of files) {
        const key = fileKey(selectedFile);
        setUploadStatus((current) => ({
          ...current,
          [key]: { status: "uploading" },
        }));

        try {
          const material = await api.uploadExamPrepMaterial(classId, materialType, selectedFile);
          uploaded.push(material);
          setUploadStatus((current) => ({
            ...current,
            [key]: { status: "uploaded" },
          }));
        } catch (error) {
          failures.push(selectedFile.name);
          setUploadStatus((current) => ({
            ...current,
            [key]: { status: "failed", message: error instanceof Error ? error.message : "Upload failed" },
          }));
        }
      }

      return { uploaded, failures };
    },
    onSuccess: async ({ uploaded }) => {
      uploaded.forEach((material) => onUploaded?.(material));
      await qc.invalidateQueries({ queryKey: ["exam-prep-materials", classId] });
      if (uploaded.length === files.length) {
        setFiles([]);
      }
    },
  });

  return (
    <div className="space-y-3 rounded-xl border border-slate-100 p-3">
      <div className="text-sm font-medium text-slate-900">Exam Lockdown materials</div>
      <div className="grid gap-3 md:grid-cols-[180px_1fr_auto] md:items-end">
        <div>
          <div className="mb-1 text-xs text-slate-500">Material type</div>
          <Select
            value={materialType}
            onChange={(e) => setMaterialType(e.target.value as ExamPrepMaterialType)}
            disabled={uploadM.isPending}
          >
            {materialTypes.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </Select>
        </div>

        <div>
          <div className="mb-1 text-xs text-slate-500">Files</div>
          <input
            type="file"
            multiple
            accept=".pdf,.txt,.md,.png,.jpg,.jpeg,.ppt,.pptx"
            disabled={uploadM.isPending}
            onChange={(e) => {
              setFiles(Array.from(e.target.files ?? []));
              setUploadStatus({});
            }}
            className="block w-full text-sm text-slate-600"
          />
        </div>

        <Button onClick={() => uploadM.mutate()} disabled={!files.length || uploadM.isPending}>
          {uploadM.isPending ? "Uploading..." : `Upload ${files.length || ""}`.trim()}
        </Button>
      </div>

      {files.length ? (
        <div className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
          {files.length} file{files.length === 1 ? "" : "s"} selected
          <div className="mt-1 space-y-1">
            {files.map((selectedFile) => {
              const status = uploadStatus[fileKey(selectedFile)];
              return (
                <div key={fileKey(selectedFile)} className="flex flex-wrap items-center gap-2">
                  <span className="truncate">{selectedFile.name}</span>
                  {status ? (
                    <span className={status.status === "failed" ? "text-pink-600" : "text-slate-500"}>
                      {status.status}{status.message ? `: ${status.message}` : ""}
                    </span>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      ) : null}

      {uploadM.error ? <div className="text-sm text-pink-600">{String(uploadM.error)}</div> : null}
      <div className="text-xs text-slate-500">
        Upload only material you want used as evidence. Question recommendations come from extracted uploaded materials.
      </div>
    </div>
  );
}
