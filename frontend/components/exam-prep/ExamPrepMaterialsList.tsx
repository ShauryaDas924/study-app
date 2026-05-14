"use client";

import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type ExamPrepMaterial, type UUID } from "@/lib/api";
import { Button } from "@/components/ui/Button";

function typeLabel(value: string) {
  return value.replace(/_/g, " ");
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
      <div className="rounded-xl border border-slate-100 bg-slate-50 p-3 text-sm text-slate-600">
        No exam-prep materials uploaded yet.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="rounded-xl border border-slate-100 p-3">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-sm font-medium text-slate-900">Uploaded materials</div>
            <div className="text-xs text-slate-500">
              {selectedIds.length} selected. Question recommendations come from extracted uploaded materials.
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="ghost" className="px-3 py-1 text-xs" onClick={() => setSelectedIds(materials.map((m) => m.id))}>
              Select all
            </Button>
            <Button variant="ghost" className="px-3 py-1 text-xs" onClick={() => setSelectedIds([])}>
              Deselect all
            </Button>
          </div>
        </div>

        <div className="mt-3 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div className="text-xs text-slate-500">
            {materialsReadyForBulkExtraction.length} selected material{materialsReadyForBulkExtraction.length === 1 ? "" : "s"} ready for new extraction.
          </div>
          <Button
            onClick={() => bulkExtractM.mutate()}
            disabled={!selectedIds.length || bulkExtractM.isPending}
          >
            {bulkExtractM.isPending ? "Extracting Selected..." : "Extract Questions from Selected"}
          </Button>
        </div>

        {bulkSummary ? <div className="mt-2 text-xs text-slate-600">{bulkSummary}</div> : null}
        {bulkExtractM.error ? <div className="mt-2 text-sm text-pink-600">{String(bulkExtractM.error)}</div> : null}
        <div className="mt-2 text-xs text-slate-500">
          Low-confidence extraction may miss some questions. Bulk extraction skips materials that already have questions.
        </div>
      </div>

      {materials.map((material) => {
        const selected = selectedIds.includes(material.id);
        const isExtracting = extractM.isPending && extractM.variables === material.id;
        const rowStatus = bulkStatus[material.id];

        return (
          <div key={material.id} className="rounded-xl border border-slate-100 p-3">
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
                  <span className="block text-xs capitalize text-slate-500">
                    {typeLabel(material.material_type)} - {material.extraction_status}
                    {material.question_count ? ` - ${material.question_count} question${material.question_count === 1 ? "" : "s"}` : ""}
                  </span>
                  {material.parse_error ? (
                    <span className="block text-xs text-pink-600">{material.parse_error}</span>
                  ) : null}
                  {rowStatus ? (
                    <span className={rowStatus.status === "failed" ? "block text-xs text-pink-600" : "block text-xs text-slate-500"}>
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
                {isExtracting ? "Extracting..." : material.question_count ? "Re-extract" : "Extract Questions"}
              </Button>
            </div>
          </div>
        );
      })}

      {extractM.error ? <div className="text-sm text-pink-600">{String(extractM.error)}</div> : null}
    </div>
  );
}
