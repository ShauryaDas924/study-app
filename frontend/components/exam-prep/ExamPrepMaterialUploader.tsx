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

const UPLOAD_CONCURRENCY = 2;

type UploadResult = {
  fileName: string;
  material?: ExamPrepMaterial;
  error?: string;
};

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
  const [uploadSummary, setUploadSummary] = useState<{ uploaded: number; total: number; failures: string[] } | null>(null);

  function fileKey(file: File) {
    return `${file.name}-${file.size}-${file.lastModified}`;
  }

  async function uploadWithConcurrency(batchFiles: File[]): Promise<UploadResult[]> {
    const results: UploadResult[] = new Array(batchFiles.length);
    let nextIndex = 0;

    async function worker() {
      while (nextIndex < batchFiles.length) {
        const index = nextIndex;
        nextIndex += 1;
        const selectedFile = batchFiles[index];
        const key = fileKey(selectedFile);

        setUploadStatus((current) => ({
          ...current,
          [key]: { status: "uploading" },
        }));

        try {
          const material = await api.uploadExamPrepMaterial(classId, materialType, selectedFile);
          results[index] = { fileName: selectedFile.name, material };
          setUploadStatus((current) => ({
            ...current,
            [key]: {
              status: material.extraction_status === "failed" ? "uploaded, text extraction failed" : "uploaded",
              message: material.parse_error ?? undefined,
            },
          }));
        } catch (error) {
          const message = error instanceof Error ? error.message : "Upload failed";
          results[index] = { fileName: selectedFile.name, error: message };
          setUploadStatus((current) => ({
            ...current,
            [key]: { status: "failed", message },
          }));
        }
      }
    }

    await Promise.all(
      Array.from({ length: Math.min(UPLOAD_CONCURRENCY, batchFiles.length) }, () => worker())
    );

    return results;
  }

  const uploadM = useMutation({
    mutationFn: async () => {
      if (!files.length) throw new Error("Choose one or more files first.");
      const batchFiles = [...files];
      setUploadSummary(null);

      const results = await uploadWithConcurrency(batchFiles);
      const uploaded = results
        .map((result) => result.material)
        .filter((material): material is ExamPrepMaterial => Boolean(material));
      const failures = results
        .filter((result) => result.error)
        .map((result) => result.fileName);

      return { uploaded, failures, total: batchFiles.length };
    },
    onSuccess: async ({ uploaded, failures, total }) => {
      uploaded.forEach((material) => onUploaded?.(material));
      await qc.invalidateQueries({ queryKey: ["exam-prep-materials", classId] });
      setUploadSummary({ uploaded: uploaded.length, failures, total });
      if (uploaded.length === total) {
        setFiles([]);
      }
    },
  });

  return (
    <div className="space-y-4 rounded-xl border border-slate-100 bg-white/80 p-4 shadow-sm">
      <div>
        <div className="text-sm font-semibold text-slate-900">Upload evidence</div>
        <div className="mt-1 text-xs text-slate-500">
          Add PDF, TXT, Markdown, or PPTX evidence. Each file must be 10 MiB or smaller.
        </div>
      </div>

      <div className="grid gap-3 lg:grid-cols-[200px_1fr_auto] lg:items-end">
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
            accept=".pdf,.txt,.md,.pptx"
            disabled={uploadM.isPending}
            onChange={(e) => {
              setFiles(Array.from(e.target.files ?? []));
              setUploadStatus({});
              setUploadSummary(null);
            }}
            className="block w-full rounded-xl border border-dashed border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600 file:mr-3 file:rounded-full file:border-0 file:bg-white file:px-3 file:py-1 file:text-xs file:font-medium file:text-slate-600"
          />
        </div>

        <Button onClick={() => uploadM.mutate()} disabled={!files.length || uploadM.isPending} className="whitespace-nowrap">
          {uploadM.isPending ? "Uploading..." : `Upload ${files.length || ""}`.trim()}
        </Button>
      </div>

      {files.length ? (
        <div className="rounded-xl bg-slate-50 px-3 py-2 text-xs text-slate-600">
          <div className="font-medium text-slate-700">{files.length} file{files.length === 1 ? "" : "s"} selected</div>
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
      {uploadSummary ? (
        <div className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2 text-xs text-slate-600">
          Uploaded {uploadSummary.uploaded}/{uploadSummary.total}
          {uploadSummary.failures.length ? (
            <div className="mt-1 text-pink-600">
              Failed: {uploadSummary.failures.join(", ")}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
