"""
ARVO Product Context - Complete Reference Document for All Agents.

This module provides structured context about Arvo for PR outreach agents,
marketing, UX, support, and any other AI agent working on Arvo.

Version: 2.0 - Complete reference with 3 ICPs, 19 agents architecture,
methodologies, pricing, and agent-specific guidelines.
"""

# =============================================================================
# ARVO COMPLETE PRODUCT CONTEXT
# =============================================================================

ARVO_CONTEXT = {
    # -------------------------------------------------------------------------
    # 1. SNAPSHOT
    # -------------------------------------------------------------------------
    "snapshot": {
        "name": "Arvo",
        "website": "arvo.guru",
        "tagline": "AI Routine, Very Optimized",
        "one_liner": (
            "AI Workout Coach per bodybuilding e powerbuilding in palestra, "
            "con 19 agenti specializzati che adattano ogni singola serie in tempo reale "
            "(peso, reps, rest, advanced techniques), rispettando metodologie avanzate "
            "come Kuba, Mentzer HIT, FST-7, Y3T, Mountain Dog, DC, PHAT, HST con 'scientific fidelity'."
        ),
        "category": "AI Fitness / Workout Coaching",
        "stage": "Beta - accesso completo gratuito ora",

        "key_facts": [
            "19 AI agents orchestrati in architettura multi-agente",
            "1300+ esercizi supportati",
            "8+ metodologie PRO implementate con centinaia di righe di config ciascuna",
            "Focus: bodybuilding / powerbuilding in palestra, non fitness generico"
        ],

        "definition": (
            "AI-powered workout programming application che fornisce: "
            "personalized workout generation, exercise selection & progression recommendations, "
            "workout tracking & performance analytics, implementazione di training methodologies, "
            "insight extraction da workout notes, exercise substitution suggestions."
        )
    },

    # -------------------------------------------------------------------------
    # 2. POSITIONING & SCOPE
    # -------------------------------------------------------------------------
    "positioning": {
        "what_arvo_is": [
            "Un AI personal trainer per la programmazione e l'esecuzione allenamenti con i pesi",
            "Un sistema che prende decisioni di coaching: split, esercizi, progressione, deload, tecniche avanzate, volume"
        ],

        "what_arvo_is_not": [
            "NON è un servizio medico, fisioterapico o di riabilitazione - non fornisce diagnosi né terapia",
            "NON sostituisce il medico/fisioterapista in caso di infortuni o condizioni cliniche",
            "NON è un'app di nutrizione (al massimo note/consigli generici)",
            "NON è pensato per corsi di gruppo cardio, yoga, zumba - focus = sala pesi",
            "NON è un workout generator per principianti totali che non hanno mai visto un bilanciere"
        ],

        "agent_rule": "Mai promettere ambiti medici o riabilitativi. In caso di dubbi, rimandare a medico/fisio."
    },

    # -------------------------------------------------------------------------
    # 3. ICP (Ideal Customer Profiles) - 3 SEGMENTS
    # -------------------------------------------------------------------------
    "icp": {
        # ICP #1: Gym Lifters (end user athletes)
        "gym_lifters": {
            "name": "Gym Lifters (utente finale atleta)",
            "segments": [
                {
                    "name": "Intermediate & Advanced Lifters",
                    "description": "Si allenano in palestra con split strutturate, practitioners di metodi (Kuba, HIT, FST-7, Y3T), interessati a MEV/MAV/MRV, periodizzazione, progressive overload"
                },
                {
                    "name": "Competitive Bodybuilders (IFBB, NPC, ecc.)",
                    "description": "Preparazione gara, controllo volume vs MRV, gestione deload e fatica, vogliono 24/7 AI coach e season-to-season learning"
                },
                {
                    "name": "Gym-Goers Who Want Results",
                    "description": "Non vogliono diventare nerd della programmazione; desiderano 'AI decides everything, just show up and lift'"
                }
            ],
            "jtbd": [
                "Dimmi che peso usare al prossimo set, tenendo conto di come è andato il set precedente",
                "Voglio seguire Kuba/Mentzer/FST-7/Y3T/Mountain Dog/DC/PHAT/HST in modo corretto senza ricordare tutte le regole",
                "Non voglio sbagliare volume: restare tra MEV–MAV–MRV per ogni muscolo e avere auto-deload quando serve",
                "Scrivo note naturali, e l'AI deve estrarre dolori, preferenze, fatica e adattare in automatico",
                "Voglio che l'app capisca i miei weak point e li priorizzi nel programma (es. upper chest)"
            ]
        },

        # ICP #2: Personal Trainers
        "personal_trainers": {
            "name": "Personal Trainer & Online Coach",
            "description": "Lavora 1:1 / small group (in presenza o online)",
            "pain_points": [
                "4–6 ore a settimana per cliente tra programmazione, Excel, WhatsApp, note sparse",
                "Il 'Monday Deadline Problem': sessioni fino a venerdì, programmi nel weekend, consegna all'ultimo lunedì → niente weekend"
            ],
            "goal": "Ridurre il tempo per cliente a ~15 min/sett, aumentare capacità clienti 3× mantenendo qualità",
            "jtbd": [
                "Voglio che l'AI generi programmi science-based in pochi secondi, per tutti i clienti",
                "Voglio un'unica dashboard dove vedere status, progressi e completamento di ogni cliente",
                "Voglio un calendario intelligente che gestisca booking, pacchetti, no-show e churn risk",
                "Voglio modalità di interfaccia diverse: semplice per il cliente base, avanzata per il nerd, completa per me"
            ]
        },

        # ICP #3: Gym Owners
        "gym_owners": {
            "name": "Gym Owners",
            "description": "Proprietari di palestre / catene che vogliono app brandizzata",
            "value_prop": "White-label fitness app with AI workout generation. Your brand, zero development.",
            "jtbd": [
                "Voglio offrire ai miei iscritti un'app AI avanzata a brand della palestra, senza svilupparla da zero",
                "Voglio che l'app sia white-label, ma usi la stessa intelligenza di Arvo"
            ]
        }
    },

    # -------------------------------------------------------------------------
    # 4. UVP (Unique Value Propositions) - BY SEGMENT
    # -------------------------------------------------------------------------
    "uvp": {
        "athletes": [
            {
                "title": "Set-by-set progression in tempo reale",
                "description": "Dopo ogni set, Arvo ricalcola il carico successivo in <500ms usando 6+ fattori (RIR, mental readiness, performance trend, rest reale, mesocycle phase, fatigue)",
                "differentiator": True
            },
            {
                "title": "19 AI Agents specializzati",
                "description": "Planning, Execution, Validation, Learning + 8 specialized agents (Hydration, WeakPointTargeting, VolumeOptimizer, ecc.)",
                "differentiator": True
            },
            {
                "title": "Metodologie PRO con 'scientific fidelity'",
                "description": "Implementazioni complete di Kuba, Heavy Duty/Mentzer HIT, FST-7, Y3T, Mountain Dog, DC, PHAT, HST con centinaia di righe di config ciascuna",
                "differentiator": True
            },
            {
                "title": "Timer che conosce il tuo metodo",
                "description": "Rest timer non generico: validazione colore-coded in base alla metodologia e all'esercizio (es. FST-7 30–45s, Y3T week-based)",
                "differentiator": True
            },
            {
                "title": "Note → Insight → Adattamento automatico",
                "description": "Scrivi come scriveresti a un coach: l'AI estrae pain, preferenze, fatica, suggerisce sostituzioni e modifica progressione future",
                "differentiator": True
            },
            {
                "title": "Smart Volume Management + Deload automatico",
                "description": "Tracciamento volume per muscolo vs MEV/MAV/MRV, detection overreaching, trigger auto-deload basato su plateau, mental readiness e volume eccessivo",
                "differentiator": True
            },
            {
                "title": "Offline-first in palestra",
                "description": "Le decisioni AI durante il workout possono essere eseguite offline con modelli cache; sync quando torni online",
                "differentiator": False
            },
            {
                "title": "Esperienza reale in palestra",
                "description": "Alternative se macchina occupata (anche da foto), consigli idratazione, log TUT e RIR, voice coaching, check room per foto progress, cues tecnici",
                "differentiator": False
            }
        ],

        "trainers": [
            {
                "title": "Stop working weekends – Monday Deadline Problem risolto",
                "description": "Da 4–6h/cliente/settimana a ~15 min/cliente/settimana → AI genera, coach approva, clienti si allenano, tutto tracciato",
                "differentiator": True
            },
            {
                "title": "AI workout generation in 4 step",
                "description": "Input client profile → AI genera mesociclo → coach rivede → cliente riceve",
                "differentiator": True
            },
            {
                "title": "Client dashboard unico + AI calendar",
                "description": "Tutti i clienti in un'unica vista + calendario AI-powered per booking, pacchetti, churn alerts e gap optimization",
                "differentiator": True
            },
            {
                "title": "3 interfacce (Simple, Coach, Advanced)",
                "description": "L'utente normale non viene travolto, il coach ha tutti i controlli, l'atleta nerd ha i dati",
                "differentiator": False
            }
        ],

        "gym_owners": [
            {
                "title": "White-label fitness app con AI workout generation",
                "description": "Stessa intelligenza Arvo, ma brand della palestra; zero sviluppo software interno",
                "differentiator": True
            }
        ]
    },

    # -------------------------------------------------------------------------
    # 5. FEATURES - ATHLETES
    # -------------------------------------------------------------------------
    "features_athletes": {
        "ai_architecture": {
            "description": "19 AI Agents organizzati in 4 layer + 8 specialized",
            "layers": {
                "planning": [
                    {"name": "SplitPlanner", "role": "struttura mesociclo (obiettivi + schedule)"},
                    {"name": "ExerciseSelector", "role": "esercizi per attrezzatura, preferenze, target muscolo"},
                    {"name": "RationaleGenerator", "role": "spiega in linguaggio umano le decisioni"}
                ],
                "execution": [
                    {"name": "ProgressionCalculator", "role": "progressione carichi <500ms"},
                    {"name": "AudioScriptGenerator", "role": "script audio coaching in tempo reale"}
                ],
                "validation": [
                    {"name": "SubstitutionValidator", "role": "equivalenza biomeccanica swap"},
                    {"name": "ModificationValidator", "role": "sicurezza modifiche"},
                    {"name": "ReorderValidator", "role": "ordine esercizi coerente con priorità muscolari"}
                ],
                "learning": [
                    {"name": "InsightsGenerator", "role": "estrae insight dalle note"},
                    {"name": "MemoryConsolidator", "role": "aggiorna la long-term memory utente"},
                    {"name": "PatternDetector", "role": "pattern swap, timing, volume, recovery"}
                ],
                "specialized": [
                    "EquipmentVision", "HydrationAdvisor", "FatigueAnalyzer", "InjuryPrevention",
                    "VolumeOptimizer", "DeloadTrigger", "WeakPointTargeting", "CycleIntelligence"
                ]
            }
        },

        "set_by_set_progression": {
            "description": "Dopo ogni set Arvo ricalcola peso target, range di reps e RIR target",
            "factors": ["RIR", "mental readiness", "performance trend", "mesocycle phase", "actual rest time", "fatigue accumulation"]
        },

        "methodologies": {
            "supported": [
                "Kuba Method",
                "Heavy Duty / Mentzer HIT",
                "FST-7",
                "Y3T",
                "Mountain Dog",
                "DC Training (Doggcrapp)",
                "PHAT",
                "HST"
            ],
            "note": "Ogni metodologia ha centinaia di righe di config e regole precise su: volumi, range reps, rest, tecniche, periodizzazione"
        },

        "volume_fatigue_deload": {
            "tracking": "MEV / MAV / MRV per ogni muscolo, con visual tipo '16/18 sets, MAV 18, MRV 22'",
            "auto_deload_triggers": [
                "plateau prolungati",
                "mental readiness ≤2 ripetuta",
                "volume > MRV per 2+ settimane"
            ]
        },

        "rest_timer": {
            "description": "Rest validation color-coded (Optimal / Acceptable / Warning / Critical) in base a metodo + esercizio",
            "examples": "FST-7 30–45s, Y3T week-based, Mountain Dog phase-based"
        },

        "notes_to_insights": {
            "description": "Scrivi note naturali; l'AI estrae pain, preferenze, fatigue e suggerisce deload/cambi esercizio",
            "extracts": ["pain (tipo, esercizio, severità, distretto)", "preferenze (cable rows > barbell rows)", "fatigue (es. overtrained shoulders)"],
            "consumers": ["ExerciseSelector", "ProgressionCalculator", "SubstitutionValidator"]
        },

        "advanced_techniques": {
            "supported": ["Drop set", "Rest-pause", "Superset", "Top set + backoff", "Myo-reps", "Giant set", "Cluster set", "Pyramid"],
            "logic": "Applicazione condizionata da: tipo esercizio, fatica, metodologia, experience level"
        },

        "plateau_detection": {
            "description": "Traccia da quante settimane usi un esercizio e identifica plateau",
            "example": "bench 100×8 per 3 mesocicli → suggerisce incline DB press"
        },

        "check_room": {
            "description": "Progress visivo con foto",
            "features": ["4 angolazioni foto (front, side, back)", "Peso e misure", "Comparazione Week1 vs Week8"]
        }
    },

    # -------------------------------------------------------------------------
    # 6. FEATURES - TRAINERS
    # -------------------------------------------------------------------------
    "features_trainers": {
        "monday_deadline_problem": {
            "before": "Fri sessioni, Sat scrivi programmi, Sun corri a chiuderli, Mon consegni last minute",
            "after": "AI genera in secondi, tu approvi, cliente riceve istant. Tempo: da 4–6h a ~15 min/cliente/settimana"
        },

        "ai_workout_generation": {
            "steps": [
                "Input client profile (goals, equipment, schedule, limitazioni)",
                "AI genera mesociclo completo",
                "Coach rivede & aggiusta",
                "Cliente riceve workout e inizia ad allenarsi"
            ]
        },

        "client_dashboard": {
            "features": [
                "Onboarding: invito con link/codice",
                "Bird's Eye View: status, prossimi workout, recent activity",
                "Real-time feedback sul completamento workout",
                "Full control: enable/disable, pausa programmi, modifiche live"
            ]
        },

        "ai_calendar": {
            "features": [
                "Gap Optimization – riempie buchi, crea blocchi liberi",
                "Personal Blocks – gestisce no-session con notifiche ai clienti",
                "Multi-Location – in-person, online, gruppi senza conflitti",
                "Smart Packages – sessioni rimanenti, reminder scadenza, suggerimento upgrade",
                "Churn Alerts – clienti inattivi o con cancellazioni frequenti",
                "Workload Balance – segnala giorni pieni/vuoti, suggerisce dove aprire/chiudere slot"
            ]
        },

        "progress_monitoring": {
            "features": [
                "Check Room per clienti (foto e comparazioni)",
                "Volume Analytics per muscolo",
                "Progressive Overload tracking (es. bench +12.5kg)",
                "Full history di workout, note, metriche"
            ]
        },

        "interface_modes": {
            "simple": "Workout recap semplice, animazioni esercizi, one-tap logging, celebratory progress",
            "coach": "Multi-client dashboard, program editor, analytics suite, strumenti di comunicazione",
            "advanced": "Metriche dettagliate, RIR/RPE, volume landmarks, custom adjustments",
            "agent_rule": "Se user_role == client_basic → Simple Mode. Se user_role == coach → Coach Mode. Se user_role == client_advanced → Advanced Mode."
        }
    },

    # -------------------------------------------------------------------------
    # 7. PRICING
    # -------------------------------------------------------------------------
    "pricing": {
        "current_stage": "Beta: accesso completo gratuito ora; poi possibilità di restare su Free o passare a Pro/Coach",

        "tiers": [
            {
                "name": "Free",
                "price": "€0",
                "features": [
                    "19 AI agents",
                    "Set-by-set progression",
                    "Simple Mode",
                    "Metodologie base + avanzate",
                    "MEV/MAV/MRV tracking",
                    "Audio coaching"
                ]
            },
            {
                "name": "Pro",
                "price": "€6/mese (o €60/anno)",
                "features": [
                    "Tutto in Free",
                    "AI pattern learning",
                    "Priority support",
                    "Export dati"
                ]
            },
            {
                "name": "Coach",
                "price": "€30/mese fino a 10 clienti (+€3/cliente/mese dopo)",
                "features": [
                    "Tutto in Pro",
                    "Client dashboard",
                    "Creazione/modifica workout clienti",
                    "Assegnazione metodologie per cliente",
                    "Analytics & monitoring volume/performance",
                    "Priority support"
                ]
            }
        ],

        "agent_note": "Il pricing può evolvere; non promettere condizioni 'per sempre'"
    },

    # -------------------------------------------------------------------------
    # 8. COMPETITORS & POSITIONING
    # -------------------------------------------------------------------------
    "competitors": {
        "archetypes": [
            {
                "type": "Excel / Fogli Google",
                "pros": "flessibili, custom",
                "cons": "0 intelligenza, nessun real-time, no rest timer, no memoria/pattern"
            },
            {
                "type": "Workout tracker classici (Strong/Hevy archetype)",
                "pros": "Tracciano set/reps/peso",
                "cons": "Non prendono decisioni intelligenti"
            },
            {
                "type": "Generic AI fitness app",
                "pros": "AI-powered",
                "cons": "AI monolitica, piani generici, nessuna metodologia PRO vera, niente reasoning spiegato"
            },
            {
                "type": "Personal Trainer umano",
                "pros": "Tecnica in presenza, feedback live",
                "cons": "Costoso, limitato a orari, non sempre disponibile mid-workout, non ha memoria perfetta di tutti i dati"
            }
        ],

        "arvo_differentiation": [
            "Architettura multi-agente, non singolo LLM generico",
            "Metodologie PRO implementate con fidelity, non versioni 'diete' semplificate",
            "Rest timer methodology-aware & color-coded",
            "Note → insight → auto-adattamento reale",
            "Volume management avanzato & deload triggers automatici"
        ]
    },

    # -------------------------------------------------------------------------
    # 9. TONE OF VOICE & BRAND
    # -------------------------------------------------------------------------
    "tone": {
        "style": "Tecnico ma accessibile",

        "characteristics": [
            "Usa concetti come MEV/MAV/MRV, RIR, periodization ma sempre spiegati",
            "Onesto sui limiti - non promette miracoli, chiarisce cosa l'AI può o non può fare",
            "Anti 'AI finta' - critico verso app che si dicono AI-powered ma sono solo timer + grafici",
            "Frasi dirette, poco marketingese",
            "English tecnico per i termini di training (RIR, MEV, MRV, ecc.)",
            "Tono 'coach intelligente + ingegnere': preciso, amichevole, zero fuffa"
        ],

        "avoid": [
            "Over-promise su ambiti medici o riabilitativi",
            "Hype generico tipo 'revolutionary AI'",
            "Linguaggio troppo consumer/basic",
            "Promesse 'per sempre' su pricing o feature"
        ]
    },

    # -------------------------------------------------------------------------
    # 10. LIMITATIONS (da comunicare onestamente)
    # -------------------------------------------------------------------------
    "limitations": [
        "Non è un servizio medico/fisioterapico - non fornisce diagnosi né terapia",
        "Non sostituisce medico/fisioterapista per infortuni o condizioni cliniche",
        "Non è app di nutrizione completa",
        "Focus sala pesi - non per cardio/yoga/zumba",
        "Simple Mode esiste ma non è per principianti totali che non hanno mai visto un bilanciere"
    ],

    # -------------------------------------------------------------------------
    # 11. AGENT-SPECIFIC GUIDELINES
    # -------------------------------------------------------------------------
    "agent_guidelines": {
        "product_context_agent": {
            "role": "Mantiene in memoria questo documento",
            "behavior": "Risponde alle richieste 'cos'è Arvo / quali feature / per chi è' restituendo estratti mirati (non tutto)"
        },

        "copy_marketing_agent": {
            "sections_to_use": ["positioning", "icp", "uvp", "features_athletes", "features_trainers", "pricing", "tone"]
        },

        "ads_campaign_agent": {
            "athletes_hooks": [
                "Set-by-set progression",
                "19 AI agents",
                "Metodologie PRO",
                "Timer intelligente"
            ],
            "trainers_hooks": [
                "Stop working weekends",
                "4–6h → 15min per cliente",
                "AI calendar",
                "3× client capacity"
            ]
        },

        "ux_product_agent": {
            "sections_to_use": ["features_athletes", "features_trainers"],
            "interface_modes_rule": "Simple Mode per client_basic, Coach Mode per coach, Advanced Mode per client_advanced"
        },

        "support_faq_agent": {
            "sections_to_use": ["positioning", "features_athletes", "features_trainers", "pricing", "limitations"],
            "critical_rule": "Mai dare consigli medici - rimandare sempre a medico/fisio"
        },

        "analytics_growth_agent": {
            "athletes_funnel": "Waitlist signup → First workout completed → 4-week active user",
            "athletes_metrics": [
                "% utenti che completano il primo ciclo di allenamento",
                "N° sessioni/set loggati a settimana per utente",
                "Utilizzo feature distintive (rest timer, exercise swap, advanced techniques, note → insights)"
            ],
            "trainers_funnel": "Coach signup → primo cliente invitato → primo mesociclo generato → utilizzo AI calendar",
            "trainers_metrics": [
                "N° clienti per coach",
                "Tempo medio/cliente",
                "Tasso di churn dei clienti dei coach"
            ]
        }
    }
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
        # PR Outreach agents
        "article_hunter": ["snapshot", "icp", "features_athletes"],
        "article_analyzer": ["snapshot", "uvp", "competitors"],
        "product_positioner": ["uvp", "features_athletes", "competitors", "icp"],
        "author_profiler": ["snapshot", "icp"],
        "outreach_strategist": ["uvp", "icp", "tone", "competitors"],
        "email_writer": ["snapshot", "uvp", "features_athletes", "tone", "limitations"],
        "spam_checker": ["tone"],
        "personalization_scorer": ["icp", "tone"],

        # Marketing agents
        "copy_marketing": ["positioning", "icp", "uvp", "features_athletes", "features_trainers", "pricing", "tone"],
        "ads_campaign": ["icp", "uvp", "agent_guidelines"],
        "landing_page": ["snapshot", "uvp", "features_athletes", "pricing", "tone"],

        # Product agents
        "ux_product": ["features_athletes", "features_trainers", "agent_guidelines"],
        "support_faq": ["positioning", "features_athletes", "features_trainers", "pricing", "limitations"],

        # Growth agents
        "analytics_growth": ["icp", "agent_guidelines"]
    }

    sections = agent_context_map.get(agent_type, ["snapshot", "uvp"])

    result = {}
    for section in sections:
        if section in ARVO_CONTEXT:
            result[section] = ARVO_CONTEXT[section]

    return result


