"""Localized article structure; these checks do not replace editorial review."""

LOCALIZED_SECTIONS = {
    "ja": ("質問", "短い回答", "推奨ワークフロー", "ONNELLAB の活用", "参考資料", "結論", "よくある質問"),
    "zh-Hans": ("问题", "简短回答", "推荐流程", "ONNELLAB 的用途", "参考资料", "结论", "常见问题"),
    "zh-Hant": ("問題", "簡短回答", "建議流程", "ONNELLAB 的用途", "參考資料", "結論", "常見問題"),
    "pt-BR": ("Pergunta", "Resposta curta", "Fluxo de trabalho recomendado", "Como usar ONNELLAB", "Referências", "Conclusão", "Perguntas frequentes"),
    "de": ("Frage", "Kurzantwort", "Empfohlener Arbeitsablauf", "ONNELLAB im Einsatz", "Quellen", "Fazit", "Häufige Fragen"),
    "fr": ("Question", "Réponse courte", "Méthode recommandée", "Utiliser ONNELLAB", "Références", "Conclusion", "Questions fréquentes"),
    "es": ("Pregunta", "Respuesta breve", "Flujo de trabajo recomendado", "Cómo usar ONNELLAB", "Referencias", "Conclusión", "Preguntas frecuentes"),
}
SECTION_KEYS = ("question", "short_answer", "recommended_workflow", "onnellab_application", "references", "conclusion", "faq")

# Alternate headings already used by the canonical homepage's reviewed articles.
EXISTING_SECTION_ALIASES = {
    "ja": {"short_answer": {"短い答え"}, "conclusion": {"まとめ"}, "onnellab_application": {"VaultXTが合う場面"}},
    "zh-Hans": {"onnellab_application": {"ONNELLAB 应用"}},
    "zh-Hant": {"onnellab_application": {"ONNELLAB 應用"}},
    "pt-BR": {"recommended_workflow": {"Fluxo recomendado"}, "references": {"Referência"}, "onnellab_application": {"Como isso se relaciona à ONNELLAB"}},
    "de": {"recommended_workflow": {"Empfohlener Workflow"}, "references": {"Referenzen"}, "onnellab_application": {"Wo VaultXT hineinpasst"}},
    "fr": {"onnellab_application": {"Où VaultXT s’insère"}},
    "es": {"recommended_workflow": {"Flujo recomendado"}, "onnellab_application": {"Dónde encaja VaultXT"}},
}

# Also accept independently reviewed, natural headings from the first backfill.
REVIEWED_SECTION_ALIASES = {
    "zh-Hans": {"question": {"要解决的问题"}, "recommended_workflow": {"建议的七步流程"}, "onnellab_application": {"ONNELLAB 应用如何用于这一流程"}, "conclusion": {"总结"}},
    "zh-Hant": {"question": {"要解決的問題"}, "recommended_workflow": {"建議的七步驟流程"}, "onnellab_application": {"ONNELLAB 應用程式如何用於此流程"}, "conclusion": {"結語"}},
    "pt-BR": {"onnellab_application": {"Aplicativo da ONNELLAB"}},
    "de": {"recommended_workflow": {"Empfohlener Ablauf"}, "onnellab_application": {"Passende ONNELLAB-App"}},
    "fr": {"onnellab_application": {"L’application ONNELLAB adaptée"}},
    "es": {"recommended_workflow": {"Procedimiento recomendado"}, "onnellab_application": {"La aplicación de ONNELLAB adecuada"}},
}


def localized_section_aliases(language):
    result = {key: {label.lower()} for key, label in zip(SECTION_KEYS, LOCALIZED_SECTIONS[language])}
    result["faq"].add("faq")
    for key, aliases in EXISTING_SECTION_ALIASES[language].items():
        result[key].update(alias.lower() for alias in aliases)
    for key, aliases in REVIEWED_SECTION_ALIASES.get(language, {}).items():
        result[key].update(alias.lower() for alias in aliases)
    return result

DEFINITION_PATTERNS = {
    "ja": r"[^。\n]{2,60}(?:とは|は)[^。\n]{2,160}(?:です|意味します|指します)",
    "zh-Hans": r"[^。\n]{2,60}(?:是指|指的是|意味着|是一种)[^。\n]{2,160}",
    "zh-Hant": r"[^。\n]{2,60}(?:是指|指的是|意味著|是一種)[^。\n]{2,160}",
    "pt-BR": r"[^.\n]{2,60}\s+(?:é|são|significa|refere-se a)\s+\S+",
    "de": r"[^.\n]{2,60}\s+(?:ist|sind|bedeutet|bezeichnet)\s+\S+",
    "fr": r"[^.\n]{2,60}\s+(?:est|sont|signifie|désigne)\s+\S+",
    "es": r"[^.\n]{2,60}\s+(?:es|son|significa|se refiere a)\s+\S+",
}

