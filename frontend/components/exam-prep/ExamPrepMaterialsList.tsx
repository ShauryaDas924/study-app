"use client";

import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type ExamPrepMaterial, type UUID } from "@/lib/api";
import { Button } from "@/components/ui/Button";

function typeLabel(value: string) {
  return value.replace(/_/g, " ");
}

function Badge({
  children,
  tone = "slate",
}: {
  children: ReactNode;
  tone?: "slate" | "green" | "amber" | "rose" | "blue";
}) {
  const tones = {
    slate: "border-slate-100 bg-slate-50 text-slate-600",
    green: "border-emerald-100 bg-emerald-50 text-emerald-700",
    amber: "border-amber-100 bg-amber-50 text-amber-700",
    rose: "border-pink-100 bg-pink-50 text-pink-700",
    blue: "border-sky-100 bg-sky-50 text-sky-700",
  };

  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}

function materialStatus(material: ExamPrepMaterial) {
  if (material.extraction_status === "failed") {
    return { label: "Needs attention", tone: "rose" as const };
  }
  if (material.extraction_status !== "success") {
    return { label: "Processing text", tone: "amber" as const };
  }
  if (material.question_count > 0) {
    return { label: "Already extracted", tone: "green" as const };
  }
  return { label: "Needs extraction", tone: "amber" as const };
}

