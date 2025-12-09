# ANALISI DI FATTIBILITA: Estensione YouTube-Autopilot per Media PR Outreach

**Data:** 2025-12-07
**Tipo:** Mapping / Feasibility Analysis
**Status:** Completo

---

## EXECUTIVE SUMMARY

Dopo un'analisi approfondita della codebase `youtube-autopilot`, ho identificato **forte riutilizzabilita** (~70% dell'infrastruttura core) per il caso d'uso di **Media PR Outreach**.

**Raccomandazione:** Estendere la codebase esistente con un nuovo modulo `pr_outreach/` piuttosto che creare un progetto separato.

---

## 1. CONFRONTO WORKFLOW: YOUTUBE vs PR OUTREACH

| Fase | YouTube Script Pipeline | PR Outreach Pipeline |
|------|------------------------|---------------------|
| **INPUT** | Topic di tendenza | Topic prodotto (es. "Best fitness AI app") |
| **DISCOVERY** | Multi-source trends (YouTube, Reddit, HN) | Multi-source articles (Google, Ahrefs, news sites) |
| **ANALYSIS** | Trend scoring + virality | Article relevance + domain authority + fit |
| **SELECTION** | AI-assisted trend selection | AI-assisted article selection |
| **STRATEGY** | Editorial strategy (format, angle) | Outreach strategy (positioning, angle) |
| **CONTENT** | Script writing (hook, bullets, CTA) | Email writing (subject, pitch, value prop) |
| **ENRICHMENT** | Visual planning | Author research + contact validation |
| **QUALITY** | Quality review + Monetization QA | Quality review + Spam check + Personalization score |
| **HUMAN GATE** | Script approval → Video approval | Email approval → Send authorization |
| **OUTPUT** | ContentPackage → Video | OutreachPackage → Sent email |
| **TRACKING** | JSONL datastore | JSONL datastore + Response tracking |

**Conclusione:** Il flusso e **strutturalmente analogo** (80% di sovrapposizione concettuale).

---

## 2. COMPONENTI DIRETTAMENTE RIUTILIZZABILI (70%)

### CORE INFRASTRUCTURE (100% riutilizzabile)

| Componente | File | Riuso PR Outreach |
|------------|------|-------------------|
| **Pydantic Schemas** | `core/schemas.py` | Estendere con `ArticleCandidate`, `OutreachEmail`, `AuthorProfile` |
| **AgentCoordinator** | `core/agent_coordinator.py` | Riutilizzare per orchestrazione agenti PR |
| **AgentContext** | `core/agent_coordinator.py` | Estendere con context PR-specific |
| **LLM Router** | `services/llm_router.py` | 100% riutilizzabile (multi-provider) |
| **Language Validator** | `core/language_validator.py` | 100% riutilizzabile (multi-lingua) |
| **Config System** | `core/config.py` | Estendere con PR-specific config |
| **Logger** | `core/logger.py` | 100% riutilizzabile |
| **Datastore** | `io/datastore.py` | Riutilizzare pattern, nuove tabelle |

### WORKSPACE & MULTI-TENANCY (90% riutilizzabile)

**Mapping strutturale:**

| YouTube Workspace | PR Outreach Campaign |
|-------------------|---------------------|
| `workspace_id` | `campaign_id` |
| `vertical_id` | `niche_id` |
| `brand_tone` | `email_tone` |
| `banned_topics` | `avoid_mentions` |
| `narrator_persona` | `sender_persona` |
| `recent_titles` | `contacted_articles` (dedup) |
| `validation_gates` | `validation_gates` (identico) |

### AGENT PATTERNS (80% riutilizzabili)

| YouTube Agent | → PR Outreach Agent | Pattern Riutilizzabile |
|---------------|---------------------|----------------------|
| `TrendHunter` | → `ArticleHunter` | Multi-source discovery + scoring |
| `EditorialStrategist` | → `OutreachStrategist` | AI strategy decision (LLM-driven) |
| `ScriptWriter` | → `EmailWriter` | Content generation (hook, body, CTA) |
| `QualityReviewer` | → `OutreachQualityReviewer` | Multi-check compliance gate |
| `SEOManager` | → `SubjectLineOptimizer` | Text optimization (CTR-focused) |

