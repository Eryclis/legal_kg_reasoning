// =============================================================
// Legal KG — CDC Art. 18 | Neo4j Aura Import Script
// Run each block individually in the Neo4j Browser Query tab.
// Base URL: https://raw.githubusercontent.com/Eryclis/legal_kg_reasoning/main/
//           01_kg_pilot/output/neo4j_data_importer/
// =============================================================

// ── 0. Limpar base (opcional — apaga tudo antes de reimportar) ─
MATCH (n) DETACH DELETE n;

// ── 1. Constraints ─────────────────────────────────────────────
// Drop existing constraints first (handles NODE KEY conflict from Data Importer)
DROP CONSTRAINT nodeId_LegalProvision_key       IF EXISTS;
DROP CONSTRAINT nodeId_LegalSubProvision_key    IF EXISTS;
DROP CONSTRAINT nodeId_Case_key                 IF EXISTS;
DROP CONSTRAINT nodeId_RepetitiveTopic_key      IF EXISTS;
DROP CONSTRAINT nodeId_STJThesis_key            IF EXISTS;
DROP CONSTRAINT nodeId_ConstitutionalControl_key IF EXISTS;
DROP CONSTRAINT nodeId_ExternalCitation_key     IF EXISTS;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:LegalProvision)        REQUIRE n.nodeId IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:LegalSubProvision)     REQUIRE n.nodeId IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Case)                  REQUIRE n.nodeId IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:RepetitiveTopic)       REQUIRE n.nodeId IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:STJThesis)             REQUIRE n.nodeId IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:ConstitutionalControl) REQUIRE n.nodeId IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:ExternalCitation)      REQUIRE n.nodeId IS UNIQUE;

// ── 2. Nodes: LegalProvision ───────────────────────────────────
LOAD CSV WITH HEADERS FROM
  'https://raw.githubusercontent.com/Eryclis/legal_kg_reasoning/main/01_kg_pilot/output/neo4j_data_importer/nodes_LegalProvision.csv'
AS row
CREATE (:LegalProvision {
  nodeId:   row.nodeId,
  law:      row.law,
  article:  toInteger(row.article),
  text:     row.text,
  is_stub:  toBoolean(row.is_stub)
});

// ── 3. Nodes: LegalSubProvision ────────────────────────────────
LOAD CSV WITH HEADERS FROM
  'https://raw.githubusercontent.com/Eryclis/legal_kg_reasoning/main/01_kg_pilot/output/neo4j_data_importer/nodes_LegalSubProvision.csv'
AS row
CREATE (:LegalSubProvision {
  nodeId:    row.nodeId,
  law:       row.law,
  article:   toInteger(row.article),
  sub_ref:   row.sub_ref,
  sub_type:  row.sub_type,
  text:      row.text,
  parent_id: row.parent_id
});

// ── 4. Nodes: Case ─────────────────────────────────────────────
LOAD CSV WITH HEADERS FROM
  'https://raw.githubusercontent.com/Eryclis/legal_kg_reasoning/main/01_kg_pilot/output/neo4j_data_importer/nodes_Case.csv'
AS row
CREATE (:Case {
  nodeId:           row.nodeId,
  title:            row.title,
  case_class:       row.case_class,
  full_text_hash:   row.full_text_hash,
  publication_date: row.publication_date,
  rapporteur:       row.rapporteur,
  adjudicating_body: row.adjudicating_body,
  summary:          row.summary,
  full_text_url:    row.full_text_url,
  authority_weight: toFloat(row.authority_weight),
  similar_count:    toInteger(row.similar_count),
  temporal_status:  row.temporal_status,
  has_rg:           toBoolean(row.has_rg),
  origin_state:     row.origin_state,
  court:            row.court,
  corpus_id:        toInteger(row.corpus_id)
});

