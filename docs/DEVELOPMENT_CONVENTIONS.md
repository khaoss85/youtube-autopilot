# Development Conventions

## Error Handling & Fallback Logging

### ⚠️ IMPORTANTE: Sistema di Fallback Logging Centralizzato

Quando implementi logica di fallback (es. LLM fallisce → usa logica alternativa), **DEVI SEMPRE** usare il sistema di logging centralizzato per tracciare questi eventi.

### Come Usare `log_fallback()`

**Importa la funzione**:
```python
from yt_autopilot.core.logger import logger, log_fallback
```

**Usa nel try/except**:
```python
try:
    # Tenta operazione LLM o logica principale
    result = llm_generate_fn(...)
except Exception as e:
    logger.error(f"Operazione fallita: {e}")
    log_fallback(
        component="NOME_COMPONENTE",      # es. "LLM_CURATION", "MONETIZATION_QA"
        fallback_type="TIPO_FALLBACK",    # es. "MOMENTUM_ONLY", "RULE_BASED"
        reason=f"Motivo: {e}",            # Descrizione chiara del perché
        impact="HIGH"                     # "LOW", "MEDIUM", "HIGH"
    )
    # Usa logica di fallback
    result = fallback_logic(...)
```

### Impact Levels

- **LOW**: Degradazione minore, quasi impercettibile
- **MEDIUM**: Degradazione moderata, output ancora utilizzabile
- **HIGH**: Degradazione significativa, qualità output compromessa

### Esempi di Fallback Types

| Scenario | Component | Fallback Type | Impact |
|----------|-----------|---------------|--------|
| LLM curation fallisce → momentum-based | LLM_CURATION | MOMENTUM_ONLY | HIGH |
| LLM improvement fallisce → generic prompt | LLM_CURATION | GENERIC_IMPROVEMENT | MEDIUM |
| LLM validation fallisce → rule-based | MONETIZATION_QA | RULE_BASED | HIGH |
| API call fallisce → cache | API_CLIENT | CACHED_DATA | MEDIUM |
| Rendering fallisce → placeholder | VIDEO_RENDER | PLACEHOLDER_SCENE | HIGH |

### Perché È Importante

1. **Test Quality Validation**: Possiamo verificare se un test usa output reali o fallback
2. **Production Monitoring**: Tracciare rate di fallback nel tempo
3. **Debug Efficiency**: Identificare velocemente cause di fallback
4. **Quality Metrics**: Misurare "purezza" dei test (0 fallback = 100% reale)

### Validazione Fallback

**Controlla se test è puro** (nessun fallback):
```bash
grep -c "🚨 FALLBACK" test.log
# 0 = puro (ideale)
# >0 = fallback presenti (da rivedere)
```

**Mostra dettagli fallback**:
```bash
grep "🚨 FALLBACK" test.log
```

**Filtra per impact**:
```bash
grep "🚨 FALLBACK.*impact: HIGH" test.log
```

### Quando NON Usare log_fallback()

- Errori che non hanno fallback logic (usa solo logger.error())
- Retry semplici senza logica alternativa
- Validazioni che falliscono senza continuare

### ✅ Checklist per Nuove Feature

Quando implementi nuova feature con LLM o logica critica:

- [ ] Aggiungi try/except per gestire errori
- [ ] Implementa logica di fallback se necessario
- [ ] **USA `log_fallback()` per tracciare fallback**
- [ ] Definisci impact level appropriato
- [ ] Testa che il fallback funzioni correttamente
- [ ] Verifica che il test grep mostri i fallback

### Pattern da Evitare

❌ **Sbagliato** (fallback silenzioso):
```python
try:
    result = llm_generate_fn(...)
except:
    result = fallback_logic()  # NESSUN LOG!
```

✅ **Corretto** (fallback tracciato):
```python
try:
    result = llm_generate_fn(...)
except Exception as e:
    logger.error(f"LLM failed: {e}")
    log_fallback("COMPONENT", "FALLBACK_TYPE", f"LLM failed: {e}", impact="HIGH")
    result = fallback_logic()
```

### Esempi Reali nel Codebase

1. **LLM Trend Curator** (`llm_trend_curator.py:646`):
   ```python
   except Exception as e:
       logger.error(f"LLM curation failed: {e}")
       log_fallback("LLM_CURATION", "MOMENTUM_ONLY", f"LLM call failed: {e}", impact="HIGH")
       curated_trends = momentum_based_curation(trends, top_n)
   ```

