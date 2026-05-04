"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useStore } from "@/store/useStore";
import { type MouseEvent, useState } from "react";
import RequireAuth from "@/components/RequireAuth";

function ClassesContent() {
  const qc = useQueryClient();
  const setClass = useStore((s) => s.setSelectedClassId);
  const selected = useStore((s) => s.selectedClassId);

  const [name, setName] = useState("");

  const classesQ = useQuery({
    queryKey: ["classes"],
    queryFn: api.listClasses,
  });

  const createM = useMutation({
    mutationFn: api.createClass,
    onSuccess: (c) => {
      qc.invalidateQueries({ queryKey: ["classes"] });
      setClass(c.id);
      setName("");
    },
  });

  const deleteM = useMutation({
    mutationFn: api.deleteClass,
    onSuccess: (_data, classId) => {
      qc.invalidateQueries({ queryKey: ["classes"] });

      if (useStore.getState().selectedClassId === classId) {
        setClass("");
      }
    },
  });

  function handleDeleteCourse(
    e: MouseEvent<HTMLButtonElement>,
    classId: string,
    className: string
  ) {
    e.stopPropagation();

    const ok = window.confirm(
      `Delete "${className}" and all of its notes, flashcards, practice, and tutor data?`
    );

    if (!ok) return;

    deleteM.mutate(classId);
  }

  return (
    <div className="app-shell space-y-6">
      <h1 className="text-2xl font-semibold" style={{ color: "var(--text-main)" }}>
        Your Courses
      </h1>

      {/* CREATE */}
      <div className="flex gap-3">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Course name (e.g. Calculus II)"
          className="app-input px-4 py-2 w-64"
        />
        <button
          onClick={() => createM.mutate({ name })}
          className="app-button-primary px-4 py-2"
        >
          Create
        </button>
      </div>

      {/* LIST */}
      <div className="space-y-2">
        {classesQ.data?.map((c) => (
          <div
            key={c.id}
            onClick={() => setClass(c.id)}
            className="p-4 rounded-2xl border cursor-pointer transition"
            style={
              selected === c.id
                ? {
                    background: "var(--gradient-main)",
                    borderColor: "var(--border-soft)",
                    color: "var(--text-main)",
                    boxShadow: "var(--shadow-button)",
                  }
                : {
                    background: "var(--gradient-card)",
                    borderColor: "var(--border-soft)",
                    color: "var(--text-main)",
                  }
            }
          >
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="truncate font-medium">{c.name}</div>
                {c.term && (
                  <div className="text-sm opacity-70">{c.term}</div>
                )}
              </div>

              <button
                className="rounded-xl border px-3 py-2 text-sm transition"
                disabled={deleteM.isPending && deleteM.variables === c.id}
                onClick={(e) => handleDeleteCourse(e, c.id, c.name)}
                style={{
                  background: "rgba(255,255,255,0.68)",
                  borderColor: "var(--border-soft)",
                  color: "#7a4551",
                }}
              >
                {deleteM.isPending && deleteM.variables === c.id
                  ? "Deleting..."
                  : "Delete"}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ClassesPage() {
  return (
    <RequireAuth>
      <ClassesContent />
    </RequireAuth>
  );
}
