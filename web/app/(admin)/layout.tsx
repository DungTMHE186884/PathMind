import AppShell from "@/components/layout/AppShell";
import StaffGuard from "@/components/admin/StaffGuard";
import StaffSidebar from "@/components/staff/StaffSidebar";

// The staff console has its own frame and navigation: R&D and administrators
// never share the learner/educator sidebar.
export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <StaffGuard>
      <AppShell sidebar={<StaffSidebar />}>{children}</AppShell>
    </StaffGuard>
  );
}