// ── 5. Nodes: RepetitiveTopic ──────────────────────────────────
LOAD CSV WITH HEADERS FROM
  'https://raw.githubusercontent.com/Eryclis/legal_kg_reasoning/main/01_kg_pilot/output/neo4j_data_importer/nodes_RepetitiveTopic.csv'
AS row
CREATE (:RepetitiveTopic {
  nodeId:           row.nodeId,
  title:            row.title,
  thesis:           row.thesis,
  ementa:           row.ementa,
  question:         row.question,
  status:           row.status,
  status_confirmed: toBoolean(row.status_confirmed),
  publication_date: row.publication_date,
  source_url:       row.source_url,
  temporal_status:  row.temporal_status,
  has_rg:           toBoolean(row.has_rg),
  authority_weight: toFloat(row.authority_weight)
});

// ── 6. Nodes: STJThesis ────────────────────────────────────────
LOAD CSV WITH HEADERS FROM
  'https://raw.githubusercontent.com/Eryclis/legal_kg_reasoning/main/01_kg_pilot/output/neo4j_data_importer/nodes_STJThesis.csv'
AS row
CREATE (:STJThesis {
  nodeId:           row.nodeId,
  edition:          row.edition,
  thesis_text:      row.thesis_text,
  source_url:       row.source_url,
  temporal_status:  row.temporal_status,
  authority_weight: toFloat(row.authority_weight)
});

// ── 7. Nodes: ConstitutionalControl ───────────────────────────
LOAD CSV WITH HEADERS FROM
  'https://raw.githubusercontent.com/Eryclis/legal_kg_reasoning/main/01_kg_pilot/output/neo4j_data_importer/nodes_ConstitutionalControl.csv'
AS row
CREATE (:ConstitutionalControl {
  nodeId:           row.nodeId,
  title:            row.title,
  process_number:   row.process_number,
  summary:          row.summary,
  publication_date: row.publication_date,
  source_url:       row.source_url,
  temporal_status:  row.temporal_status,
  authority_weight: toFloat(row.authority_weight)
});

// ── 8. Nodes: ExternalCitation ────────────────────────────────
LOAD CSV WITH HEADERS FROM
  'https://raw.githubusercontent.com/Eryclis/legal_kg_reasoning/main/01_kg_pilot/output/neo4j_data_importer/nodes_ExternalCitation.csv'
AS row
CREATE (:ExternalCitation {
  nodeId:            row.nodeId,
  citation_raw:      row.citation_raw,
  inferred_type:     row.inferred_type,
  court:             row.court,
  authority_weight:  toFloat(row.authority_weight),
  case_number:       row.case_number,
  origin_state:      row.origin_state,
  adjudicating_body: row.adjudicating_body,
  rapporteur:        row.rapporteur,
  decision_date:     row.decision_date,
  cited_ementa:      row.cited_ementa
});

// ── 9. Rel: CONTROLLED_BY ─────────────────────────────────────
LOAD CSV WITH HEADERS FROM
  'https://raw.githubusercontent.com/Eryclis/legal_kg_reasoning/main/01_kg_pilot/output/neo4j_data_importer/rel_CONTROLLED_BY.csv'
AS row
MATCH (a {nodeId: row.start_id})
MATCH (b {nodeId: row.end_id})
CREATE (a)-[:CONTROLLED_BY {weight: toFloat(row.weight)}]->(b);

// ── 10. Rel: INTERPRETED_BY_BINDING_THESIS ────────────────────
LOAD CSV WITH HEADERS FROM
  'https://raw.githubusercontent.com/Eryclis/legal_kg_reasoning/main/01_kg_pilot/output/neo4j_data_importer/rel_INTERPRETED_BY_BINDING_THESIS.csv'
AS row
MATCH (a {nodeId: row.start_id})
MATCH (b {nodeId: row.end_id})
CREATE (a)-[:INTERPRETED_BY_BINDING_THESIS {weight: toFloat(row.weight)}]->(b);

