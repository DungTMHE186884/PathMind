import AdminOnlyGuard from "@/components/common/AdminOnlyGuard";

// Memory is a Personalization surface: administrators only when sign-in is on.
// Bare shell — each memory page owns its own padding + scroll behavior.
// Hub uses `overflow-y-auto` with a max-width container; the L2/L3
// workbench pages use a full-height flex column with internal scrolling
// per pane (preview / LLM workspace) so the outer page never grows.
export default function MemoryLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <main className="flex h-full min-h-0 flex-col bg-[var(--background)]">
      <AdminOnlyGuard>{children}</AdminOnlyGuard>
    </main>
  );
}
