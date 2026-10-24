"""Exact independently reviewed VaultXT section names; no quality thresholds."""
SLUG = "make-long-plain-text-easier-to-navigate"
HEADINGS = {
    "en": {
        "question": [
            "Question"
        ],
        "short_answer": [
            "Short Answer"
        ],
        "recommended_workflow": [
            "Recommended Workflow"
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
            "짧은 답"
        ],
        "recommended_workflow": [
            "다섯 단계 작업 방법"
        ],
        "onnellab_application": [
            "선택 가능한 도구: VaultXT"
        ],
        "references": [
            "함께 읽기"
        ],
        "conclusion": [
            "결론"
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
            "五つの手順"
        ],
        "onnellab_application": [
            "選択肢の一つ：VaultXT"
        ],
        "references": [
            "関連ガイド"
        ],
        "conclusion": [
            "結論"
        ],
        "faq": [
            "よくある質問"
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
            "五步工作流程"
        ],
        "onnellab_application": [
            "一种可选工具：VaultXT"
        ],
        "references": [
            "延伸阅读"
        ],
        "conclusion": [
            "结论"
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
            "五步工作流程"
        ],
        "onnellab_application": [
            "一種可選工具：VaultXT"
        ],
        "references": [
            "延伸閱讀"
        ],
        "conclusion": [
            "結論"
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
            "Fluxo de trabalho em cinco etapas"
        ],
        "onnellab_application": [
            "Uma opção de aplicativo"
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
            "Kurzantwort"
        ],
        "recommended_workflow": [
            "Vorgehen in fünf Schritten"
        ],
        "onnellab_application": [
            "Eine mögliche App"
        ],
        "references": [
            "Weiterführende Leitfäden"
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
            "Une méthode en cinq étapes"
        ],
        "onnellab_application": [
            "Une application possible"
        ],
        "references": [
            "Guides complémentaires"
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
            "Un método en cinco pasos"
        ],
        "onnellab_application": [
            "Una aplicación opcional"
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
        raise ValueError("Unsupported VaultXT locale")
    return {key: {value.lower() for value in values} for key, values in HEADINGS[locale].items()}
