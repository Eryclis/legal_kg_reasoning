

**KG \- TECHNICAL SPECIFICATION**

**\========================================**  
**1\. KG PURPOSE**  
**\========================================**

PRIMARY FUNCTION:  
Guide LLM reasoning via graph traversal \+ validate inferences via symbolic constraints

It is an Argumentation reasoning system:

- Navigation scaffold (graph shows reasoning paths)  
- Validation engine (symbolic constraints check validity)  
- Argumentation framework grounding (attack/support relations)

USE CASES:

Use Case 1: Navigation  
Query: "Given Art. 18 and 'TV defect 35 days', what's the next reasoning step?"  
Returns: "Check if TV is durable good → if yes, 90-day period applies"

Use Case 2: Validation  
LLM claims: "35 days exceeds 30-day period, no right to exchange"  
KG validates: FALSE \- Art. 18 §1º specifies 90 days for durable goods

Use Case 3: Conflict Detection  
Query: "Arguments that attack '90-day period for all products'?"  
Returns: "Art. 18 §1º distinguishes durable (90d) vs non-durable (30d)"

**\========================================**  
**2\. ANNOTATION SCHEME**  
**\========================================**

FOUR ANNOTATION LEVELS:

\---  
Level 1: GRAPH STRUCTURE (Navigation)  
\---

Properties:  
\- reasoning\_step\_type: typification | interpretation | specification | evidence  
\- claim: What's being argued (1 sentence)  
\- next\_steps: List of possible next nodes (IDs)  
\- conditions: When to take this path

Example:  
{  
  "node\_id": "Tema\_449",  
  "reasoning\_step\_type": "interpretation",  
  "claim": "30-day period for apparent defects in non-durable goods",  
  "next\_steps": \["Tese\_Ed42"\],  
  "conditions": {"defect\_type": "apparent", "product\_type": "non\_durable"}  
}

\---  
Level 2: VALIDATION RULES (Symbolic Constraints)  
\---

Properties:  
\- applicability\_conditions: When this argument applies (dict)  
\- required\_elements: What must be proven (list)  
\- exceptions: When this does NOT apply (list)  
\- legal\_basis: Grounding norm (string)

Example:  
{  
  "node\_id": "Art\_18\_Par1",  
  "applicability\_conditions": {"product\_defect": true, "product\_type": "durable"},  
  "required\_elements": \["defect\_identification", "delivery\_date", "claim\_within\_90\_days"\],  
  "exceptions": \["hidden\_defect", "supplier\_bad\_faith"\],  
  "legal\_basis": "Art. 18, §1º, CDC"  
}

\---  
Level 3: ARGUMENTATION RELATIONS  
\---

Relation types:  
\- refines: A adds specificity to B (Tese refines Tema)  
\- supports: A provides evidence for B (Cases support Tese)  
\- attacks: A contradicts B (Edge case attacks general rule)  
\- qualifies: A creates exception to B ("unless hidden defect")  
\- supersedes: A replaces B (Tese 2020 supersedes Tese 2015\)

Example:  
{  
  "relation\_type": "refines",  
  "source": "Tese\_Ed42",  
  "target": "Tema\_449",  
  "strength": 0.9,  
  "explanation": "These specifies period counts from delivery, not discovery"  
}

\---  
Level 4: AUTHORITY & STRENGTH  
\---

Properties:  
\- authority\_level: Hierarchical weight (float 0-1)  
\- court: STF | STJ | TRF | TJ  
\- support\_count: Number of similar cases (from Corpus927 metadata)  
\- date: When issued  
\- status: active | superseded | overruled

Authority hierarchy (proposed):  
STF \= 1.0  
STJ \- Tema \= 0.9  
STJ \- Tese \= 0.8  
STJ \- Grouped \= 0.6  
STJ \- Isolated \= 0.5  
TRF/TJ \= 0.4

DISCUSS: Is quantitative authority appropriate? Alternative: categorical (binding/persuasive)?

**\========================================**  
**3\. ENTITIES & RELATIONS**  
**\========================================**

1. **ENTITY TYPES**

| Entity | Description | Corpus927 Source | Example |
| :---- | ----- | ----- | ----- |
| `Norm` | Legal article | Level 1 | Art. 18, CDC |
| `ConstitutionalArgument` | STF review | Level 2 | ADI 5158 |
| `QualifiedPrecedent` | STJ Tema | Level 3 | Tema 449 |
| `Thesis` | STJ Tese | Level 4 | ed. 42 |
| `GroupedCase` | Similar precedents | Level 5 | REsp 1.556.132 \+ 34 similar |
| `IsolatedCase` | Individual precedent | Level 6 | REsp X |

