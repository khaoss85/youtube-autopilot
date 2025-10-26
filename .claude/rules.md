# 🚨 REGOLE NON NEGOZIABILI - SEMPRE RISPETTARE

Queste regole sono **CRITICHE** per l'architettura del progetto. Violerle causa problemi gravi.

---

## ❌ VIETATO ASSOLUTAMENTE

### Layer Import Restrictions

```
❌ agents/ NON può importare:
   - services/
   - pipeline/
   - io/

❌ services/ NON può importare:
   - agents/
   - pipeline/

❌ core/ NON può importare:
   - NULLA fuori da core/

❌ io/ NON può importare:
   - agents/
   - services/
```

**Regola d'oro:**
- **Agents = Brain** (think, don't do)
- **Services = Hands** (do, don't think)
- **Pipeline = Coordinator** (tells brain to think, tells hands to do)

**Solo `pipeline/` può importare sia agents che services.**

---

## ✅ OBBLIGATORIO SEMPRE

### 1. Schemas Centralizzati

```python
✅ CORRETTO:
from yt_autopilot.core.schemas import VideoPlan, VideoScript

❌ SBAGLIATO:
from pydantic import BaseModel
class VideoPlan(BaseModel):  # NO! Usa quello in core/schemas.py
```

**Tutti i modelli dati SOLO da `core/schemas.py`**

### 2. Type Hints Ovunque

```python
✅ CORRETTO:
def generate_video_plan(trends: List[TrendCandidate], memory: Dict) -> VideoPlan:

❌ SBAGLIATO:
def generate_video_plan(trends, memory):  # NO! Mancano type hints
```

### 3. Logging Centralizzato

```python
✅ CORRETTO:
from yt_autopilot.core.logger import logger
logger.info("Processing video...")

❌ SBAGLIATO:
import logging
logging.info("Processing video...")  # NO! Usa core.logger
```

### 4. Agents = Pure Functions

```python
✅ CORRETTO (agent):
def write_script(plan: VideoPlan, memory: Dict) -> VideoScript:
    # Solo reasoning, ritorna dati strutturati
    return VideoScript(hook="...", bullets=[...])

❌ SBAGLIATO (agent):
def write_script(plan: VideoPlan, memory: Dict) -> VideoScript:
    with open("script.txt", "w") as f:  # NO! Agents non toccano filesystem
        f.write("...")
    return VideoScript(...)
```

**Agents non devono:**
- Leggere/scrivere file
- Chiamare API esterne
- Fare operazioni di I/O
- Avere side effects

---

## 🏗️ Workspace System (Step 08)

### Sempre usare workspace_id

```python
✅ CORRETTO:
build_video_package(workspace_id="tech_ai_creator")
save_script_draft(ready, datetime, workspace_id="tech_ai_creator")

❌ SBAGLIATO:
build_video_package()  # NO! Workspace_id obbligatorio
```

### Review commands filtrano per workspace

```bash
✅ DEFAULT (workspace attivo):
python run.py review scripts

✅ CROSS-WORKSPACE (quando serve):
python run.py review scripts --all-workspaces
```

---

## 🔐 Security & Compliance

### VIETATO nei contenuti generati

❌ **MAI generare contenuti con:**
- Promesse mediche garantite
- Hate speech o insulti
- Politica aggressiva/partitica
- Claim legali borderline
- Copyright violations esplicite

### OBBLIGATORIO nei contenuti

✅ **Sempre rispettare:**
- Brand tone del canale (diretto, utile, professionale)
- Formato verticale 9:16 per Shorts
- Compliance check via QualityReviewer

---

## 📝 Development Workflow

### Prima di modificare codice:

1. ✅ Verifica che non violi Layer Rules
2. ✅ Aggiungi type hints
3. ✅ Usa schemas da `core/schemas.py`
4. ✅ Testa con workspace attivo
5. ✅ Aggiorna documentazione se serve

### Quando aggiungi nuovi modelli:

1. ✅ Aggiungi a `core/schemas.py` PRIMA
2. ✅ Usa Pydantic BaseModel
3. ✅ Aggiungi docstring e esempi
4. ✅ Type hints completi

---

## 🚀 CLI Usage (Step 08)

### Workspace management

```bash
python run.py workspace list      # Lista workspace
python run.py workspace switch <id>  # Cambia workspace
python run.py workspace create    # Crea nuovo workspace
```

### Review workflow (2-gate)

```bash
# Gate 1: Script review (cheap)
python run.py review scripts
python run.py review approve-script <id> --approved-by "you@company"

# Gate 2: Video review (after assets)
python run.py review list
python run.py review publish <id> --approved-by "you@company"
```

---

## 💡 Quick Reference

**Dove mettere il codice:**

| Cosa devi fare | Dove metterlo |
|----------------|---------------|
| Ragionare su trend/script/visuals | `agents/` |
| Chiamare API esterne (Veo, YouTube) | `services/` |
| Orchestrare agents + services | `pipeline/` |
| Salvare/leggere dati | `io/` |
| Definire modelli dati | `core/schemas.py` |
| Config/logging | `core/` |

**Ricorda:**
- 🧠 Agents = think
- 👐 Services = do
- 🎯 Pipeline = coordinate
- 🏢 Workspace = isolation
