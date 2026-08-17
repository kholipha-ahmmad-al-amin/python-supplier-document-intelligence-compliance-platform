CREATE TABLE suppliers (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE evidence (
  id INTEGER PRIMARY KEY,
  supplier_id INTEGER NOT NULL,
  filename TEXT NOT NULL,
  document_type TEXT NOT NULL,
  status TEXT NOT NULL,
  policy_outcome TEXT,
  quality_score REAL,
  confidence REAL,
  extracted_text TEXT,
  explanation_json TEXT,
  findings_json TEXT,
  days_until_expiry INTEGER,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(supplier_id) REFERENCES suppliers(id)
);

CREATE TABLE audit_events (
  id INTEGER PRIMARY KEY,
  actor TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  action TEXT NOT NULL,
  description TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX evidence_supplier_index ON evidence(supplier_id);
CREATE INDEX audit_entity_index ON audit_events(entity_type, entity_id);
