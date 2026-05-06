// Legal KG — Art. 18 CDC
// Neo4j 5.x import script (corrected)
// Run in Neo4j Browser after: MATCH (n) DETACH DELETE n
//
// Fixes applied vs. original Data Importer export:
//   1. Removed `weight IS RELATIONSHIP KEY` constraints (prevented CITES_EXTERNAL duplicates)
//   2. HAS_INCISE: file_8 source is LegalSubProvision → LegalSubProvision (not LegalProvision)
//   3. STJThesis label (not StjThesis)
//   4. CONTROLLED_BY (not SUBJECT_TO_CONTROL)
//   5. Removed IS_PART_OF auto-generated reverse relationship
//   6. publication_date stored as string (datetime() fails on empty values)
//   7. CITES_ARTICLE for STJThesis uses correct label

:param {
  file_path_root: 'file:///',
  file_0: 'nodes_ExternalCitation.csv',
  file_1: 'nodes_ConstitutionalControl.csv',
  file_2: 'nodes_STJThesis.csv',
  file_3: 'nodes_RepetitiveTopic.csv',
  file_4: 'nodes_LegalSubProvision.csv',
  file_5: 'nodes_LegalProvision.csv',
  file_6: 'nodes_Case.csv',
  file_7: 'rel_INTERPRETED_BY_LEADING_CASE.csv',
  file_8: 'rel_HAS_INCISE.csv',
  file_9: 'rel_HAS_SUB_PROVISION.csv',
  file_10: 'rel_CONTROLLED_BY.csv',
  file_11: 'rel_CITES_EXTERNAL.csv',
  file_12: 'rel_INTERPRETED_BY_ISOLATED_CASE.csv',
  file_13: 'rel_INTERPRETED_BY_BINDING_THESIS.csv',
  file_14: 'rel_SUMMARIZED_BY_STJ_THESIS.csv',
  file_15: 'rel_CITES_ARTICLE.csv'
};

// ── NODE KEY CONSTRAINTS ────────────────────────────────────────────────────
// One per label — ensures nodeId is unique within each label.
// No relationship key constraints (weight is a property, not an identifier).

CREATE CONSTRAINT `nodeId_ExternalCitation_key` IF NOT EXISTS
FOR (n: `ExternalCitation`)
REQUIRE (n.`nodeId`) IS NODE KEY;

CREATE CONSTRAINT `nodeId_ConstitutionalControl_key` IF NOT EXISTS
FOR (n: `ConstitutionalControl`)
REQUIRE (n.`nodeId`) IS NODE KEY;

CREATE CONSTRAINT `nodeId_STJThesis_key` IF NOT EXISTS
FOR (n: `STJThesis`)
REQUIRE (n.`nodeId`) IS NODE KEY;

CREATE CONSTRAINT `nodeId_RepetitiveTopic_key` IF NOT EXISTS
FOR (n: `RepetitiveTopic`)
REQUIRE (n.`nodeId`) IS NODE KEY;

CREATE CONSTRAINT `nodeId_LegalSubProvision_key` IF NOT EXISTS
FOR (n: `LegalSubProvision`)
REQUIRE (n.`nodeId`) IS NODE KEY;

CREATE CONSTRAINT `nodeId_LegalProvision_key` IF NOT EXISTS
FOR (n: `LegalProvision`)
REQUIRE (n.`nodeId`) IS NODE KEY;

CREATE CONSTRAINT `nodeId_Case_key` IF NOT EXISTS
FOR (n: `Case`)
REQUIRE (n.`nodeId`) IS NODE KEY;

:param {
  idsToSkip: []
};

// ── NODE LOAD ───────────────────────────────────────────────────────────────

