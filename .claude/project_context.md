# yt_autopilot - Contesto Globale del Progetto

## Obiettivo Finale

Sistema automatizzato end-to-end per produzione e pubblicazione video YouTube:

1. **Trovare trend** di contenuti
2. **Generare script e piano visivo** con agenti AI specializzati
3. **Generare clip video** usando Veo API
4. **Montare il video finale** (ffmpeg) con voiceover TTS
5. **Caricare su YouTube** programmando data/ora pubblicazione (YouTube Data API)
6. **Raccogliere KPI** (views, watchtime, CTR) da YouTube Analytics API
7. **Salvare tutto** in datastore locale
8. **Automatizzare** su scheduler (NO n8n, Zapier, Make)

---

## Architettura a LAYER (OBBLIGATORIA)

### `core/`
**Contratti dati condivisi, logger, config/env, memoria del canale**
- Brand tone, regole compliance, titoli già usati
- **NON importa niente dagli altri layer**
- Singola fonte di verità per schemas/models

### `agents/`
**Multi-agente "cervello editoriale"**
- TrendHunter, ScriptWriter, VisualPlanner, SeoManager, QualityReviewer
- Ragionano e generano oggetti strutturati
- **NO chiamate a ffmpeg, Veo, YouTube, filesystem**
- Possono SOLO leggere memoria dal core
- **Niente side effects**

### `services/`
**"Le mani" - operazioni concrete**
- `trend_source` → recupero trend esterni
- `video_gen_service` → Veo API → clip .mp4
- `tts_service` → voiceover .wav
- `video_assemble_service` → ffmpeg, intro/outro/logo
- `thumbnail_service` → genera immagine thumbnail
- `youtube_uploader` → upload/schedule su YouTube Data API
- `youtube_analytics` → metriche KPI
- `datastore & exports` → stato locale
- Possono leggere `core.schemas`, `core.config`, `core.logger`
- **NON devono importare gli agenti**

### `pipeline/`
**Orchestratori**
- `build_video_package.py` → usa SOLO gli agenti (produce piano strategico)
- `produce_render_publish.py` → end-to-end (produce video reale, upload, salva)
- `tasks.py` → job atomici
- `scheduler.py` → pianificazione lavoro giornaliero/ricorrente
- **Unico layer autorizzato a importare sia agents che services**

### `io/`
**Persistenza interna**
- Salvataggio JSON/SQLite/CSV
- Esportazioni
- Gestione storica

---

## Regole Chiave

### Importazioni e Dipendenze
1. ✅ Tutti i modelli dati SOLO da `yt_autopilot.core.schemas`
2. ❌ NON ridefinire mai classi dati localmente
3. ❌ `core/` non importa nulla fuori da `core/`
4. ❌ `agents/` non importa nulla da `services/`
5. ❌ `services/` non importa nulla da `agents/`
6. ✅ `pipeline/` è l'unico autorizzato a conoscere entrambi

### Coding Style
- **Python 3.11+**
- Type hints ovunque
- Pydantic per modelli e validazione
- Se inventi tipi aggiuntivi (es. `UploadResult`, `VideoMetrics`), aggiungili a `core/schemas.py` PRIMA di usarli altrove
- Funzioni pubbliche piccole, pure, con firma chiara
- Gestione errori con logging chiaro da `core/logger.py`

### File di Configurazione
- `.env.example` per template credenziali
- `.gitignore` per evitare commit di credenziali reali
- README sempre aggiornato quando si aggiungono componenti nuovi

---

## Compliance & Brand Safety

**SEMPRE, OGNI VOLTA CHE SI SCRIVE CONTENUTO:**

### ❌ VIETATO
- Promettere cure mediche garantite
- Hate speech, insulti verso gruppi o individui
- Politica aggressiva/partitica
- Claim legali borderline
- Copyright esplicito (es. "usa la musica di [artista famoso]")

### ✅ OBBLIGATORIO
- Tono del canale: **diretto, utile, zero volgarità**
- Stile visivo: **ritmo alto, overlay di testo grande, formato verticale 9:16 per Shorts**

---

## Workflow di Sviluppo

Il lavoro avanza in **step incrementali**. Ogni step sa:
- Cosa è già fatto
- Cosa deve fare dopo
- Quali layer tocca
- Quali acceptance criteria deve soddisfare

**Step corrente e progressi:** vedi `.claude/progress.md`

### Come Iniziare una Sessione
1. Leggi `.claude/progress.md` per vedere:
   - Quali step sono completati
   - Qual è lo step corrente e i suoi obiettivi
   - Gli acceptance criteria da soddisfare
   - Note della sessione precedente
2. Segui le regole architetturali definite sopra
3. Aggiorna `progress.md` durante e alla fine della sessione

---

## Note per Claude Code

