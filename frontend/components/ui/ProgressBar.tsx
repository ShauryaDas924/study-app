type Props = {
  value: number;
};

export default function ProgressBar({ value }: Props) {
  return (
    <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden">
      <div
        className="h-full bg-gradient-to-r from-emerald-300 via-green-300 to-blue-300 transition-all duration-700"
        style={{ width: `${value}%` }}
      />
    </div>
  );
}