2. **Monetization QA** (`monetization_qa.py:307`):
   ```python
   except Exception as e:
       logger.error(f"Monetization QA AI validation failed: {e}")
       log_fallback("MONETIZATION_QA", "RULE_BASED", f"LLM validation failed: {e}", impact="HIGH")
       return rule_based_validation(package)
   ```

### Documentazione Completa

Vedi `/tmp/FALLBACK_LOGGING_SYSTEM.md` per documentazione dettagliata del sistema.

---

## Log Message Truncation

### ⚠️ IMPORTANTE: Usa Sempre `truncate_for_log()` per Troncamento

Quando loggi testo lungo (reasoning AI, task descriptions, content previews), **DEVI SEMPRE** usare la funzione `truncate_for_log()` invece di troncamento manuale con slicing.

### Perché NON Usare Troncamento Manuale

❌ **Problemi con troncamento manuale**:
```python
logger.info(f"Reasoning: {reasoning[:100]}...")  # SBAGLIATO
```

1. **Inconsistenza**: Ogni sviluppatore sceglie lunghezze diverse (50, 100, 120, 150...)
2. **Crash con None**: Se `reasoning` è None, il codice crasha
3. **Manutenzione difficile**: Per cambiare il limite devi modificare decine di file
4. **Leggibilità scarsa**: 100 caratteri spesso tagliano a metà frase

✅ **Vantaggi con `truncate_for_log()`**:
```python
logger.info(f"Reasoning: {truncate_for_log(reasoning, LOG_TRUNCATE_REASONING)}")  # CORRETTO
```

1. **Consistenza totale**: Tutti usano le stesse lunghezze
2. **Sicuro**: Gestisce None/stringhe vuote automaticamente
3. **Configurabile**: Cambi limite in un solo posto (`config.py`)
4. **Leggibile**: Limiti ottimizzati per non floodare ma essere comprensibili

### Come Usare `truncate_for_log()`

**Importa le utilities**:
```python
from yt_autopilot.core.logger import logger, truncate_for_log
from yt_autopilot.core.config import (
    LOG_TRUNCATE_TASK,       # 200 chars - Task descriptions
    LOG_TRUNCATE_REASONING,  # 300 chars - AI reasoning
    LOG_TRUNCATE_CONTENT,    # 300 chars - Content previews
    LOG_TRUNCATE_SHORT       # 100 chars - Titles, identifiers
)
```

**Usa nelle log calls**:
```python
# AI reasoning (decisioni strategiche, spiegazioni)
logger.info(f"  Reasoning: {truncate_for_log(reasoning, LOG_TRUNCATE_REASONING)}")

# Task descriptions per LLM
logger.info(f"LLM task: {truncate_for_log(task, LOG_TRUNCATE_TASK)}")

# Content previews (script snippets, generated text)
logger.info(f"Generated: {truncate_for_log(content, LOG_TRUNCATE_CONTENT)}")

# Short text (titles, labels)
logger.info(f"Title: {truncate_for_log(title, LOG_TRUNCATE_SHORT)}")
```

### Costanti Disponibili

| Costante | Limite | Uso Previsto | Esempi |
|----------|--------|--------------|--------|
| `LOG_TRUNCATE_TASK` | 200 chars | Task LLM, istruzioni | "Generate script for topic..." |
| `LOG_TRUNCATE_REASONING` | 300 chars | AI reasoning, rationale | Editorial decisions, format choices |
| `LOG_TRUNCATE_CONTENT` | 300 chars | Content previews | Script snippets, generated text |
| `LOG_TRUNCATE_SHORT` | 100 chars | Titles, identifiers | Video titles, labels |

### Pattern Sbagliato vs Corretto

❌ **Sbagliato** (troncamento manuale inconsistente):
```python
# Problemi: crashes con None, inconsistenza, troppo corto
logger.info(f"Task: {task[:50]}...")
logger.info(f"Reasoning: {decision.reasoning_summary[:100]}...")
logger.info(f"Content: {content[:120] if content else 'None'}...")
```