2. **CORE PROPERTIES**

| Property | Type | Required | Description |
| :---- | ----- | ----- | ----- |
| `id` | string | Yes | Unique identifier |
| `type` | enum | Yes | Entity type |
| `text` | string | Yes | Textual content (ementa/tese/article text) |
| `source_url` | string | No | Link to full document |
| `article_anchor` | id | Yes | Which CDC article this relates to |

3. **RELATION TYPES**

| Relation | Domain | Range | Semantics |
| :---- | ----- | ----- | ----- |
| `refines` | Any | Any | A specifies B |
| `supports` | Any | Any | A provides evidence for B |
| `attacks` | Any | Any | A contradicts B |
| `qualifies` | Any | Any | A creates exception to B |
| `supersedes` | Thesis/Case | Thesis/Case | A replaces B |
| `interprets` | Precedent | Norm | A interprets B |
| `applies_to` | Norm/Precedent | Norm | A applies to situations in B |

**\========================================**  
**4\. EXAMPLE: Art. 18 (6 Levels)**  
**\========================================**

\[Include the annotated JSON example you created\]

Visualization:  
Art. 18 (Norm)  
  ↓ refines  
Art. 18 §1º (90d durable / 30d non-durable)  
  ↓ interprets  
Tema 449 (30d apparent defect non-durable)  
  ↓ refines  
Tese Ed.42 (period from delivery, not discovery)  
  ↓ supports  
Grouped Cases (34 similar)  
  ↓ qualifies  
Edge Case (exception: hidden defect)

**\========================================**  
**5\. VALIDATION QUERIES**  
**\========================================**

Critical queries KG must answer:

Q1: Navigation \- "What's the next reasoning step from Art. 18?"  
Q2: Validation \- "Is inference 'TV durable → 90 days' valid?"  
Q3: Conflict \- "Arguments that attack claim X?"  
Q4: Authority \- "Most authoritative precedent on Art. 18?"  
Q5: Temporal \- "Is Tese X still valid (not superseded)?"

**\========================================**  
**6\. OPEN QUESTIONS**  
**\========================================**

IMPLEMENTATION PLATFORM:  
\- Your recommendation?

AUTHORITY REPRESENTATION:  
Quantitative (0-1) vs Categorical (binding/persuasive)?  
\- Quantitative: enables weighted reasoning, but arbitrary  
\- Categorical: legally accurate, but loses nuance  
\- Hybrid option?

VALIDATION DETAIL:  
How detailed should applicability\_conditions be?  
\- High-level: {"product\_defect": true, "within\_period": true}  
\- Detailed: {"defect\_type": "apparent", "product\_type": "durable", "days\_since\_delivery": "\<90"}  
\- Trade-off: detail \= better validation, harder annotation

TEMPORAL DYNAMICS:  
How to represent jurisprudential evolution?  
\- Option 1: supersedes relation \+ status property  
\- Option 2: Versioning (Tese\_v1, Tese\_v2)  
\- Option 3: Temporal validity ranges

**\========================================**  
**7\. EXAMPLE \- art. 18, CDC**  
**\========================================**

