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
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Your Classes</h1>

      {/* CREATE */}
      <div className="flex gap-3">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Class name (e.g. Calculus II)"
          className="border rounded-xl px-4 py-2 w-64"
        />
        <button
          onClick={() => createM.mutate({ name })}
          className="bg-green-500 text-white px-4 py-2 rounded-xl"
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
            className={`p-4 rounded-xl border cursor-pointer ${
              selected === c.id
                ? "bg-green-100 border-green-400"
                : "bg-white"
            }`}
          >
            {c.name}
          </div>
        ))}
      </div>
    </div>
  );
}