export default function ExamPrepMaterialsList({
  classId,
  materials,
  selectedIds,
  setSelectedIds,
}: {
  classId: UUID;
  materials: ExamPrepMaterial[];
  selectedIds: UUID[];
  setSelectedIds: (ids: UUID[]) => void;
}) {
  const qc = useQueryClient();
  const [bulkStatus, setBulkStatus] = useState<Record<UUID, { status: string; message?: string }>>({});
  const [bulkSummary, setBulkSummary] = useState<string>("");
  const selectedMaterials = useMemo(
    () => materials.filter((material) => selectedIds.includes(material.id)),
    [materials, selectedIds]
  );
  const materialsReadyForBulkExtraction = useMemo(
    () => selectedMaterials.filter((material) => material.extraction_status === "success" && !material.question_count),
    [selectedMaterials]
  );
  const selectedAlreadyExtracted = selectedMaterials.filter((material) => material.question_count > 0).length;
  const selectedNeedsAttention = selectedMaterials.filter((material) => material.extraction_status === "failed").length;
  const selectedWaitingForText = selectedMaterials.filter((material) => material.extraction_status !== "success" && material.extraction_status !== "failed").length;
  const failedMaterials = materials.filter((material) => material.extraction_status === "failed");
  const totalQuestions = materials.reduce((sum, material) => sum + Number(material.question_count || 0), 0);

  const extractM = useMutation({
    mutationFn: (materialId: UUID) => api.extractExamPrepQuestions(materialId),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["exam-prep-materials", classId] });
    },
  });

  const bulkExtractM = useMutation({
    mutationFn: async () => {
      const results: { id: UUID; status: "success" | "failed" | "skipped"; message?: string }[] = [];
      setBulkSummary("");

      if (!selectedMaterials.length) {
        return results;
      }

      for (const material of selectedMaterials) {
        if (material.extraction_status !== "success") {
          results.push({ id: material.id, status: "skipped", message: "Text extraction is not ready." });
          setBulkStatus((current) => ({
            ...current,
            [material.id]: { status: "skipped", message: "Text extraction is not ready." },
          }));
          continue;
        }

        if (material.question_count > 0) {
          results.push({ id: material.id, status: "skipped", message: "Already has extracted questions." });
          setBulkStatus((current) => ({
            ...current,
            [material.id]: { status: "skipped", message: "Already has extracted questions." },
          }));
          continue;
        }

        setBulkStatus((current) => ({
          ...current,
          [material.id]: { status: "extracting" },
        }));

        try {
          await api.extractExamPrepQuestions(material.id);
          results.push({ id: material.id, status: "success" });
          setBulkStatus((current) => ({
            ...current,
            [material.id]: { status: "extracted" },
          }));
        } catch (error) {
          const message = error instanceof Error ? error.message : "Question extraction failed.";
          results.push({ id: material.id, status: "failed", message });
          setBulkStatus((current) => ({
            ...current,
            [material.id]: { status: "failed", message },
          }));
        }
      }

      return results;
    },
    onSuccess: async (results) => {
      const extracted = results.filter((result) => result.status === "success").length;
      const failed = results.filter((result) => result.status === "failed").length;
      const skipped = results.filter((result) => result.status === "skipped").length;
      setBulkSummary(`${extracted} extracted, ${skipped} skipped, ${failed} failed.`);
      await qc.invalidateQueries({ queryKey: ["exam-prep-materials", classId] });
    },
  });

  function toggle(id: UUID) {
    if (selectedIds.includes(id)) {
      setSelectedIds(selectedIds.filter((item) => item !== id));
    } else {
      setSelectedIds([...selectedIds, id]);
    }
  }

  if (!materials.length) {
    return (
      <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/70 p-5 text-sm text-slate-600">
        No evidence uploaded yet. Add past exams, homework, notes, review sheets, or practice banks to unlock question recommendations.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="rounded-xl border border-slate-100 bg-white/80 p-4 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="text-sm font-semibold text-slate-900">Evidence Library</div>
            <div className="mt-1 text-xs text-slate-500">
              {selectedIds.length} selected · {selectedAlreadyExtracted} already extracted · {materialsReadyForBulkExtraction.length} need extraction
              {selectedNeedsAttention || selectedWaitingForText ? ` · ${selectedNeedsAttention + selectedWaitingForText} need attention` : ""}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="ghost" className="px-3 py-1 text-xs" onClick={() => setSelectedIds(materials.map((m) => m.id))}>
              Select all
            </Button>
            <Button variant="ghost" className="px-3 py-1 text-xs" onClick={() => setSelectedIds([])}>
              Deselect all
            </Button>
            <Button
              onClick={() => bulkExtractM.mutate()}
              disabled={!selectedIds.length || bulkExtractM.isPending}
              className="px-3 py-1 text-xs"
            >
              {bulkExtractM.isPending ? "Extracting..." : "Extract selected"}
            </Button>
          </div>
        </div>

        <div className="mt-3 grid gap-2 sm:grid-cols-4">
          <div className="rounded-lg bg-slate-50 px-3 py-2">
            <div className="text-lg font-semibold text-slate-900">{materials.length}</div>
            <div className="text-xs text-slate-500">materials</div>
          </div>
          <div className="rounded-lg bg-emerald-50 px-3 py-2">
            <div className="text-lg font-semibold text-emerald-700">{totalQuestions}</div>
            <div className="text-xs text-emerald-700">questions extracted</div>
          </div>
          <div className="rounded-lg bg-amber-50 px-3 py-2">
            <div className="text-lg font-semibold text-amber-700">{materialsReadyForBulkExtraction.length}</div>
            <div className="text-xs text-amber-700">selected need extraction</div>
          </div>
          <div className="rounded-lg bg-pink-50 px-3 py-2">
            <div className="text-lg font-semibold text-pink-700">{failedMaterials.length}</div>
            <div className="text-xs text-pink-700">need attention</div>
          </div>
        </div>

        {bulkSummary ? <div className="mt-2 text-xs text-slate-600">{bulkSummary}</div> : null}
        {bulkExtractM.error ? <div className="mt-2 text-sm text-pink-600">{String(bulkExtractM.error)}</div> : null}
        <div className="mt-2 text-xs text-slate-500">
          Low-confidence extraction may miss some questions. Bulk extraction skips materials that already have questions.
        </div>

        {failedMaterials.length ? (
          <details className="mt-3 rounded-lg border border-pink-100 bg-pink-50 px-3 py-2 text-xs text-pink-700">
            <summary className="cursor-pointer font-medium">{failedMaterials.length} material{failedMaterials.length === 1 ? "" : "s"} need attention</summary>
            <div className="mt-2 space-y-1">
              {failedMaterials.slice(0, 8).map((material) => (
                <div key={material.id} className="truncate">
                  {material.filename}{material.parse_error ? ` - ${material.parse_error}` : ""}
                </div>
              ))}
            </div>
          </details>
        ) : null}
      </div>

      <div className="max-h-[520px] space-y-2 overflow-y-auto pr-1">
        {materials.map((material) => {
          const selected = selectedIds.includes(material.id);
          const isExtracting = extractM.isPending && extractM.variables === material.id;
          const rowStatus = bulkStatus[material.id];
          const status = materialStatus(material);

          return (
            <div
              key={material.id}
              className={[
                "rounded-xl border bg-white/80 p-3 transition",
                selected ? "border-pink-200 shadow-sm" : "border-slate-100",
              ].join(" ")}
            >
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <label className="flex min-w-0 items-start gap-3">
                  <input
                    type="checkbox"
                    checked={selected}
                    onChange={() => toggle(material.id)}
                    className="mt-1"
                  />
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium text-slate-900">{material.filename}</span>
                    <span className="mt-1 flex flex-wrap gap-1.5">
                      <Badge tone="blue">{typeLabel(material.material_type)}</Badge>
                      <Badge tone={status.tone}>{status.label}</Badge>
                      <Badge>{material.question_count || 0} question{material.question_count === 1 ? "" : "s"}</Badge>
                    </span>
                    {material.parse_error ? (
                      <span className="mt-1 block text-xs text-pink-600">{material.parse_error}</span>
                    ) : null}
                    {rowStatus ? (
                      <span className={rowStatus.status === "failed" ? "mt-1 block text-xs text-pink-600" : "mt-1 block text-xs text-slate-500"}>
                        {rowStatus.status}{rowStatus.message ? `: ${rowStatus.message}` : ""}
                      </span>
                    ) : null}
                  </span>
                </label>

                <Button
                  variant="secondary"
                  className="px-3 py-1 text-xs"
                  onClick={() => extractM.mutate(material.id)}
                  disabled={material.extraction_status !== "success" || isExtracting || bulkExtractM.isPending}
                >
                  {isExtracting ? "Extracting..." : material.question_count ? "Re-extract" : "Extract questions"}
                </Button>
              </div>
            </div>
          );
        })}
      </div>

      {extractM.error ? <div className="text-sm text-pink-600">{String(extractM.error)}</div> : null}
    </div>
  );
}