LOAD CSV WITH HEADERS FROM ($file_path_root + $file_0) AS row
WITH row
WHERE NOT row.`nodeId` IN $idsToSkip AND NOT row.`nodeId` IS NULL
CALL (row) {
  MERGE (n: `ExternalCitation` { `nodeId`: row.`nodeId` })
  SET n.`nodeId`            = row.`nodeId`
  SET n.`citationRaw`       = row.`citation_raw`
  SET n.`inferredType`      = row.`inferred_type`
  SET n.`court`             = row.`court`
  SET n.`authorityWeight`   = toFloat(trim(row.`authority_weight`))
  SET n.`caseNumber`        = row.`case_number`
  SET n.`originState`       = row.`origin_state`
  SET n.`adjudicatingBody`  = row.`adjudicating_body`
  SET n.`rapporteur`        = row.`rapporteur`
  SET n.`decisionDate`      = row.`decision_date`
  SET n.`citedEmenta`       = row.`cited_ementa`
} IN TRANSACTIONS OF 10000 ROWS;

LOAD CSV WITH HEADERS FROM ($file_path_root + $file_1) AS row
WITH row
WHERE NOT row.`nodeId` IN $idsToSkip AND NOT row.`nodeId` IS NULL
CALL (row) {
  MERGE (n: `ConstitutionalControl` { `nodeId`: row.`nodeId` })
  SET n.`nodeId`          = row.`nodeId`
  SET n.`title`           = row.`title`
  SET n.`processNumber`   = row.`process_number`
  SET n.`summary`         = row.`summary`
  SET n.`publicationDate` = row.`publication_date`
  SET n.`sourceUrl`       = row.`source_url`
  SET n.`temporalStatus`  = row.`temporal_status`
  SET n.`authorityWeight` = toFloat(trim(row.`authority_weight`))
} IN TRANSACTIONS OF 10000 ROWS;

LOAD CSV WITH HEADERS FROM ($file_path_root + $file_2) AS row
WITH row
WHERE NOT row.`nodeId` IN $idsToSkip AND NOT row.`nodeId` IS NULL
CALL (row) {
  MERGE (n: `STJThesis` { `nodeId`: row.`nodeId` })
  SET n.`nodeId`          = row.`nodeId`
  SET n.`edition`         = row.`edition`
  SET n.`thesisText`      = row.`thesis_text`
  SET n.`sourceUrl`       = row.`source_url`
  SET n.`temporalStatus`  = row.`temporal_status`
  SET n.`authorityWeight` = toFloat(trim(row.`authority_weight`))
} IN TRANSACTIONS OF 10000 ROWS;

LOAD CSV WITH HEADERS FROM ($file_path_root + $file_3) AS row
WITH row
WHERE NOT row.`nodeId` IN $idsToSkip AND NOT row.`nodeId` IS NULL
CALL (row) {
  MERGE (n: `RepetitiveTopic` { `nodeId`: row.`nodeId` })
  SET n.`nodeId`           = row.`nodeId`
  SET n.`title`            = row.`title`
  SET n.`thesis`           = row.`thesis`
  SET n.`ementa`           = row.`ementa`
  SET n.`question`         = row.`question`
  SET n.`status`           = row.`status`
  SET n.`statusConfirmed`  = toLower(trim(row.`status_confirmed`)) IN ['1','true','yes']
  SET n.`publicationDate`  = row.`publication_date`
  SET n.`sourceUrl`        = row.`source_url`
  SET n.`temporalStatus`   = row.`temporal_status`
  SET n.`hasRg`            = toLower(trim(row.`has_rg`)) IN ['1','true','yes']
  SET n.`authorityWeight`  = toFloat(trim(row.`authority_weight`))
} IN TRANSACTIONS OF 10000 ROWS;

LOAD CSV WITH HEADERS FROM ($file_path_root + $file_4) AS row
WITH row
WHERE NOT row.`nodeId` IN $idsToSkip AND NOT row.`nodeId` IS NULL
CALL (row) {
  MERGE (n: `LegalSubProvision` { `nodeId`: row.`nodeId` })
  SET n.`nodeId`   = row.`nodeId`
  SET n.`law`      = row.`law`
  SET n.`article`  = toInteger(trim(row.`article`))
  SET n.`subRef`   = row.`sub_ref`
  SET n.`subType`  = row.`sub_type`
  SET n.`text`     = row.`text`
  SET n.`parentId` = row.`parent_id`
} IN TRANSACTIONS OF 10000 ROWS;