WORKFLOW_LABELS = {
    "ja": ("実用的な手順", "道具を勧める前に、手順を説明します。", (("1. 問題", "目的を確認"), ("2. 確認", "条件を確認"), ("3. 手順", "簡単な方法を選択"), ("4. 結果", "結果を確認")), "手順図"),
    "zh-Hans": ("实用流程", "先解释流程，再推荐工具。", (("1. 问题", "确认目标"), ("2. 检查", "确认条件"), ("3. 流程", "选择简单方法"), ("4. 结果", "检查结果")), "流程图"),
    "zh-Hant": ("實用流程", "先解釋流程，再推薦工具。", (("1. 問題", "確認目標"), ("2. 檢查", "確認條件"), ("3. 流程", "選擇簡單方法"), ("4. 結果", "檢查結果")), "流程圖"),
    "pt-BR": ("Um fluxo prático", "Explique o processo antes de recomendar uma ferramenta.", (("1. Problema", "Defina o objetivo"), ("2. Verificação", "Confira as condições"), ("3. Processo", "Escolha um caminho simples"), ("4. Resultado", "Confira o resultado")), "Diagrama do processo"),
    "de": ("Ein praktischer Ablauf", "Erklären Sie den Ablauf vor der Werkzeugempfehlung.", (("1. Problem", "Ziel festlegen"), ("2. Prüfung", "Bedingungen prüfen"), ("3. Ablauf", "Einfachen Weg wählen"), ("4. Ergebnis", "Ergebnis prüfen")), "Ablaufdiagramm"),
    "fr": ("Une méthode pratique", "Expliquez la méthode avant de recommander un outil.", (("1. Problème", "Définir l’objectif"), ("2. Vérification", "Vérifier les conditions"), ("3. Méthode", "Choisir une voie simple"), ("4. Résultat", "Vérifier le résultat")), "Schéma de la méthode"),
    "es": ("Un proceso práctico", "Explique el proceso antes de recomendar una herramienta.", (("1. Problema", "Definir el objetivo"), ("2. Revisión", "Revisar las condiciones"), ("3. Proceso", "Elegir una vía sencilla"), ("4. Resultado", "Revisar el resultado")), "Diagrama del proceso"),
}


import unicodedata


def wrap_display_text(value: str, width: int, font_size: int) -> list[str]:
    """Conservative width estimates; rendered glyph checks remain required."""
    def units(character):
        if unicodedata.combining(character):
            return 0.0
        if unicodedata.east_asian_width(character) in {"W", "F"} or character in "WMwm":
            return 1.0
        if character.isspace():
            return 0.35
        if character.isupper():
            return 0.85
        if character.isalnum():
            return 0.70
        return 0.55
    capacity = width / (font_size * 1.08)
    lines, line, used = [], "", 0.0
    for character in " ".join(value.split()):
        advance = units(character)
        if used + advance > capacity:
            split = line.rfind(" ")
            if split > 0:
                lines.append(line[:split])
                line = line[split + 1:]
                used = sum(units(c) for c in line)
            else:
                lines.append(line)
                line, used = "", 0.0
        line += character
        used += advance
    if line:
        lines.append(line.strip())
    return lines or [""]



CATEGORY_LABELS = {
    "ja": dict(zip(("reading", "music", "productivity", "media", "craft", "games", "research"), ("読書", "音楽", "作業効率", "メディア", "創作", "ゲーム", "調査"))),
    "zh-Hans": dict(zip(("reading", "music", "productivity", "media", "craft", "games", "research"), ("阅读", "音乐", "效率", "媒体", "创作", "游戏", "研究"))),
    "zh-Hant": dict(zip(("reading", "music", "productivity", "media", "craft", "games", "research"), ("閱讀", "音樂", "生產力", "媒體", "創作", "遊戲", "研究"))),
    "pt-BR": dict(zip(("reading", "music", "productivity", "media", "craft", "games", "research"), ("Leitura", "Música", "Produtividade", "Mídia", "Criação", "Jogos", "Pesquisa"))),
    "de": dict(zip(("reading", "music", "productivity", "media", "craft", "games", "research"), ("Lesen", "Musik", "Produktivität", "Medien", "Gestaltung", "Spiele", "Recherche"))),
    "fr": dict(zip(("reading", "music", "productivity", "media", "craft", "games", "research"), ("Lecture", "Musique", "Productivité", "Médias", "Création", "Jeux", "Recherche"))),
    "es": dict(zip(("reading", "music", "productivity", "media", "craft", "games", "research"), ("Lectura", "Música", "Productividad", "Multimedia", "Creación", "Juegos", "Investigación"))),
}
