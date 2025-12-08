"""
ARVO Product Context - Reference document for all agents.

This module provides structured context about Arvo for PR outreach agents.
Import and use the relevant sections based on agent needs.
"""

# =============================================================================
# ARVO PRODUCT CONTEXT
# =============================================================================

ARVO_CONTEXT = {
    # -------------------------------------------------------------------------
    # 1. SNAPSHOT
    # -------------------------------------------------------------------------
    "snapshot": {
        "name": "Arvo",
        "website": "arvo.guru",
        "one_liner": "AI personal trainer che ti segue set-by-set in tempo reale, adattando pesi, ripetizioni e recuperi con 19 agenti AI specializzati.",
        "category": "AI Fitness / Workout Coaching",
        "stage": "Beta with early users, pre-revenue",
        "positioning": [
            "Personal trainer in tasca per chi fa allenamento serio con i pesi",
            "Per intermedi e avanzati, non principianti",
            "Sostituisce Excel + app generiche con sistema evidence-based e multi-agente"
        ]
    },

    # -------------------------------------------------------------------------
    # 2. UVP (Unique Value Propositions)
    # -------------------------------------------------------------------------
    "uvp": {
        "primary": "Coaching in tempo reale, set-by-set - non programmi fissi '3x10' ma adattamento live alla tua performance",

        "key_uvps": [
            {
                "title": "Set-by-set real-time coaching",
                "description": "L'app suggerisce peso, ripetizioni e recupero per ogni singolo set, aggiornandosi in base alla performance reale",
                "differentiator": True
            },
            {
                "title": "19 agenti AI specializzati",
                "description": "Non un solo modello generico: 19 agenti orchestrano decisioni diverse (programmazione, progressione, memoria, pattern)",
                "differentiator": True
            },
            {
                "title": "Progressive overload intelligente",
                "description": "Rispetta MEV/MAV/MRV, periodizzazione e progressive overload automatizzati con AI",
                "differentiator": True
            },
            {
                "title": "Sistema di memoria e pattern recognition",
                "description": "Estrae pattern su sostituzioni esercizi, preferenze attrezzatura, orari di performance per adattare scelte future",
                "differentiator": True
            },
            {
                "title": "Trasparenza: spiega il perché",
                "description": "L'AI spiega il reasoning dietro ogni scelta - raro nelle app fitness",
                "differentiator": True
            },
            {
                "title": "Rest timer intelligente",
                "description": "Calcola recupero tra set in tempo reale con logica warning/critical",
                "differentiator": False
            },
            {
                "title": "Supporto pratico in palestra",
                "description": "Alternative se macchinario occupato, idratazione, TUT/RIR logging, voice guidance",
                "differentiator": False
            },
            {
                "title": "Metodologie PRO integrate",
                "description": "Supporto a Kuba Method, Mentzer HIT/Heavy Duty, FST-7 e altri approcci avanzati",
                "differentiator": True
            },
            {
                "title": "Costo 1/10 di un PT",
                "description": "~15$/mese vs 600-900$/mese per PT umano",
                "differentiator": False
            }
        ]
    },

    # -------------------------------------------------------------------------
    # 3. IDEAL CUSTOMER PROFILE (ICP)
    # -------------------------------------------------------------------------
    "icp": {
        "primary_segment": "Intermediate-Advanced Lifter",

        "characteristics": [
            "Già allenato, sa usare i carichi, conosce esercizi principali",
            "Segue o vuole seguire metodologie strutturate (evidence-based, periodizzazione)",
            "Data-driven / tech-savvy - oggi usa Excel o app generiche ma insoddisfatto",
            "Bodybuilder / strength enthusiast - frequenta palestra seriamente",
            "Budget-sensitive vs PT umano - vorrebbe coach preciso ma non 600-1200€/mese"
        ],

        "not_for": [
            "Principianti assoluti che non conoscono gli esercizi base",
            "Chi cerca solo un timer/tracker semplice",
            "Chi non è interessato a metodologie strutturate"
        ],

        "jtbd": [  # Jobs To Be Done
            "Dammi una scheda ottimizzata per il mio metodo (Kuba, HIT, FST-7), giorni, attrezzatura e weak points",
            "Durante l'allenamento, dimmi quanto caricare, quante reps, quanto recuperare senza pensarci",
            "Se cambio esercizio, ho infortunio o sono stanco, adatta tutto in tempo reale",
            "Spiegami il perché delle scelte (non voglio magia nera)",
            "Tieni traccia di progressi, pattern, preferenze per migliorare la programmazione nel tempo"
        ]
    },

    # -------------------------------------------------------------------------
    # 4. FEATURES
    # -------------------------------------------------------------------------
    "features": {
        "core": [
            {
                "name": "AI Personal Trainer",
                "description": "Generazione personalizzata di workout con AI multi-agente"
            },
            {
                "name": "Parametric Program Builder",
                "description": "Costruisci split personalizzate e traccia tutto"
            },
            {
                "name": "Real-Time Coaching Loop",
                "description": "Adattamento set-by-set: peso, reps, rest"
            },
            {
                "name": "19-Agent Architecture",
                "description": "Workout Planner, Exercise Selector, Progression Engine, Fatigue Manager, MemoryConsolidator, etc."
            },
            {
                "name": "Memory & Pattern System",
                "description": "Analizza history per pattern su sostituzioni, preferenze, orari, risposte a volumi/intensità"
            }
        ],

        "gym_experience": [
            "Voice guidance durante set/sessione",
            "Log di TUT (Time Under Tension) e RIR per ogni set",
            "Consigli idratazione",
            "Suggerimenti automatici se macchina occupata (anche da foto)",
            "Libreria esercizi con video e coaching cues",
            "Check room (foto, comparazioni) per progress visivo",
            "Mindset logging"
        ],

        "methodology_support": [
            "Kuba Method",
            "Mentzer HIT / Heavy Duty",
            "FST-7",
            "Evidence-based periodization",
            "MEV/MAV/MRV volume landmarks"
        ]
    },

    # -------------------------------------------------------------------------
    # 5. PRICING
    # -------------------------------------------------------------------------
    "pricing": {
        "current_stage": "Beta, pre-revenue, waitlist for early access",
        "target_price": "~15$/month",
        "comparison": "1/10 del costo di un PT umano (150$/sessione, 600-900$/mese)",
        "note": "Pricing in definizione - non fare promesse rigide"
    },

    # -------------------------------------------------------------------------
    # 6. COMPETITORS
    # -------------------------------------------------------------------------
    "competitors": {
        "categories": [
            {
                "type": "Workout tracker classici",
                "examples": ["Strong", "Hevy", "Gym Log"],
                "weakness": "Loggano ma non prendono decisioni intelligenti"
            },
            {
                "type": "AI fitness app generiche",
                "examples": ["Fitbod", "FitnessAI"],
                "weakness": "Single-agent monolitico, poca personalizzazione metodologica, no reasoning esplicito"
            },
            {
                "type": "Personal trainer umano",
                "examples": ["Coach 1:1"],
                "weakness": "Costo alto (150$/sessione, 600-900$/mese)"
            }
        ],

        "arvo_differentiation": [
            "Multi-agente (19 specializzati) vs single-agent",
            "Real-time reasoning set-by-set vs programmi fissi",
            "Spiegazione delle decisioni vs black box",
            "Rispetto rigoroso metodologie PRO vs generici",
            "Pattern recognition su history vs no memoria"
        ]
    },

    # -------------------------------------------------------------------------
    # 7. TONE OF VOICE
    # -------------------------------------------------------------------------
    "tone": {
        "style": "Tecnico ma accessibile",
        "characteristics": [
            "Usa linguaggio evidence-based (MEV/MAV/MRV, RIR, periodizzazione) ma spiegato chiaramente",
            "Onesto sui limiti (non vede form, non sostituisce presenza coach)",
            "Anti-hype, anti 'AI finta'",
            "Critica app che si limitano a timer 60s o tracker glorificati"
        ],
        "avoid": [
            "Over-promise su sostituzione totale PT umano",
            "Hype generico tipo 'revolutionary AI'",
            "Linguaggio troppo consumer/basic"
        ]
    },

    # -------------------------------------------------------------------------
    # 8. LIMITATIONS (da comunicare onestamente)
    # -------------------------------------------------------------------------
    "limitations": [
        "Non vede ancora la form (video analysis)",
        "Non dà la 'pacca sulla spalla' motivazionale del coach umano",
        "Per intermedi/avanzati - principianti potrebbero non capire i concetti"
    ]
}