### VALIDATION & QUALITY FRAMEWORK (100% riutilizzabile)

- **4-Gate Validation System** → Applicabile a PR (Post-Discovery, Post-Analysis, Post-Email, Pre-Send)
- **FASE 1 Quality Validators** → Pattern per email quality check
- **Retry + Fallback Logic** → Identico per email regeneration
- **Human Approval Workflow** → `PENDING_REVIEW → APPROVED → SENT`

### HUMAN-LIKE BEHAVIOR PATTERNS (90% riutilizzabili)

| YouTube | PR Outreach |
|---------|-------------|
| Narrator persona (Coach Marco) | Sender persona (es. "PR Manager Sarah") |
| Brand tone enforcement | Email tone enforcement |
| Language compliance | Language compliance (internazionale) |
| Signature phrases | Email signature + P.S. patterns |
| Credibility markers | Credibility in signature/intro |

---

## 3. GAP FUNZIONALI: COSA MANCA (30%)

### NUOVI SERVIZI DA CREARE

| Servizio | Funzione | Complessita |
|----------|----------|-------------|
| **ArticleScraper** | Estrazione contenuto da URL (newspaper3k, trafilatura) | Media |
| **AuthorFinder** | Ricerca autore (LinkedIn, Twitter, email hunter) | Alta |
| **ContactValidator** | Validazione email/social (email verification API) | Media |
| **DomainAnalyzer** | Domain Authority, traffico (Ahrefs API, SimilarWeb) | Media |
| **EmailSender** | SMTP/API integration (SendGrid, Mailgun) | Media |
| **ResponseTracker** | Tracking aperture/reply (webhook + parsing) | Alta |

### NUOVI AGENTI DA CREARE

| Agente | Responsabilita | Input → Output |
|--------|----------------|----------------|
| **ArticleHunter** | Cercare articoli rilevanti per topic | Topic → `List[ArticleCandidate]` |
| **ArticleAnalyzer** | Analizzare contenuto e trovare insertion point | Article → `InsertionOpportunity` |
| **ProductPositioner** | Suggerire come posizionare prodotto | Article + Product → `PositioningStrategy` |
| **AuthorProfiler** | Ricercare e validare autore | Article → `AuthorProfile` |
| **EmailWriter** | Scrivere email personalizzata | Context → `OutreachEmail` |
| **SpamChecker** | Verificare email non sembri spam | Email → Score (0-1) |
| **PersonalizationScorer** | Valutare livello personalizzazione | Email → Score (0-1) |

### NUOVI SCHEMAS DA CREARE

```python
class ArticleCandidate(BaseModel):
    url: str
    title: str
    domain: str
    domain_authority: float  # 0-100
    publication_date: datetime
    author_name: Optional[str]
    content_excerpt: str
    relevance_score: float  # 0-1
    insertion_opportunities: List[str]

class AuthorProfile(BaseModel):
    name: str
    email: Optional[str]
    linkedin_url: Optional[str]
    twitter_handle: Optional[str]
    bio: Optional[str]
    recent_articles: List[str]
    confidence_score: float  # 0-1

class OutreachEmail(BaseModel):
    subject: str
    opening_hook: str
    value_proposition: str
    insertion_suggestion: str
    call_to_action: str
    full_body: str
    ps_line: Optional[str]

class OutreachPackage(BaseModel):
    status: str  # DRAFT|PENDING_REVIEW|APPROVED|SENT|REPLIED|REJECTED
    article: ArticleCandidate
    author: AuthorProfile
    email: OutreachEmail
    product_info: ProductInfo
    positioning_strategy: str
    personalization_score: float
    spam_score: float
    sent_at: Optional[datetime]
    response_received: Optional[bool]
```

---

## 4. ARCHITETTURA PROPOSTA

### OPZIONE A: ESTENDERE LA CODEBASE (RACCOMANDATO)

