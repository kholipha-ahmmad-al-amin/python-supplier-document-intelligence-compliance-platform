import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, FileSearch, FileUp, Filter, LoaderCircle, ScanSearch, ShieldCheck, XCircle } from "lucide-react";
import { FormEvent, useState } from "react";
import { create } from "zustand";

type Role = "admin" | "analyst" | "reviewer";
type Evidence = { id: number; supplier_id: number; filename: string; document_type: string; status: string; policy_outcome?: string; quality_score?: number; confidence?: number; findings?: string[] };
type Supplier = { id: number; name: string };
const API = import.meta.env.VITE_API_URL ?? "http://localhost:8100";
const useSession = create<{ role: Role; setRole: (role: Role) => void }>(set => ({ role: "admin", setRole: role => set({ role }) }));

async function request<T>(path: string, role: Role, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API}${path}`, { ...options, headers: { "X-Role": role, "X-Actor": "web-reviewer", ...(options.headers ?? {}) } });
  if (!response.ok) throw new Error((await response.json().catch(() => ({ detail: "Request failed" }))).detail);
  return response.json();
}

export default function App() {
  const { role, setRole } = useSession();
  const [supplierName, setSupplierName] = useState("");
  const [supplierId, setSupplierId] = useState("");
  const [documentType, setDocumentType] = useState("insurance_certificate");
  const [hintText, setHintText] = useState("insurance policy coverage insurer");
  const [expiry, setExpiry] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [filter, setFilter] = useState("all");
  const suppliers = useQuery({ queryKey: ["suppliers", role], queryFn: () => request<Supplier[]>("/suppliers", role), enabled: false });
  const evidence = useQuery({ queryKey: ["evidence", role], queryFn: () => request<Evidence[]>("/evidence", role) });
  const createSupplier = useMutation({ mutationFn: () => request<Supplier>("/suppliers", role, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: supplierName }) }), onSuccess: () => { setSupplierName(""); suppliers.refetch(); } });
  const upload = useMutation({
    mutationFn: async () => {
      if (!file || !supplierId) throw new Error("Select a supplier and evidence file");
      const body = new FormData(); body.set("supplier_id", supplierId); body.set("document_type", documentType); body.set("hint_text", hintText); body.set("file", file); if (expiry) body.set("expires_on", expiry);
      return request<Evidence>("/evidence", role, { method: "POST", body });
    },
    onSuccess: () => { setFile(null); evidence.refetch(); },
  });
  const review = useMutation({ mutationFn: ({ id, decision }: { id: number; decision: string }) => request<Evidence>(`/evidence/${id}/review`, role, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision, note: `Reviewer selected ${decision}` }) }), onSuccess: () => evidence.refetch() });
  const visible = (evidence.data ?? []).filter(item => filter === "all" || item.status === filter || item.policy_outcome === filter);
  const submitSupplier = (event: FormEvent) => { event.preventDefault(); createSupplier.mutate(); };
  const submitUpload = (event: FormEvent) => { event.preventDefault(); upload.mutate(); };

  return <main><aside><div className="brand"><ShieldCheck /><div><b>Veritas Evidence</b><span>Supplier intelligence</span></div></div><nav><a className="active"><ScanSearch />Review queue</a><a><FileSearch />Evidence register</a><a><ShieldCheck />Policy controls</a></nav><div className="operator"><span>Role context</span><select value={role} onChange={event => setRole(event.target.value as Role)}><option value="admin">admin</option><option value="analyst">analyst</option><option value="reviewer">reviewer</option></select></div></aside><section className="workspace"><header><div><p className="eyebrow">Supplier document intelligence</p><h1>Evidence that can defend a supplier decision.</h1><p>Extract, classify, score, and review supplier documents in a governed queue with a traceable chain of evidence.</p></div><div className="signal"><CheckCircle2 />API processing online</div></header><div className="grid top-grid"><article className="panel queue"><div className="panel-heading"><div><p className="eyebrow">Review queue</p><h2>Policy signal review</h2></div><div className="filter"><Filter /><select value={filter} onChange={event => setFilter(event.target.value)}><option value="all">All evidence</option><option value="review">Needs review</option><option value="pass">Policy pass</option><option value="fail">Policy fail</option></select></div></div>{evidence.isLoading ? <Loading /> : <div className="evidence-list">{visible.map(item => <EvidenceCard key={item.id} item={item} role={role} busy={review.isPending} onReview={decision => review.mutate({ id: item.id, decision })} />)}{!visible.length ? <div className="empty"><FileSearch /><p>No evidence matches the current filter.</p></div> : null}</div>}</article><article className="panel intake"><p className="eyebrow">Evidence intake</p><h2>Begin a controlled review</h2><form onSubmit={submitSupplier}><label>New supplier<input value={supplierName} onChange={event => setSupplierName(event.target.value)} placeholder="Northstar Industrial" required /></label><button disabled={createSupplier.isPending}>{createSupplier.isPending ? "Creating" : "Create supplier"}</button></form><div className="divider" /><button type="button" className="minor" onClick={() => suppliers.refetch()}>Load suppliers</button><form onSubmit={submitUpload}><label>Supplier<select value={supplierId} onChange={event => setSupplierId(event.target.value)} required><option value="">Select supplier</option>{(suppliers.data ?? []).map(supplier => <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}</select></label><label>Policy type<select value={documentType} onChange={event => setDocumentType(event.target.value)}><option value="insurance_certificate">Insurance certificate</option><option value="tax_certificate">Tax certificate</option><option value="sanctions_screening">Sanctions screening</option><option value="quality_certificate">Quality certificate</option></select></label><label>Review hint<textarea value={hintText} onChange={event => setHintText(event.target.value)} /></label><label>Expiry date<input type="date" value={expiry} onChange={event => setExpiry(event.target.value)} /></label><label className="file"><FileUp />{file?.name ?? "Select PDF or image"}<input type="file" accept=".png,.jpg,.jpeg,.pdf" onChange={event => setFile(event.target.files?.[0] ?? null)} required /></label><button disabled={upload.isPending}>{upload.isPending ? "Processing evidence" : "Extract and route to review"}</button>{upload.error ? <p className="error">{upload.error.message}</p> : null}</form></article></div></section></main>;
}

function EvidenceCard({ item, role, onReview, busy }: { item: Evidence; role: Role; onReview: (decision: string) => void; busy: boolean }) {
  const severity = item.policy_outcome === "fail" ? "fail" : item.policy_outcome === "review" ? "review" : "pass";
  return <div className="evidence-card"><div className="evidence-title"><div className={`state ${severity}`}>{severity === "fail" ? <XCircle /> : severity === "review" ? <AlertTriangle /> : <CheckCircle2 />}</div><div><b>{item.filename}</b><p>{item.document_type.replaceAll("_", " ")} · supplier #{item.supplier_id}</p></div></div><div className="metrics"><span><b>{Math.round((item.confidence ?? 0) * 100)}%</b> confidence</span><span><b>{Math.round((item.quality_score ?? 0) * 100)}%</b> quality</span><span className={`tag ${severity}`}>{item.policy_outcome ?? item.status}</span></div>{item.findings?.length ? <p className="findings">{item.findings.join(" · ")}</p> : <p className="findings positive">No blocking policy findings.</p>}{item.status === "review" && (role === "admin" || role === "reviewer") ? <div className="actions"><button onClick={() => onReview("accepted")} disabled={busy}>Accept</button><button className="outline" onClick={() => onReview("correction_requested")} disabled={busy}>Request correction</button><button className="danger" onClick={() => onReview("rejected")} disabled={busy}>Reject</button></div> : null}</div>;
}

function Loading() { return <div className="loading"><LoaderCircle />Loading evidence queue</div>; }
