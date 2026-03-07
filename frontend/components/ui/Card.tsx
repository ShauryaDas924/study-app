import { ReactNode } from "react";

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={[
        "bg-white rounded-2xl border border-slate-100",
        "shadow-sm hover:shadow-md transition",
        "p-6",
        className,
      ].join(" ")}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  subtitle,
  right,
}: {
  title: string;
  subtitle?: string;
  right?: ReactNode;
}) {
  return (
    <div className="mb-5 flex justify-between">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
        {subtitle && (
          <p className="text-sm text-slate-500 mt-1">{subtitle}</p>
        )}
      </div>
      {right}
    </div>
  );
}