```
youtube-autopilot/
├── yt_autopilot/           # Esistente (YouTube)
│   ├── core/               # Shared (schemas, coordinator, llm_router)
│   ├── agents/             # YouTube-specific agents
│   ├── services/           # YouTube-specific services
│   ├── pipeline/           # YouTube pipeline
│   └── io/                 # Shared datastore pattern
│
├── pr_outreach/            # NUOVO MODULO
│   ├── core/
│   │   └── schemas.py      # PR-specific schemas (extends base)
│   ├── agents/
│   │   ├── article_hunter.py
│   │   ├── article_analyzer.py
│   │   ├── product_positioner.py
│   │   ├── author_profiler.py
│   │   ├── email_writer.py
│   │   ├── spam_checker.py
│   │   └── personalization_scorer.py
│   ├── services/
│   │   ├── article_scraper.py
│   │   ├── author_finder.py
│   │   ├── contact_validator.py
│   │   ├── domain_analyzer.py
│   │   ├── email_sender.py
│   │   └── response_tracker.py
│   ├── pipeline/
│   │   └── build_outreach_package.py
│   └── io/
│       └── outreach_datastore.py
│
├── shared/                 # REFACTOR: Move shared components
│   ├── core/
│   │   ├── schemas_base.py
│   │   ├── agent_coordinator.py
│   │   ├── language_validator.py
│   │   └── config.py
│   ├── services/
│   │   └── llm_router.py
│   └── io/
│       └── datastore_base.py
│
├── workspaces/             # YouTube workspaces
├── campaigns/              # PR outreach campaigns
├── run.py                  # CLI: youtube commands
└── outreach.py             # CLI: pr outreach commands
```

#### Vantaggi OPZIONE A:
- **70% codice riutilizzato** (no duplicazione)
- **Skill transfer** (stesso team puo lavorare su entrambi)
- **Shared improvements** (bug fix beneficiano entrambi)
- **Unified testing** (stesse CI/CD pipeline)
- **Consistent patterns** (stessi design patterns)

#### Svantaggi OPZIONE A:
- Richiede refactoring iniziale
- Codebase piu grande da mantenere

---

### OPZIONE B: NUOVA CODEBASE DEDICATA

#### Vantaggi OPZIONE B:
- Nessun rischio di break su youtube-autopilot
- Team separati possono lavorare indipendentemente
- Versioning indipendente

#### Svantaggi OPZIONE B:
- **Duplicazione ~8,000 linee di codice**
- **Maintenance double** (bug fix da replicare)
- **No skill transfer** (divergenza patterns nel tempo)

---

## 5. PIPELINE PR OUTREACH (PROPOSTA)

```
1. CAMPAIGN SETUP
   - Carica campaign config (product, target niche, tone)
   - Load sender persona
   - Check contacted_articles (evita duplicati)

2. ARTICLE DISCOVERY (new: ArticleHunter)
   - Query Google Search API: "best {topic} 2024"
   - Query Ahrefs API: backlinks to competitors
   - Query news aggregators: TechCrunch, VentureBeat, niche blogs
   - Output: List[ArticleCandidate] (top 50)

3. ARTICLE SCORING (new: ArticleAnalyzer)
   - Domain Authority score (Ahrefs/Moz)
   - Recency score (publication date)
   - Relevance score (LLM semantic match)
   - Insertion opportunity score (where can product fit?)
   - Output: Ranked List[ArticleCandidate] (top 10)

4. AI-ASSISTED SELECTION (reuse: AgentCoordinator pattern)
   - LLM reviews top 10
   - Semantic duplicate check vs contacted_articles
   - Output: Selected article + insertion strategy

5. PRODUCT POSITIONING (new: ProductPositioner)
   - Analyze article structure
   - Identify "listicle insertion points" or "mention opportunities"
   - Generate positioning rationale
   - Output: PositioningStrategy

6. AUTHOR RESEARCH (new: AuthorProfiler + AuthorFinder service)
   - Extract author name from article
   - Search LinkedIn, Twitter, email
   - Validate contact (email verification)
   - Analyze recent articles (style, tone)
   - Output: AuthorProfile

7. OUTREACH STRATEGY (adapt: EditorialStrategist → OutreachStrategist)
   - Decide email angle (direct pitch vs value-first)
   - Decide personalization level
   - Decide CTA type (update request, new feature mention, etc.)
   - Output: OutreachDecision

8. EMAIL GENERATION (adapt: ScriptWriter → EmailWriter)
   - Generate subject line (A/B options)
   - Generate opening hook (personalized)
   - Generate value proposition (why include product)
   - Generate insertion suggestion (specific, helpful)
   - Generate CTA (soft ask)
   - Optional P.S. line
   - Output: OutreachEmail

GATE 1: POST-EMAIL VALIDATION
   - Spam score check (new: SpamChecker)
   - Personalization score check (new: PersonalizationScorer)
   - Language consistency (reuse: LanguageValidator)
   - Tone compliance (adapt: QualityReviewer)

9. HUMAN APPROVAL (reuse: approval workflow)
   - Status: PENDING_REVIEW
   - CLI: `python outreach.py review emails`
   - CLI: `python outreach.py approve-email <id> --approved-by "email"`
   - Status: APPROVED

10. SEND EMAIL (new: EmailSender service)
    - Status: SENT
    - Track: sent_at, message_id

11. RESPONSE TRACKING (new: ResponseTracker service)
    - Webhook for replies
    - Status: REPLIED / NO_RESPONSE
    - Update campaign stats

12. LEARNING LOOP (reuse: performance summary pattern)
    - Track: open rates, reply rates, conversion rates
    - Feed back to ArticleHunter scoring
```

