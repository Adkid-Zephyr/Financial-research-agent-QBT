REVIEW_RUBRIC = {
    "logic_chain": {
        "weight": 25,
        "criteria": [
            "核心观点与后文是否一致",
            "供需库存逻辑是否完整",
            "国际联动是否与国内逻辑衔接",
        ],
    },
    "data_quality": {
        "weight": 20,
        "criteria": [
            "是否有关键数字",
            "是否有来源标注",
            "数据是否具备近期属性",
        ],
    },
    "conclusion_clarity": {
        "weight": 20,
        "criteria": [
            "多空判断是否明确",
            "是否避免骑墙表述",
        ],
    },
    "risk_disclosure": {
        "weight": 15,
        "criteria": [
            "风险是否具体",
            "是否覆盖供需和政策不确定性",
        ],
    },
    "compliance": {
        "weight": 20,
        "blocking_checks": [
            "不含绝对预测",
            "不含投资建议",
            "含有 AI 免责声明",
        ],
    },
}
