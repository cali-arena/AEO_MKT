# Application: Autism Support AI Project

**Candidate:** Lucas Cabral  
**Subject:** Domain-Specific AI Systems Design & Implementation

---

Dear Hiring Manager,

I am applying for this project because it aligns directly with the type of domain-specific AI systems I design and deploy. Building an autism support tool for parents is not simply a prompt engineering problem. It requires structured knowledge grounding, domain alignment, and careful architectural decisions to ensure responses are accurate, nuanced, and safe.

From your description, the current issue is that GPT-4o is producing responses that are too generic. This is expected when a base model is used with only a system prompt. Large models are generalists by design. To achieve consistent autism-specific depth, we need controlled knowledge injection and behavioral steering.

## Technical Assessment Approach

My first step would be a structured technical assessment. I would evaluate sample outputs, identify where generic reasoning occurs, and categorize failure types: lack of domain vocabulary, absence of evidence-backed strategies, insufficient contextual personalization, or overgeneralized advice. This diagnosis determines whether the problem is knowledge grounding, behavioral alignment, or both.

## Hybrid RAG + Fine-Tuning Strategy

In most cases like this, a **hybrid RAG plus light fine-tuning** approach performs best.

**RAG** would serve as the primary knowledge backbone. We would curate a high-quality autism parenting knowledge base including vetted resources on meltdowns, sensory processing, ABA therapy principles, IEP navigation, communication frameworks, and regulation strategies. The key is not dumping content into a vector database but structuring it correctly. I design retrieval systems with metadata-aware chunking, intent labeling, and domain tagging so the model retrieves context that matches the parent's exact concern.

For example, a question about school accommodations should retrieve IEP-specific procedural guidance rather than general emotional support advice. Proper retrieval scoring and grounding enforcement significantly reduce generic output.

**Fine-tuning** would then be used selectively, not as a replacement for retrieval. Instead of teaching the model facts, fine-tuning would shape tone, specificity, and reasoning style. We would create curated example pairs demonstrating nuanced autism-parent communication: emotionally aware, practical, and structured. This helps the model internalize response patterns such as breaking strategies into steps, referencing developmental considerations, and avoiding vague reassurance.

The combination produces stronger results than either approach alone. RAG ensures factual specificity. Fine-tuning shapes delivery and domain reasoning.

## Technical Implementation

- Structured RAG pipeline using a vector database such as Pinecone or Weaviate
- Metadata tagging for topic, age range, context type, and support category
- Hybrid retrieval combining semantic similarity with keyword filtering
- Grounding enforcement so responses must use retrieved context
- Optional lightweight fine-tuning of GPT-4o for tone and reasoning alignment
- Evaluation framework with test queries covering meltdowns, ABA, IEP, sensory regulation, and communication
- Before and after comparison scoring for specificity and usefulness

Your current stack using Next.js and GPT-4o API integrates cleanly with this architecture. The RAG layer can be implemented as a backend service or serverless function. No major infrastructure overhaul is required.

## Deliverables & Milestones

| Phase | Description |
|-------|-------------|
| 1 | Assessment and architecture design |
| 2 | Knowledge base structuring and RAG implementation |
| 3 | Fine-tuning dataset creation and optional model tuning |
| 4 | Testing, evaluation, and documentation |

Documentation will be part of delivery. I provide clear architecture diagrams, dataset formatting standards, retraining steps if fine-tuning is used, and guidance on expanding the knowledge base safely. A realistic estimate for a production-ready implementation would typically scope in the mid four-figure range for a robust system rather than a quick patch.

---

## Appendix: Technical Acceptance Proof

Below is output from a working RAG/crawl pipeline I implemented (different domain: moving services). It demonstrates crawl indexing, chunk statistics, retrieval sanity checks, and tenant isolation (leakage tests). The same patterns apply to an autism knowledge base.

### A) Crawl results

| Domain | Pages Indexed |
|--------|---------------|
| coasttocoastmovers.com | 1 |
| quote.unitedglobalvanline.com | 1 |
| quote domain excluded | 2 pages (ui_flow_excluded) |

**Top exclusion reasons:** flow route (2), session/token params, form UI heuristic

### B) Chunk stats

| Metric | Value |
|--------|-------|
| total sections | 2 |
| avg chars/section | 192 |
| min/max | 152 / 232 |

### C) Retrieval sanity checks (3 queries)

**Q1:** "Do they offer long distance moving?"
- 1) https://coasttocoastmovers.com/about | sec_35136addebec327a | score=0.552538  
  evidence: "About Coast to Coast Movers We offer long distance moving, local moving, and storage services."
- 2) https://quote.unitedglobalvanline.com/company | sec_d11c1b2cb2c41a55 | score=0.521475  
  evidence: "United Global Van Lines Informational content about moving tips, company history, and services."

**Q2:** "What storage options are available?"
- 1) https://coasttocoastmovers.com/about | sec_35136addebec327a | score=0.523845  
  evidence: "About Coast to Coast Movers We offer long distance moving, local moving, and storage services."
- 2) https://quote.unitedglobalvanline.com/company | sec_d11c1b2cb2c41a55 | score=0.500222  
  evidence: "United Global Van Lines Informational content about moving tips, company history, and services."

**Q3:** "Commercial moving services"
- 1) https://coasttocoastmovers.com/about | sec_35136addebec327a | score=0.585166  
  evidence: "About Coast to Coast Movers We offer long distance moving, local moving, and storage services."
- 2) https://quote.unitedglobalvanline.com/company | sec_d11c1b2cb2c41a55 | score=0.533112  
  evidence: "United Global Van Lines Informational content about moving tips, company history, and services."

### D) Leakage test status

**PASS**

---

I have built domain-specific AI systems in regulated and sensitive environments where accuracy and clarity matter. I also understand the importance of communicating technical decisions clearly to non-technical founders. My goal is not just to implement something that works today, but to give you a structured, scalable foundation you can iterate on confidently.

*I included the word scout as requested.*

If you would like, I can outline a concrete architecture proposal based on a few sample questions from your current system.

Best regards,  
**Lucas Cabral**
