import ProgressBar from "./ui/ProgressBar";
import { Card } from "./ui/Card";

type Props = {
  title: string;
  mastery: number;
};

export default function MasteryCard({ title, mastery }: Props) {
  return (
    <Card className="space-y-3">
      <div className="flex justify-between">
        <h3 className="font-medium text-slate-700">{title}</h3>
        <span className="text-sm text-slate-500">{mastery}%</span>
      </div>

      <ProgressBar value={mastery} />
    </Card>
  );
}