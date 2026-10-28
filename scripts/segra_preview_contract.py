"""Exact independently reviewed Segra section names; no quality thresholds."""
SLUG = "choose-safe-audio-working-copy"
HEADINGS = {
    "en": {
        "question": [
            "Question"
        ],
        "short_answer": [
            "Short Answer"
        ],
        "recommended_workflow": [
            "A Practical Workflow"
        ],
        "onnellab_application": [
            "Limits and Optional Tools"
        ],
        "references": [
            "Related Guides"
        ],
        "conclusion": [
            "Conclusion"
        ],
        "faq": [
            "FAQ"
        ]
    },
    "ko": {
        "question": [
            "질문"
        ],
        "short_answer": [
            "짧은 답변"
        ],
        "recommended_workflow": [
            "작업 순서"
        ],
        "onnellab_application": [
            "한계와 선택 가능한 도구"
        ],
        "references": [
            "관련 안내"
        ],
        "conclusion": [
            "정리"
        ],
        "faq": [
            "자주 묻는 질문"
        ]
    },
    "ja": {
        "question": [
            "質問"
        ],
        "short_answer": [
            "短い答え"
        ],
        "recommended_workflow": [
            "編集前後の手順"
        ],
        "onnellab_application": [
            "Segraを使う場合"
        ],
        "references": [
            "関連ガイド"
        ],
        "conclusion": [
            "まとめ"
        ],
        "faq": [
            "FAQ"
        ]
    },
    "zh-Hans": {
        "question": [
            "问题"
        ],
        "short_answer": [
            "简短回答"
        ],
        "recommended_workflow": [
            "建议的操作顺序"
        ],
        "onnellab_application": [
            "Segra可以用在哪一步？"
        ],
        "references": [
            "相关指南"
        ],
        "conclusion": [
            "总结"
        ],
        "faq": [
            "常见问题"
        ]
    },
    "zh-Hant": {
        "question": [
            "問題"
        ],
        "short_answer": [
            "簡短回答"
        ],
        "recommended_workflow": [
            "建議的操作順序"
        ],
        "onnellab_application": [
            "Segra可以用在哪一步？"
        ],
        "references": [
            "相關指南"
        ],
        "conclusion": [
            "總結"
        ],
        "faq": [
            "常見問題"
        ]
    },
    "pt-BR": {
        "question": [
            "Pergunta"
        ],
        "short_answer": [
            "Resposta curta"
        ],
        "recommended_workflow": [
            "Um procedimento prático"
        ],
        "onnellab_application": [
            "Limites e ferramentas opcionais"
        ],
        "references": [
            "Guias relacionados"
        ],
        "conclusion": [
            "Conclusão"
        ],
        "faq": [
            "Perguntas frequentes"
        ]
    },
    "de": {
        "question": [
            "Frage"
        ],
        "short_answer": [
            "Kurze Antwort"
        ],
        "recommended_workflow": [
            "Praktisches Vorgehen"
        ],
        "onnellab_application": [
            "Grenzen und optionale Werkzeuge"
        ],
        "references": [
            "Weiterführende Anleitungen"
        ],
        "conclusion": [
            "Fazit"
        ],
        "faq": [
            "Häufige Fragen"
        ]
    },
    "fr": {
        "question": [
            "Question"
        ],
        "short_answer": [
            "Réponse courte"
        ],
        "recommended_workflow": [
            "Une méthode pratique"
        ],
        "onnellab_application": [
            "Limites et outils possibles"
        ],
        "references": [
            "Guides connexes"
        ],
        "conclusion": [
            "Conclusion"
        ],
        "faq": [
            "Questions fréquentes"
        ]
    },
    "es": {
        "question": [
            "Pregunta"
        ],
        "short_answer": [
            "Respuesta breve"
        ],
        "recommended_workflow": [
            "Un procedimiento práctico"
        ],
        "onnellab_application": [
            "Límites y herramientas opcionales"
        ],
        "references": [
            "Guías relacionadas"
        ],
        "conclusion": [
            "Conclusión"
        ],
        "faq": [
            "Preguntas frecuentes"
        ]
    }
}

def section_aliases(locale):
    if locale not in HEADINGS:
        raise ValueError("Unsupported Segra locale")
    return {key: {value.lower() for value in values} for key, values in HEADINGS[locale].items()}
