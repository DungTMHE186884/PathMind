"use client";

import { useTranslation } from "react-i18next";

import KnowledgeTreePage from "@/components/knowledge-tree/KnowledgeTreePage";
import StaffPage from "@/components/staff/StaffPage";

export default function StaffKnowledgePage() {
  const { t } = useTranslation();
  return (
    <StaffPage
      wide
      title={t("Knowledge")}
      subtitle={t("The main knowledge tree, its document store and import/export. Only R&D and administrators see this.")}
    >
      <KnowledgeTreePage />
    </StaffPage>
  );
}