```json
{
  "article_id": "Art_18_CDC",
  "graph": {
    "nodes": [
      {
        "id": "Art_18_CDC",
        "type": "Norm",
        "text": "Suppliers of durable or non-durable consumer products are jointly and severally liable for quality or quantity defects that make them improper or inadequate for their intended use or diminish their value...",
        "reasoning_step_type": "typification",
        "claim": "Suppliers are jointly liable for product quality defects",
        "next_steps": ["ADI_5158", "Tema_449", "Tema_200"],
        "authority_level": 1.0,
        "date": "1990-09-11"
      },
      {
        "id": "ADI_5158",
        "type": "ConstitutionalReview",
        "court": "STF",
        "text": "State law imposing obligation to provide replacement vehicle is unconstitutional due to exceeding concurrent jurisdiction",
        "reasoning_step_type": "interpretation",
        "claim": "Limits of state jurisdiction in consumer law",
        "interprets": "Art_18_CDC",
        "authority_level": 1.0,
        "date": "2019-02-19"
      },
      {
        "id": "Tema_449",
        "type": "QualifiedPrecedent",
        "court": "STJ",
        "question": "Application of statute of limitations (Art. 26 CDC) to banking account disclosure",
        "thesis": "Statute of limitations in Art. 26 CDC does not apply to disclosure actions for clarification of banking fees",
        "reasoning_step_type": "interpretation",
        "claim": "Art. 26 CDC does not apply to disclosure actions (not defect claims)",
        "interprets": "Art_18_CDC",
        "authority_level": 0.9,
        "date": "2011-10-10",
        "status": "final_judgment"
      },
      {
        "id": "Tema_200",
        "type": "QualifiedPrecedent",
        "court": "STJ",
        "question": "Validity of CONMETRO/INMETRO fines for non-conforming products",
        "thesis": "CONMETRO/INMETRO regulations are legal for regulating product quality in consumer market",
        "reasoning_step_type": "specification",
        "claim": "CONMETRO/INMETRO have authority to regulate product conformity",
        "refines": "Art_18_CDC",
        "authority_level": 0.9,
        "date": "2009-10-29",
        "status": "final_judgment"
      },
      {
        "id": "Tese_Ed42_Item12",
        "type": "Thesis",
        "court": "STJ",
        "edition": "42",
        "text": "The statute of limitations period for product defect claims (Art. 26 CDC) begins after the contractual warranty expires",
        "reasoning_step_type": "specification",
        "claim": "Limitation period starts after warranty expiration",
        "refines": "Tema_449",
        "authority_level": 0.8,
        "date": "2020-01-01"
      },
      {
        "id": "Tese_Ed42_Item5",
        "type": "Thesis",
        "court": "STJ",
        "edition": "42",
        "text": "Moral damages are warranted when consumer of new vehicle must return to dealership multiple times for defect repairs",
        "reasoning_step_type": "specification",
        "claim": "Multiple defects in new vehicle generate moral damages",
        "refines": "Art_18_CDC",
        "authority_level": 0.8
      },
      {
        "id": "Tese_Ed42_Item6",
        "type": "Thesis",
        "court": "STJ",
        "edition": "42",
        "text": "Detection of defect in new vehicle constitutes product defect and imposes joint liability on dealership and manufacturer",
        "reasoning_step_type": "specification",
        "claim": "Dealership and manufacturer are jointly liable for defects",
        "refines": "Art_18_CDC",
        "authority_level": 0.8
      },
      {
        "id": "GroupedCases_REsp1556132",
        "type": "GroupedCase",
        "court": "STJ",
        "representative_case": "REsp 1.556.132",
        "text": "Crime against consumer relations (Art. 7, IX, Law 8137/90). Improper product for consumption. Expert examination required for criminal materiality.",
        "reasoning_step_type": "evidence",
        "claim": "Improper product requires expert examination to prove criminal materiality",
        "supports": "Tese_Ed99_Item9",
        "authority_level": 0.6,
        "support_count": 34,
        "date": "2016-03-31"
      }
    ],
    "relations": [
      {
        "type": "interprets",
        "source": "ADI_5158",
        "target": "Art_18_CDC",
        "explanation": "Defines limits of state jurisdiction over consumer law"
      },
      {
        "type": "interprets",
        "source": "Tema_449",
        "target": "Art_18_CDC",
        "explanation": "Clarifies application of statute of limitations to defect claims"
      },
      {
        "type": "refines",
        "source": "Tema_200",
        "target": "Art_18_CDC",
        "explanation": "Specifies who regulates product conformity"
      },
      {
        "type": "refines",
        "source": "Tese_Ed42_Item12",
        "target": "Tema_449",
        "explanation": "Specifies when limitation period begins"
      },
      {
        "type": "refines",
        "source": "Tese_Ed42_Item5",
        "target": "Art_18_CDC",
        "explanation": "Specifies consequence of multiple defects (moral damages)"
      },
      {
        "type": "refines",
        "source": "Tese_Ed42_Item6",
        "target": "Art_18_CDC",
        "explanation": "Specifies joint liability of dealership and manufacturer"
      },
      {
        "type": "supports",
        "source": "GroupedCases_REsp1556132",
        "target": "Tese_Ed99_Item9",
        "strength": 0.9,
        "explanation": "34 uniform cases on expert examination requirement"
      }
    ]
  }
}

```

**\================================================**  