LOAD CSV WITH HEADERS FROM ($file_path_root + $file_5) AS row
WITH row
WHERE NOT row.`nodeId` IN $idsToSkip AND NOT row.`nodeId` IS NULL
CALL (row) {
  MERGE (n: `LegalProvision` { `nodeId`: row.`nodeId` })
  SET n.`nodeId`   = row.`nodeId`
  SET n.`law`      = row.`law`
  SET n.`article`  = toInteger(trim(row.`article`))
  SET n.`text`     = row.`text`
  SET n.`isStub`   = toLower(trim(row.`is_stub`)) IN ['1','true','yes']
} IN TRANSACTIONS OF 10000 ROWS;

LOAD CSV WITH HEADERS FROM ($file_path_root + $file_6) AS row
WITH row
WHERE NOT row.`nodeId` IN $idsToSkip AND NOT row.`nodeId` IS NULL
CALL (row) {
  MERGE (n: `Case` { `nodeId`: row.`nodeId` })
  SET n.`nodeId`          = row.`nodeId`
  SET n.`title`           = row.`title`
  SET n.`caseClass`       = row.`case_class`
  SET n.`fullTextHash`    = row.`full_text_hash`
  SET n.`publicationDate` = row.`publication_date`
  SET n.`rapporteur`      = row.`rapporteur`
  SET n.`adjudicatingBody`= row.`adjudicating_body`
  SET n.`summary`         = row.`summary`
  SET n.`fullTextUrl`     = row.`full_text_url`
  SET n.`authorityWeight` = toFloat(trim(row.`authority_weight`))
  SET n.`similarCount`    = toInteger(trim(row.`similar_count`))
  SET n.`temporalStatus`  = row.`temporal_status`
  SET n.`hasRg`           = toLower(trim(row.`has_rg`)) IN ['1','true','yes']
  SET n.`originState`     = row.`origin_state`
  SET n.`court`           = row.`court`
  SET n.`corpusId`        = toInteger(trim(row.`corpus_id`))
} IN TRANSACTIONS OF 10000 ROWS;


// ── RELATIONSHIP LOAD ───────────────────────────────────────────────────────

// LegalProvision --[INTERPRETED_BY_LEADING_CASE]--> Case
LOAD CSV WITH HEADERS FROM ($file_path_root + $file_7) AS row
WITH row
CALL (row) {
  MATCH (source: `LegalProvision` { `nodeId`: row.`start_id` })
  MATCH (target: `Case`           { `nodeId`: row.`end_id` })
  MERGE (source)-[r: `INTERPRETED_BY_LEADING_CASE`]->(target)
  SET r.`weight` = toFloat(trim(row.`weight`))
} IN TRANSACTIONS OF 10000 ROWS;

// LegalSubProvision(paragraph) --[HAS_INCISE]--> LegalSubProvision(incise)
LOAD CSV WITH HEADERS FROM ($file_path_root + $file_8) AS row
WITH row
CALL (row) {
  MATCH (source: `LegalSubProvision` { `nodeId`: row.`start_id` })
  MATCH (target: `LegalSubProvision` { `nodeId`: row.`end_id` })
  MERGE (source)-[r: `HAS_INCISE`]->(target)
  SET r.`weight` = toFloat(trim(row.`weight`))
} IN TRANSACTIONS OF 10000 ROWS;

// LegalProvision --[HAS_SUB_PROVISION]--> LegalSubProvision(paragraph)
LOAD CSV WITH HEADERS FROM ($file_path_root + $file_9) AS row
WITH row
CALL (row) {
  MATCH (source: `LegalProvision`    { `nodeId`: row.`start_id` })
  MATCH (target: `LegalSubProvision` { `nodeId`: row.`end_id` })
  MERGE (source)-[r: `HAS_SUB_PROVISION`]->(target)
  SET r.`weight` = toFloat(trim(row.`weight`))
} IN TRANSACTIONS OF 10000 ROWS;

