export type Finding = {
  id: number; category: string; severity: string; title: string; explanation: string;
  excerpt: string; page: number | null; evidence_status: string; recommendation: string
}
export type Analysis = {
  id: number; document_id: number; filename: string; requirements: string[];
  overall_risk: string; summary: string; created_at: string | null; findings: Finding[]
}