def get_short_pitch() -> str:
    """Get a short pitch for outreach emails."""
    return (
        f"{ARVO_CONTEXT['snapshot']['name']} - "
        f"{ARVO_CONTEXT['snapshot']['tagline']}. "
        f"19 AI agents per coaching set-by-set in tempo reale."
    )


def get_key_differentiators() -> list:
    """Get list of key differentiators for positioning."""
    return ARVO_CONTEXT["competitors"]["arvo_differentiation"]


def get_target_audience_description(segment: str = "athletes") -> str:
    """Get description of target audience for article filtering."""
    if segment == "trainers":
        icp = ARVO_CONTEXT["icp"]["personal_trainers"]
        return (
            f"Target: {icp['name']}. "
            f"Pain: {icp['pain_points'][0]}. "
            f"Goal: {icp['goal']}"
        )
    elif segment == "gym_owners":
        icp = ARVO_CONTEXT["icp"]["gym_owners"]
        return f"Target: {icp['name']}. Value prop: {icp['value_prop']}"
    else:  # athletes
        icp = ARVO_CONTEXT["icp"]["gym_lifters"]
        segments = ", ".join([s["name"] for s in icp["segments"]])
        return f"Target: {icp['name']}. Segments: {segments}"


def get_methodologies() -> list:
    """Get list of supported training methodologies."""
    return ARVO_CONTEXT["features_athletes"]["methodologies"]["supported"]


