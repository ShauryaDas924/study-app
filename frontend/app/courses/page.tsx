"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useStore } from "@/store/useStore";
import { useState } from "react";

export default function ClassesPage() {
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
            {c.name}
          </div>
        ))}
      </div>
    </div>
  );
}