# =============================================================================
# HELPER FUNCTIONS FOR AGENTS
# =============================================================================

def get_context_for_agent(agent_type: str) -> dict:
    """
    Get relevant context sections based on agent type.

    Args:
        agent_type: Type of agent requesting context

    Returns:
        Dictionary with relevant context sections
    """
    agent_context_map = {
        # Article/content agents need product info for positioning
        "article_hunter": ["snapshot", "icp", "features.core"],
        "article_analyzer": ["snapshot", "uvp", "competitors"],
        "product_positioner": ["uvp", "features", "competitors", "icp"],

        # Author-related agents need tone and positioning
        "author_profiler": ["snapshot", "icp"],
        "outreach_strategist": ["uvp", "icp", "tone", "competitors"],

        # Email writing needs everything
        "email_writer": ["snapshot", "uvp", "features.core", "tone", "limitations"],

        # Quality agents need full context
        "spam_checker": ["tone"],
        "personalization_scorer": ["icp", "tone"]
    }

    sections = agent_context_map.get(agent_type, ["snapshot", "uvp"])

    result = {}
    for section in sections:
        if "." in section:
            parent, child = section.split(".")
            if parent in ARVO_CONTEXT and child in ARVO_CONTEXT[parent]:
                result[f"{parent}_{child}"] = ARVO_CONTEXT[parent][child]
        else:
            if section in ARVO_CONTEXT:
                result[section] = ARVO_CONTEXT[section]

    return result


