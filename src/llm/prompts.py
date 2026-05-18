"""
Prompt-Templates für PKC-Antworten.
"""


def build_rag_prompt(query: str, context: str) -> list:
    """Einfacher RAG-Prompt ohne History (Fallback)."""
    return build_conversational_rag_prompt(query, context, history=[])


def build_report_prompt(topic: str, vault_context: str, web_context: str, history: str = "") -> list:
    """
    Prompt für die Erstellung eines strukturierten Berichts.
    Kombiniert Vault-Wissen mit aktuellen Web-Informationen.
    """
    system = (
        "Du bist PKC, ein persönlicher Wissensassistent. Du erstellst strukturierte, "
        "detaillierte Berichte auf Deutsch. Sprich den Nutzer mit 'du' an.\n\n"
        "Ein guter Bericht:\n"
        "- Hat eine klare Struktur mit Überschriften\n"
        "- Kombiniert Vault-Wissen mit aktuellen Web-Informationen\n"
        "- Unterscheidet klar zwischen gesichertem Wissen und aktuellen Entwicklungen\n"
        "- Enthält am Ende eine Quellenliste (Vault + Web)\n"
        "- Ist auf Deutsch, präzise und ohne Fülltext"
    )

    content_parts = []
    if vault_context:
        content_parts.append(f"=== Wissen aus deinem Vault ===\n{vault_context}")
    if web_context:
        content_parts.append(web_context)
    if history:
        content_parts.append(f"=== Bisheriger Gesprächskontext ===\n{history}")

    combined = "\n\n".join(content_parts)

    user_content = (
        f"Erstelle einen umfassenden Bericht zum Thema: **{topic}**\n\n"
        f"Verfügbare Informationen:\n{combined}\n\n"
        "Struktur des Berichts:\n"
        "# {Thema}\n"
        "## Überblick\n"
        "## Kernkonzepte & Details\n"
        "## Aktuelle Entwicklungen (falls Web-Quellen vorhanden)\n"
        "## Verbindungen & Zusammenhänge\n"
        "## Quellen\n\n"
        "Erstelle jetzt den vollständigen Bericht:"
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]


def build_conversational_rag_prompt(
    query: str,
    context: str,
    history: list = None,
    max_history: int = 6,
    web_context: str = "",
) -> list:
    """
    Conversational RAG-Prompt mit Gesprächsverlauf und Ideen-Vernetzung.

    history: Liste von {"role": "user"/"assistant", "content": "..."} — die letzten N Nachrichten.
    """
    system = (
        "Du bist PKC, ein persönlicher Wissensassistent. Du sprichst den Nutzer immer mit 'du' an.\n\n"
        "Deine Antworten sind:\n"
        "- Direkt und klar — kein akademisches Schreiben, keine übermäßigen Überschriften\n"
        "- Auf den Punkt — nicht länger als nötig\n"
        "- Konversationell — du führst ein Gespräch, kein Vortrag\n"
        "- Ehrlich — wenn etwas nicht im Kontext steht, sagst du es kurz\n\n"
        "Wenn du Verbindungen zu früheren Gesprächsthemen siehst, fließen diese natürlich "
        "in die Antwort ein — kein eigener Abschnitt dafür, keine Metakommentare wie "
        "'Da dies die erste Frage ist...'. Einfach antworten.\n\n"
        "Keine LaTeX-Notation. Kein formelles 'Sie'. Antworte auf Deutsch."
    )

    messages = [{"role": "system", "content": system}]

    # Gesprächsverlauf einbauen (letzte N Nachrichten)
    if history:
        for msg in history[-max_history:]:
            if msg.get("role") in ("user", "assistant") and msg.get("content"):
                messages.append({"role": msg["role"], "content": msg["content"]})

    # Aktuelle Frage mit RAG-Kontext
    parts = [f"Kontext aus der Wissensdatenbank:\n{context}"]
    if web_context:
        parts.append(web_context)
    parts.append(f"---\nFrage: {query}")
    user_content = "\n\n".join(parts)

    messages.append({"role": "user", "content": user_content})
    return messages


def build_conversation_summary_prompt(messages: list) -> list:
    """
    Erstellt einen detaillierten Prompt zur Gesprächszusammenfassung.
    Ziel: kompakter aber vollständiger Kontext für die Fortsetzung.
    """
    formatted = "\n\n".join(
        f"{'[Nutzer]' if m['role'] == 'user' else '[PKC]'}: {m['content']}"
        for m in messages
        if m.get("content") and m.get("role") in ("user", "assistant")
    )

    user_content = (
        "Erstelle eine detaillierte Zusammenfassung dieses Gesprächsverlaufs.\n\n"
        "Die Zusammenfassung dient als Kontext für die Fortsetzung des Gesprächs — "
        "sie ersetzt den Originalverlauf, muss also alle relevanten Informationen enthalten.\n\n"
        "Struktur der Zusammenfassung:\n"
        "1. **Behandelte Themen & Konzepte** — alle erwähnten Ideen, Begriffe, Theorien (nichts weglassen)\n"
        "2. **Erkannte Zusammenhänge** — Verbindungen zwischen Ideen, die im Gespräch aufgetaucht sind\n"
        "3. **Wichtige Erkenntnisse & Schlussfolgerungen** — was wurde festgestellt, entschieden, gelernt\n"
        "4. **Offene Fragen & ungelöste Punkte** — was noch nicht abschließend besprochen wurde\n"
        "5. **Intellektueller Faden** — die Richtung und Entwicklung des Gesprächs\n\n"
        "Schreibe fließend und konkret — keine vagen Formulierungen wie 'Es wurde über X gesprochen'.\n"
        "Stattdessen: 'Nutzer untersucht X im Kontext von Y, weil Z. PKC stellte Verbindung zu W fest.'\n\n"
        f"Gesprächsverlauf:\n{formatted}\n\n"
        "Detaillierte Zusammenfassung:"
    )

    return [
        {
            "role": "system",
            "content": "Du bist ein präziser Assistent zur Wissensanalyse. Erstelle vollständige, detailreiche Zusammenfassungen.",
        },
        {"role": "user", "content": user_content},
    ]


def build_summary_prompt(text: str) -> list:
    """Kurze Zusammenfassung eines Dokuments erstellen."""
    return [
        {
            "role": "user",
            "content": f"Fasse folgenden Text in 3-5 Sätzen zusammen:\n\n{text}",
        }
    ]