- **LEGGI SEMPRE** `.claude/rules.md` - regole NON NEGOZIABILI
- Usa TodoWrite per tracciare task multipli
- Mantieni separazione layer rigorosa (vedi `.claude/rules.md`)
- Type hints e Pydantic validation ovunque
- Logging centralizzato via `core.logger`
- Prima di aggiungere nuovi schemas, verifica non esistano già in `core/schemas.py`
- Per storia del progetto: `docs/history.md`
- Per architettura dettagliata: README.md (sezioni Architecture e Layer Rules)

---

## 📝 Protocollo Aggiornamento Documentazione

**IMPORTANTE:** Aggiorna SEMPRE la documentazione quando completi modifiche significative.

### Quando Aggiornare Cosa

| Modifica Effettuata | File da Aggiornare | Cosa Aggiornare |
|---------------------|-------------------|-----------------|
| **Nuova regola architetturale** | `.claude/rules.md` | Aggiungi alla sezione appropriata (VIETATO/OBBLIGATORIO) |
| **Completamento Step** | `docs/history.md` | Aggiungi nuova sezione Step con status ✅ Completato |
| **Nuovi comandi CLI** | `README.md` | Aggiorna sezione "Usage" e "Quick Start" |
| **Cambio architettura layer** | `README.md` + `.claude/rules.md` | Aggiorna entrambi per coerenza |
| **Nuovo workspace pattern** | `.claude/rules.md` | Aggiungi esempi in sezione "Workspace System" |
| **Breaking changes** | `README.md` + `docs/history.md` | Documenta in entrambi con esempi before/after |

### Ordine di Aggiornamento

Quando completi un task significativo:

1. **Durante lo sviluppo:**
   - Se aggiungi/cambi regole → Aggiorna `.claude/rules.md` subito
   - Se cambi CLI → Aggiorna `README.md` nella sezione Usage

2. **A fine task/step:**
   - Aggiorna `docs/history.md` con nuova sezione Step (se applicabile)
   - Verifica `README.md` sia allineato con il codice
   - Verifica `.claude/rules.md` contenga tutte le regole applicate

3. **Prima del commit:**
   - Controlla che TUTTI i file di documentazione siano aggiornati
   - Verifica coerenza tra `README.md`, `.claude/rules.md`, `docs/history.md`

### Esempi Pratici

**Scenario 1: Completato nuovo Step 09 (Scheduler)**
```bash
1. Aggiorna docs/history.md:
   - Aggiungi sezione "## Step 09: Scheduler Automation"
   - Stato: ✅ Completato
   - Descrivi features implementate

2. Aggiorna README.md (se serve):
   - Nuovi comandi CLI per scheduler
   - Nuova sezione "Automation" se necessario

3. Commit con messaggio che include "(Step 09)"
```

**Scenario 2: Nuova regola "agents non possono chiamare datastore direttamente"**
```bash
1. Aggiorna .claude/rules.md:
   Sezione "❌ VIETATO ASSOLUTAMENTE":
   - Aggiungi esempio codice SBAGLIATO
   - Aggiungi esempio codice CORRETTO (usa pipeline)

2. Aggiorna README.md:
   - Sezione "Layer Rules" se esistente
   - O aggiungi nota in "Architecture"

3. Commit: "docs: add rule - agents cannot call datastore directly"
```

**Scenario 3: Nuovo comando CLI `python run.py scheduler start`**
```bash
1. Aggiorna README.md:
   Sezione "Usage" → "Scheduler management":
   ```bash
   python run.py scheduler start
   python run.py scheduler stop
   python run.py scheduler status
   ```

2. Aggiorna .claude/rules.md (se serve):
   Sezione "CLI Usage" con esempi

3. Commit: "feat: add scheduler CLI commands"
```

### Checklist Pre-Commit Documentazione

Prima di ogni commit, verifica:

- [ ] `.claude/rules.md` contiene tutte le regole che hai applicato nel codice?
- [ ] `README.md` riflette i comandi CLI attuali?
- [ ] `docs/history.md` è aggiornato con l'ultimo step completato?
- [ ] Esiste coerenza tra tutti i file di documentazione?
- [ ] Hai rimosso informazioni obsolete/deprecated?

### File da NON Modificare

- ❌ `.claude/project_context.md` - modificare SOLO per cambi strutturali al progetto
- ❌ `.env.example` - modificare SOLO quando aggiungi/rimuovi variabili d'ambiente
- ❌ File in `docs/` - NON creare nuovi file senza discutere prima

### Mantenere Documentazione Lean

**REGOLA D'ORO:** Documentazione concisa è meglio di documentazione verbose.

- `.claude/rules.md` → MAX 300 righe (regole essenziali)
- `README.md` → MAX 1500 righe (riferimento tecnico)
- `docs/history.md` → Sintesi per step, NON documentazione dettagliata

Se un file supera il limite, considera:
1. Spostare dettagli storici in `docs/history.md`
2. Rimuovere esempi ridondanti
3. Consolidare sezioni simili
