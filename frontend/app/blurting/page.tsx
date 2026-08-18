import BlurtingMindMapPage from "@/components/blurting-mindmap/BlurtingMindMapPage";
import RequireAuth from "@/components/RequireAuth";

export default function BlurtingPage() {
  return (
    <RequireAuth>
      <BlurtingMindMapPage />
    </RequireAuth>
  );
}