---

## 6. CHECKLIST REQUISITI vs COPERTURA

| Requisito | Coperto da Codebase Esistente | Da Creare |
|-----------|------------------------------|-----------|
| Dato un topic, cercare top source | Pattern TrendSource riutilizzabile | ArticleHunter + Google/Ahrefs API |
| Analizzare articoli | Pattern analisi riutilizzabile | ArticleAnalyzer + Scraper |
| Estrarre contenuto | No | ArticleScraper (newspaper3k) |
| Posizionare prodotto | No | ProductPositioner (LLM) |
| Trovare contatti autore | No | AuthorFinder + Hunter.io API |
| Validare contatti | No | ContactValidator |
| Scrivere email | Pattern ScriptWriter riutilizzabile | EmailWriter |
| Approvazione umana | 100% riutilizzabile | - |
| Inviare email | No | EmailSender (SendGrid) |
| Persistenza per evitare ripetizioni | 100% riutilizzabile | - |
| Filtri e qualita | 90% riutilizzabile | SpamChecker, PersonalizationScorer |
| Agenti sembrano umani | 90% riutilizzabile (persona) | Adattare per email |

---

## 7. DIPENDENZE ESTERNE NUOVE

- **Google Custom Search API** (o SerpAPI)
- **Ahrefs/Moz API** (domain authority)
- **Hunter.io API** (email finding)
- **Email Verification API** (ZeroBounce, NeverBounce)
- **SendGrid/Mailgun** (email sending)
- **newspaper3k / trafilatura** (article scraping)

---

## 8. CONCLUSIONE

**Raccomandazione finale: OPZIONE A - ESTENDERE LA CODEBASE**

**Motivazioni:**

1. **Riuso elevato (70%)**: L'architettura multi-agente, AgentCoordinator, LLM Router, validation gates, human approval workflow, datastore pattern sono tutti riutilizzabili con minime modifiche.

2. **Pattern collaudati**: I pattern per "human-like behavior" (persona, tone, language compliance) sono gia implementati e testati.

3. **Manutenibilita**: Un solo codebase significa bug fix e miglioramenti condivisi.

4. **Scalabilita**: La struttura workspace/campaign e gia multi-tenant.

5. **Skill transfer**: Lo stesso team puo lavorare su entrambi i moduli.

---

## 9. PROSSIMI PASSI (se si procede)

1. Definire schemas PR (ArticleCandidate, AuthorProfile, OutreachEmail, OutreachPackage)
2. Refactoring shared/ (estrarre componenti comuni)
3. Implementare ArticleHunter (primo agente PR)
4. Implementare ArticleScraper (primo servizio PR)
5. Testare pipeline discovery (solo ricerca, no email)
6. Implementare EmailWriter (adattare ScriptWriter)
7. Implementare human approval (riutilizzare pattern)
8. Implementare send + tracking (ultimo step)