// ── 11. Rel: INTERPRETED_BY_LEADING_CASE ─────────────────────
LOAD CSV WITH HEADERS FROM
  'https://raw.githubusercontent.com/Eryclis/legal_kg_reasoning/main/01_kg_pilot/output/neo4j_data_importer/rel_INTERPRETED_BY_LEADING_CASE.csv'
AS row
MATCH (a {nodeId: row.start_id})
MATCH (b {nodeId: row.end_id})
CREATE (a)-[:INTERPRETED_BY_LEADING_CASE {weight: toFloat(row.weight)}]->(b);

// ── 12. Rel: INTERPRETED_BY_ISOLATED_CASE ────────────────────
LOAD CSV WITH HEADERS FROM
  'https://raw.githubusercontent.com/Eryclis/legal_kg_reasoning/main/01_kg_pilot/output/neo4j_data_importer/rel_INTERPRETED_BY_ISOLATED_CASE.csv'
AS row
MATCH (a {nodeId: row.start_id})
MATCH (b {nodeId: row.end_id})
CREATE (a)-[:INTERPRETED_BY_ISOLATED_CASE {weight: toFloat(row.weight)}]->(b);

// ── 13. Rel: SUMMARIZED_BY_STJ_THESIS ────────────────────────
LOAD CSV WITH HEADERS FROM
  'https://raw.githubusercontent.com/Eryclis/legal_kg_reasoning/main/01_kg_pilot/output/neo4j_data_importer/rel_SUMMARIZED_BY_STJ_THESIS.csv'
AS row
MATCH (a {nodeId: row.start_id})
MATCH (b {nodeId: row.end_id})
CREATE (a)-[:SUMMARIZED_BY_STJ_THESIS {weight: toFloat(row.weight)}]->(b);

// ── 14. Rel: HAS_SUB_PROVISION ───────────────────────────────
LOAD CSV WITH HEADERS FROM
  'https://raw.githubusercontent.com/Eryclis/legal_kg_reasoning/main/01_kg_pilot/output/neo4j_data_importer/rel_HAS_SUB_PROVISION.csv'
AS row
MATCH (a {nodeId: row.start_id})
MATCH (b {nodeId: row.end_id})
CREATE (a)-[:HAS_SUB_PROVISION {weight: toFloat(row.weight)}]->(b);

// ── 15. Rel: HAS_INCISE ──────────────────────────────────────
LOAD CSV WITH HEADERS FROM
  'https://raw.githubusercontent.com/Eryclis/legal_kg_reasoning/main/01_kg_pilot/output/neo4j_data_importer/rel_HAS_INCISE.csv'
AS row
MATCH (a {nodeId: row.start_id})
MATCH (b {nodeId: row.end_id})
CREATE (a)-[:HAS_INCISE {weight: toFloat(row.weight)}]->(b);

// ── 16. Rel: CITES_ARTICLE ───────────────────────────────────
LOAD CSV WITH HEADERS FROM
  'https://raw.githubusercontent.com/Eryclis/legal_kg_reasoning/main/01_kg_pilot/output/neo4j_data_importer/rel_CITES_ARTICLE.csv'
AS row
MATCH (a {nodeId: row.start_id})
MATCH (b {nodeId: row.end_id})
CREATE (a)-[:CITES_ARTICLE {weight: toFloat(row.weight)}]->(b);

// ── 17. Rel: CITES_EXTERNAL ──────────────────────────────────
LOAD CSV WITH HEADERS FROM
  'https://raw.githubusercontent.com/Eryclis/legal_kg_reasoning/main/01_kg_pilot/output/neo4j_data_importer/rel_CITES_EXTERNAL.csv'
AS row
MATCH (a {nodeId: row.start_id})
MATCH (b {nodeId: row.end_id})
CREATE (a)-[:CITES_EXTERNAL {weight: toFloat(row.weight)}]->(b);

// ── 18. Verificação final ─────────────────────────────────────
MATCH (n) RETURN labels(n)[0] AS label, count(n) AS total ORDER BY total DESC;