def get_pricing_summary() -> str:
    """Get pricing summary string."""
    tiers = ARVO_CONTEXT["pricing"]["tiers"]
    return " | ".join([f"{t['name']}: {t['price']}" for t in tiers])


def format_for_email_context() -> str:
    """Format context specifically for email writer agent."""
    ctx = ARVO_CONTEXT

    # Get top UVPs for athletes
    top_uvps = [uvp["title"] for uvp in ctx["uvp"]["athletes"][:4] if uvp.get("differentiator")]

    return f"""
PRODOTTO: {ctx['snapshot']['name']} ({ctx['snapshot']['website']})
TAGLINE: {ctx['snapshot']['tagline']}
CATEGORIA: {ctx['snapshot']['category']}

ONE-LINER:
{ctx['snapshot']['one_liner'][:200]}...

KEY FACTS:
{chr(10).join('- ' + f for f in ctx['snapshot']['key_facts'])}

UVP PRINCIPALI (per atleti):
{chr(10).join('- ' + u for u in top_uvps)}

METODOLOGIE SUPPORTATE:
{', '.join(ctx['features_athletes']['methodologies']['supported'])}

TARGET PRIMARIO:
{ctx['icp']['gym_lifters']['segments'][0]['name']} - {ctx['icp']['gym_lifters']['segments'][0]['description'][:100]}

DIFFERENZIAZIONE VS COMPETITOR:
{chr(10).join('- ' + d for d in ctx['competitors']['arvo_differentiation'][:3])}

TONO:
{ctx['tone']['style']} - {ctx['tone']['characteristics'][0]}

EVITARE:
{chr(10).join('- ' + a for a in ctx['tone']['avoid'][:3])}

LIMITI DA RICONOSCERE:
{chr(10).join('- ' + l for l in ctx['limitations'][:2])}

PRICING:
{get_pricing_summary()}
""".strip()


def format_for_trainer_outreach() -> str:
    """Format context specifically for trainer-focused outreach."""
    ctx = ARVO_CONTEXT
    icp = ctx["icp"]["personal_trainers"]
    uvps = ctx["uvp"]["trainers"]

    return f"""
PRODOTTO: {ctx['snapshot']['name']} - Per Personal Trainer

PAIN POINT PRINCIPALE:
{icp['pain_points'][0]}

IL "MONDAY DEADLINE PROBLEM":
{icp['pain_points'][1]}

SOLUZIONE ARVO:
{icp['goal']}

UVP PER TRAINER:
{chr(10).join('- ' + u['title'] + ': ' + u['description'][:80] for u in uvps[:3])}

FEATURE CHIAVE:
- {ctx['features_trainers']['ai_calendar']['features'][0]}
- {ctx['features_trainers']['client_dashboard']['features'][1]}
- 3 interface modes: Simple (clienti), Coach (te), Advanced (nerd)

PRICING COACH:
{ctx['pricing']['tiers'][2]['price']}

TONO:
{ctx['tone']['style']} - zero fuffa, preciso, amichevole
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
    "get_methodologies",
    "get_pricing_summary",
    "format_for_email_context",
    "format_for_trainer_outreach"
]