// LegalProvision --[CONTROLLED_BY]--> ConstitutionalControl
LOAD CSV WITH HEADERS FROM ($file_path_root + $file_10) AS row
WITH row
CALL (row) {
  MATCH (source: `LegalProvision`      { `nodeId`: row.`start_id` })
  MATCH (target: `ConstitutionalControl` { `nodeId`: row.`end_id` })
  MERGE (source)-[r: `CONTROLLED_BY`]->(target)
  SET r.`weight` = toFloat(trim(row.`weight`))
} IN TRANSACTIONS OF 10000 ROWS;

// Case --[CITES_EXTERNAL]--> ExternalCitation
LOAD CSV WITH HEADERS FROM ($file_path_root + $file_11) AS row
WITH row
CALL (row) {
  MATCH (source: `Case`             { `nodeId`: row.`start_id` })
  MATCH (target: `ExternalCitation` { `nodeId`: row.`end_id` })
  MERGE (source)-[r: `CITES_EXTERNAL`]->(target)
  SET r.`weight` = toFloat(trim(row.`weight`))
} IN TRANSACTIONS OF 10000 ROWS;

// LegalProvision --[INTERPRETED_BY_ISOLATED_CASE]--> Case
LOAD CSV WITH HEADERS FROM ($file_path_root + $file_12) AS row
WITH row
CALL (row) {
  MATCH (source: `LegalProvision` { `nodeId`: row.`start_id` })
  MATCH (target: `Case`           { `nodeId`: row.`end_id` })
  MERGE (source)-[r: `INTERPRETED_BY_ISOLATED_CASE`]->(target)
  SET r.`weight` = toFloat(trim(row.`weight`))
} IN TRANSACTIONS OF 10000 ROWS;

// LegalProvision --[INTERPRETED_BY_BINDING_THESIS]--> RepetitiveTopic
LOAD CSV WITH HEADERS FROM ($file_path_root + $file_13) AS row
WITH row
CALL (row) {
  MATCH (source: `LegalProvision`  { `nodeId`: row.`start_id` })
  MATCH (target: `RepetitiveTopic` { `nodeId`: row.`end_id` })
  MERGE (source)-[r: `INTERPRETED_BY_BINDING_THESIS`]->(target)
  SET r.`weight` = toFloat(trim(row.`weight`))
} IN TRANSACTIONS OF 10000 ROWS;

// LegalProvision --[SUMMARIZED_BY_STJ_THESIS]--> STJThesis
LOAD CSV WITH HEADERS FROM ($file_path_root + $file_14) AS row
WITH row
CALL (row) {
  MATCH (source: `LegalProvision` { `nodeId`: row.`start_id` })
  MATCH (target: `STJThesis`      { `nodeId`: row.`end_id` })
  MERGE (source)-[r: `SUMMARIZED_BY_STJ_THESIS`]->(target)
  SET r.`weight` = toFloat(trim(row.`weight`))
} IN TRANSACTIONS OF 10000 ROWS;

// RepetitiveTopic --[CITES_ARTICLE]--> LegalProvision
LOAD CSV WITH HEADERS FROM ($file_path_root + $file_15) AS row
WITH row
CALL (row) {
  MATCH (source: `RepetitiveTopic` { `nodeId`: row.`start_id` })
  MATCH (target: `LegalProvision`  { `nodeId`: row.`end_id` })
  MERGE (source)-[r: `CITES_ARTICLE`]->(target)
  SET r.`weight` = toFloat(trim(row.`weight`))
} IN TRANSACTIONS OF 10000 ROWS;

// STJThesis --[CITES_ARTICLE]--> LegalProvision
LOAD CSV WITH HEADERS FROM ($file_path_root + $file_15) AS row
WITH row
CALL (row) {
  MATCH (source: `STJThesis`      { `nodeId`: row.`start_id` })
  MATCH (target: `LegalProvision` { `nodeId`: row.`end_id` })
  MERGE (source)-[r: `CITES_ARTICLE`]->(target)
  SET r.`weight` = toFloat(trim(row.`weight`))
} IN TRANSACTIONS OF 10000 ROWS;