✅ **Corretto** (centralizzato e sicuro):
```python
# Consistente, sicuro, ottimizzato
logger.info(f"Task: {truncate_for_log(task, LOG_TRUNCATE_TASK)}")
logger.info(f"Reasoning: {truncate_for_log(decision.reasoning_summary, LOG_TRUNCATE_REASONING)}")
logger.info(f"Content: {truncate_for_log(content, LOG_TRUNCATE_CONTENT)}")
```

### Quando Usare Quale Costante

**`LOG_TRUNCATE_REASONING` (300 chars)** - Il più importante:
- AI reasoning da Editorial Strategist, Duration Strategist, Format Reconciler
- Spiegazioni di decisioni strategiche (perché questo formato, durata, CTA)
- Decision rationale che deve essere comprensibile per debug

**`LOG_TRUNCATE_TASK` (200 chars)**:
- Task descriptions passate all'LLM Router
- Istruzioni high-level per agenti AI
- Context che spiega cosa l'AI deve fare

**`LOG_TRUNCATE_CONTENT` (300 chars)**:
- Preview di script generati
- Snippet di content improvements
- Fallback text previews
- Generated text samples

**`LOG_TRUNCATE_SHORT` (100 chars)**:
- Video titles, trending topics
- Labels brevi
- Short identifiers

### Esempi Reali nel Codebase

1. **LLM Router Task** (`services/llm_router.py:81`):
   ```python
   logger.info(f"LLM Router: Generating text for role={role}, task={truncate_for_log(task, LOG_TRUNCATE_TASK)}")
   ```

2. **Editorial Decision Reasoning** (`pipeline/build_video_package.py:905`):
   ```python
   logger.info(f"  Reasoning: {truncate_for_log(editorial_decision.reasoning_summary, LOG_TRUNCATE_REASONING)}")
   ```

3. **Format Reconciliation** (`agents/format_reconciler.py:200`):
   ```python
   logger.info(f"  Reasoning: {truncate_for_log(reconciled['reasoning'], LOG_TRUNCATE_REASONING)}")
   ```

4. **CTA Strategy** (`agents/cta_strategist.py:286`):
   ```python
   logger.info(f"  Reasoning: {truncate_for_log(cta_strategy['reasoning'], LOG_TRUNCATE_REASONING)}")
   ```

### ✅ Checklist per Nuovi Log Messages

Quando aggiungi nuovi log messages con testo potenzialmente lungo:

- [ ] **NON usare** troncamento manuale `[:N]...`
- [ ] Importa `truncate_for_log` e la costante appropriata
- [ ] Usa `LOG_TRUNCATE_REASONING` per AI reasoning/decisions (default sicuro)
- [ ] Usa `LOG_TRUNCATE_TASK` per task descriptions
- [ ] Usa `LOG_TRUNCATE_CONTENT` per content previews
- [ ] Usa `LOG_TRUNCATE_SHORT` per titles/labels brevi
- [ ] Testa che il log message sia leggibile senza essere troppo verboso

### Come Cambiare i Limiti Globalmente

Se vuoi modificare i limiti di troncamento, cambia solo `yt_autopilot/core/config.py`:

```python
# In config.py (righe 229-243)
LOG_TRUNCATE_TASK = 200        # Cambia qui per tutti i task
LOG_TRUNCATE_REASONING = 300   # Cambia qui per tutto il reasoning
LOG_TRUNCATE_CONTENT = 300     # Cambia qui per tutto il content
LOG_TRUNCATE_SHORT = 100       # Cambia qui per tutti i titoli
```

Non serve modificare nessun altro file - il cambiamento si propaga automaticamente.

---

## Altri Standard di Sviluppo

### Logging Generale

- Usa sempre `from yt_autopilot.core.logger import logger`
- NON usare `print()` per debugging
- Usa livelli appropriati: DEBUG, INFO, WARNING, ERROR
- **SEMPRE** usa `truncate_for_log()` per testo lungo (vedi sezione precedente)

### Test

- Ogni test dovrebbe controllare fallback count
- Target: 0 fallback per test di qualità
- Documenta eventuali fallback previsti

### Error Messages

- Includi sempre contesto dell'errore
- Usa f-strings per formattare messaggi
- Includi parametri rilevanti nel messaggio

---

**Data ultima revisione**: 2025-11-02

**Responsabile**: Sistema di logging centralizzato implementato e validato. Log truncation utilities standardizzate.
