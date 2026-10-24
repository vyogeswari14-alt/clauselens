import type { Analysis } from './types'
async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try { const body = await res.json(); detail = body.detail || detail } catch {}
    throw new Error(detail)
  }
  return res.json()
}
export async function uploadContract(file: File) {
  const data = new FormData(); data.append('file', file)
  return request<{document_id:number;filename:string;file_type:string;characters_extracted:number;page_references_available:boolean}>('/api/documents/upload', {method:'POST',body:data})
}
export async function analyze(document_id:number, requirements:string[]): Promise<Analysis> {
  return request('/api/analysis/start', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({document_id,requirements})})
}
export async function getHistory() { return request<Array<{id:number;filename:string;overall_risk:string;created_at:string|null;finding_count:number}>>('/api/analysis/history') }
export async function askGuidance(question:string,language:string) {
  return request<{answer:string;language:string;sources:Array<{name:string;topic:string;official_url:string}>;disclaimer:string}>('/api/guidance/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question,language})})
}
export async function negotiate(clause_text:string,goal:string,tone:string) {
  return request<{draft:string;disclaimer:string}>('/api/clauses/negotiation',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({clause_text,goal,tone})})
}
export async function getHealth() { return request<{status:string;service:string}>('/api/health') }