def get_short_pitch() -> str:
    """Get a short pitch for outreach emails."""
    return (
        f"{ARVO_CONTEXT['snapshot']['name']} - "
        f"{ARVO_CONTEXT['snapshot']['one_liner']}"
    )


def get_key_differentiators() -> list:
    """Get list of key differentiators for positioning."""
    return [
        uvp["title"]
        for uvp in ARVO_CONTEXT["uvp"]["key_uvps"]
        if uvp.get("differentiator")
    ]


def get_target_audience_description() -> str:
    """Get description of target audience for article filtering."""
    icp = ARVO_CONTEXT["icp"]
    return (
        f"Target: {icp['primary_segment']}. "
        f"Characteristics: {', '.join(icp['characteristics'][:3])}. "
        f"NOT for: {', '.join(icp['not_for'][:2])}"
    )


def format_for_email_context() -> str:
    """Format context specifically for email writer agent."""
    ctx = ARVO_CONTEXT

    return f"""
PRODOTTO: {ctx['snapshot']['name']} ({ctx['snapshot']['website']})
CATEGORIA: {ctx['snapshot']['category']}

UVP PRINCIPALE:
{ctx['uvp']['primary']}

DIFFERENZIATORI CHIAVE:
{chr(10).join('- ' + d for d in get_key_differentiators()[:4])}

TARGET:
{ctx['icp']['primary_segment']} - {ctx['icp']['characteristics'][0]}

TONO:
{ctx['tone']['style']} - {ctx['tone']['characteristics'][0]}

EVITARE:
{chr(10).join('- ' + a for a in ctx['tone']['avoid'])}

LIMITI DA RICONOSCERE:
{chr(10).join('- ' + l for l in ctx['limitations'][:2])}
""".strip()


# =============================================================================
# EXPORT
# =============================================================================

__all__ = [
    "ARVO_CONTEXT",
    "get_context_for_agent",
    "get_short_pitch",
    "get_key_differentiators",
    "get_target_audience_description",
    "format_for_email_context"
]
