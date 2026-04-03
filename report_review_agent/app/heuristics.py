from __future__ import annotations

import re
from dataclasses import dataclass

from report_review_agent.app import config
from report_review_agent.app.models import DimensionScore, ImprovementAction, ParsedDocument, ReviewFinding
from report_review_agent.app.rubric import RUBRIC

HEADING_RE = re.compile(r"^(#{1,6}\s+|[一二三四五六七八九十]+、|[0-9]+\.\s+)", re.MULTILINE)
SOURCE_RE = re.compile(r"(来源[:：]|source[:：]|according to|数据来源|参考资料|citation)", re.IGNORECASE)
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?(?:%|bp|bps|亿|万|吨|元|美元)?")
RISK_RE = re.compile(r"(风险|risk|uncertainty|不确定性| downside |上行风险|下行风险)", re.IGNORECASE)
SUMMARY_RE = re.compile(r"(核心观点|摘要|结论|executive summary|summary|investment view|观点)", re.IGNORECASE)
CONCLUSION_RE = re.compile(r"(结论|展望|判断|outlook|conclusion)", re.IGNORECASE)
CAUSAL_RE = re.compile(r"(因此|因为|由于|所以|表明|意味着|driven by|because|therefore|however|while|leading to)", re.IGNORECASE)
HEDGING_RE = re.compile(r"(可能|或许|大概|也许|unclear|maybe|perhaps|both ways)", re.IGNORECASE)
DISCLAIMER_RE = re.compile(r"(仅供参考|不构成投资建议|for reference only|not investment advice)", re.IGNORECASE)
ABSOLUTE_RE = re.compile(r"(必涨|必跌|一定会|肯定会|稳赚|must rise|must fall|guaranteed)", re.IGNORECASE)
ADVICE_RE = re.compile(r"(建议买入|建议卖出|应当做多|应当做空|strong buy|buy now|sell now|建仓)", re.IGNORECASE)


@dataclass
class HeuristicSnapshot:
    overall_score: float
    status: str
    passed: bool
    executive_summary: str
    strengths: list[str]
    dimension_scores: list[DimensionScore]
    findings: list[ReviewFinding]
    improvement_actions: list[ImprovementAction]
    suggested_outline: list[str]
    blocking_issues: list[str]
    metrics: dict[str, float | int]


class HeuristicReviewer:
    def review(self, document: ParsedDocument) -> HeuristicSnapshot:
        text = document.content
        normalized = text.strip()
        if not normalized:
            finding = ReviewFinding(
                severity="critical",
                title="文档内容为空",
                detail="上传文件中没有可评审的正文内容。",
                recommendation="请上传完整研报，格式支持 Markdown、纯文本或可提取文本的 PDF。",
            )
            return HeuristicSnapshot(
                overall_score=0.0,
                status="fail",
                passed=False,
                executive_summary="本次上传无法评审，因为系统没有读取到可用的正文内容。",
                strengths=[],
                dimension_scores=[],
                findings=[finding],
                improvement_actions=[
                    ImprovementAction(
                        priority=1,
                        title="补充可读取的原文",
                        action="请重新上传原始研报，优先使用 Markdown、纯文本或电子版 PDF。",
                    )
                ],
                suggested_outline=[],
                blocking_issues=["empty_document"],
                metrics={"char_count": 0},
            )

        headings = HEADING_RE.findall(text)
        source_hits = SOURCE_RE.findall(text)
        number_hits = NUMBER_RE.findall(text)
        risk_hits = RISK_RE.findall(text)
        summary_present = bool(SUMMARY_RE.search(text))
        conclusion_present = bool(CONCLUSION_RE.search(text))
        causal_hits = CAUSAL_RE.findall(text)
        hedging_hits = HEDGING_RE.findall(text)
        disclaimer_present = bool(DISCLAIMER_RE.search(text))
        absolute_hit = bool(ABSOLUTE_RE.search(text))
        advice_hit = bool(ADVICE_RE.search(text))

        findings: list[ReviewFinding] = []
        actions: list[ImprovementAction] = []
        strengths: list[str] = []
        blocking_issues: list[str] = []

        structure_score = self._score_structure(len(headings), summary_present, conclusion_present, len(text))
        evidence_score = self._score_evidence(len(number_hits), len(source_hits), len(text), findings, actions)
        reasoning_score = self._score_reasoning(
            len(causal_hits),
            len(hedging_hits),
            summary_present,
            conclusion_present,
            findings,
            actions,
        )
        risk_score = self._score_risk(len(risk_hits), text, findings, actions)
        compliance_score = self._score_compliance(
            absolute_hit=absolute_hit,
            advice_hit=advice_hit,
            disclaimer_present=disclaimer_present,
            findings=findings,
            actions=actions,
            blocking_issues=blocking_issues,
        )

        if structure_score >= 15:
            strengths.append("报告结构层级较完整，便于读者定位关键信息，也便于后续修订。")
        if evidence_score >= 18:
            strengths.append("报告包含一定数量的数据或来源标注，基础证据框架较为完整。")
        if reasoning_score >= 14:
            strengths.append("报告不仅在描述现象，也能体现一定的因果推理链条。")
        if risk_score >= 10:
            strengths.append("报告对不确定性和反向情景有一定覆盖，不是单边叙述。")
        if compliance_score >= 16:
            strengths.append("报告整体措辞较为克制，未出现明显的直接交易指令。")

        dimension_scores = [
            DimensionScore(
                key="structure_completeness",
                label=RUBRIC["structure_completeness"]["label"],
                score=structure_score,
                max_score=RUBRIC["structure_completeness"]["max_score"],
                rationale=f"检测到 {len(headings)} 个标题标记；摘要存在={summary_present}；结论存在={conclusion_present}。",
            ),
            DimensionScore(
                key="evidence_traceability",
                label=RUBRIC["evidence_traceability"]["label"],
                score=evidence_score,
                max_score=RUBRIC["evidence_traceability"]["max_score"],
                rationale=f"检测到 {len(number_hits)} 处数字信息，{len(source_hits)} 处来源标记。",
            ),
            DimensionScore(
                key="reasoning_clarity",
                label=RUBRIC["reasoning_clarity"]["label"],
                score=reasoning_score,
                max_score=RUBRIC["reasoning_clarity"]["max_score"],
                rationale=f"检测到 {len(causal_hits)} 处因果连接词，{len(hedging_hits)} 处模糊表述。",
            ),
            DimensionScore(
                key="risk_balance",
                label=RUBRIC["risk_balance"]["label"],
                score=risk_score,
                max_score=RUBRIC["risk_balance"]["max_score"],
                rationale=f"检测到 {len(risk_hits)} 处风险相关表达。",
            ),
            DimensionScore(
                key="compliance_objectivity",
                label=RUBRIC["compliance_objectivity"]["label"],
                score=compliance_score,
                max_score=RUBRIC["compliance_objectivity"]["max_score"],
                rationale=f"免责声明存在={disclaimer_present}；绝对化表述={absolute_hit}；直接建议={advice_hit}。",
            ),
        ]

        overall_score = round(sum(item.score for item in dimension_scores), 1)
        status = self._resolve_status(overall_score, blocking_issues)
        passed = status == "pass"
        if not strengths:
            strengths.append("报告具备基本内容量，足以开展结构化质量评审。")

        if not actions:
            actions.append(
                ImprovementAction(
                    priority=1,
                    title="强化证据到结论的映射",
                    action="每个核心判断都补一条直接数据证据，并说明这条证据为什么会改变最终结论。",
                    target_sections=["正文", "结论"],
                )
            )

        suggested_outline = [
            "执行摘要：一句明确判断 + 两条核心依据",
            "关键证据：列出核心数据、事实与来源",
            "推理链条：解释证据如何推导出结论",
            "风险与反例：说明哪些条件会推翻主判断",
            "结尾说明：明确适用范围与局限",
        ]

        executive_summary = self._build_summary(overall_score, status, findings)
        metrics = {
            "char_count": document.char_count,
            "heading_count": len(headings),
            "source_count": len(source_hits),
            "number_count": len(number_hits),
            "risk_count": len(risk_hits),
        }

        return HeuristicSnapshot(
            overall_score=overall_score,
            status=status,
            passed=passed,
            executive_summary=executive_summary,
            strengths=strengths[:4],
            dimension_scores=dimension_scores,
            findings=self._dedupe_findings(findings),
            improvement_actions=self._dedupe_actions(actions),
            suggested_outline=suggested_outline,
            blocking_issues=blocking_issues,
            metrics=metrics,
        )

    def _score_structure(self, heading_count: int, summary_present: bool, conclusion_present: bool, text_length: int) -> float:
        score = 6.0
        score += min(heading_count, 6) * 1.5
        if summary_present:
            score += 3.0
        if conclusion_present:
            score += 2.0
        if text_length > 1200:
            score += 1.0
        return round(min(score, RUBRIC["structure_completeness"]["max_score"]), 1)

    def _score_evidence(
        self,
        number_count: int,
        source_count: int,
        text_length: int,
        findings: list[ReviewFinding],
        actions: list[ImprovementAction],
    ) -> float:
        score = 4.0 + min(number_count, 12) * 1.0 + min(source_count, 6) * 1.5
        if text_length > 1500 and number_count >= 4:
            score += 2.0
        if number_count < 3:
            findings.append(
                ReviewFinding(
                    severity="major",
                    title="量化支撑不足",
                    detail="报告中的数字信息过少，导致核心判断难以验证。",
                    recommendation="为每条关键论点补充具体数值、时间点、区间或同比环比对比。",
                    evidence=[f"检测到的数字信息数量：{number_count}"],
                    target_sections=["证据", "分析"],
                )
            )
            actions.append(
                ImprovementAction(
                    priority=1,
                    title="补充具体数据点",
                    action="每条核心判断至少补一条可量化数据、日期或可比较指标。",
                    target_sections=["证据", "分析"],
                )
            )
        if source_count < 2:
            findings.append(
                ReviewFinding(
                    severity="major",
                    title="来源可追溯性偏弱",
                    detail="对于研究型文档而言，报告中可识别的来源标记偏少。",
                    recommendation="关键事实后补充来源、出处、机构名或数据集名称。",
                    evidence=[f"检测到的来源标记数量：{source_count}"],
                    target_sections=["证据", "参考资料"],
                )
            )
            actions.append(
                ImprovementAction(
                    priority=2,
                    title="增强来源标注",
                    action="在事实性表述后补充来源标签，确保读者可以回溯信息路径。",
                    target_sections=["证据", "参考资料"],
                )
            )
        return round(min(score, RUBRIC["evidence_traceability"]["max_score"]), 1)

    def _score_reasoning(
        self,
        causal_count: int,
        hedging_count: int,
        summary_present: bool,
        conclusion_present: bool,
        findings: list[ReviewFinding],
        actions: list[ImprovementAction],
    ) -> float:
        score = 5.0 + min(causal_count, 8) * 1.4
        if summary_present and conclusion_present:
            score += 3.0
        if hedging_count > causal_count + 4:
            score -= 3.0
            findings.append(
                ReviewFinding(
                    severity="major",
                    title="结论表述过于含糊",
                    detail="报告中的模糊表述明显多于因果解释，削弱了最终判断的清晰度。",
                    recommendation="先明确写出基准判断，再把上行与下行情景放入独立风险段落。",
                    evidence=[f"模糊表述数量：{hedging_count}", f"因果连接词数量：{causal_count}"],
                    target_sections=["摘要", "结论", "风险"],
                )
            )
            actions.append(
                ImprovementAction(
                    priority=1,
                    title="区分基准判断与不确定性",
                    action="先写一句明确的基准判断，再把不同情景风险独立列出，而不是混在每段里。",
                    target_sections=["摘要", "结论", "风险"],
                )
            )
        if causal_count < 2:
            findings.append(
                ReviewFinding(
                    severity="major",
                    title="证据到结论的推理链偏弱",
                    detail="报告更像是在罗列现象，没有清楚说明这些事实如何推导出最终判断。",
                    recommendation="补充明确的因果句式，解释每条事实为何会改变后续判断。",
                    evidence=[f"因果连接词数量：{causal_count}"],
                    target_sections=["分析", "结论"],
                )
            )
        return round(max(0.0, min(score, RUBRIC["reasoning_clarity"]["max_score"])), 1)

    def _score_risk(
        self,
        risk_count: int,
        text: str,
        findings: list[ReviewFinding],
        actions: list[ImprovementAction],
    ) -> float:
        score = 4.0 + min(risk_count, 5) * 2.0
        if risk_count < 2:
            findings.append(
                ReviewFinding(
                    severity="major",
                    title="风险揭示不足",
                    detail="报告对反向情景、下行情景或不确定性驱动因素的讨论不够充分。",
                    recommendation="增加独立风险章节，说明哪些条件会推翻当前核心判断。",
                    evidence=[f"风险表达数量：{risk_count}"],
                    target_sections=["风险"],
                )
            )
            actions.append(
                ImprovementAction(
                    priority=2,
                    title="增加独立风险章节",
                    action="列出 2 到 4 个最可能推翻主判断的条件，并解释影响路径。",
                    target_sections=["风险"],
                )
            )
        if "风险" in text or "risk" in text.lower():
            score += 1.0
        return round(min(score, RUBRIC["risk_balance"]["max_score"]), 1)

    def _score_compliance(
        self,
        *,
        absolute_hit: bool,
        advice_hit: bool,
        disclaimer_present: bool,
        findings: list[ReviewFinding],
        actions: list[ImprovementAction],
        blocking_issues: list[str],
    ) -> float:
        score = 14.0
        if disclaimer_present:
            score += 3.0
        else:
            findings.append(
                ReviewFinding(
                    severity="minor",
                    title="缺少范围免责声明",
                    detail="文档没有明确说明适用范围、使用边界或非直接投资建议属性。",
                    recommendation="增加简短免责声明，说明用途范围和决策局限。",
                    target_sections=["页脚", "免责声明"],
                )
            )
            actions.append(
                ImprovementAction(
                    priority=3,
                    title="补充免责声明",
                    action="明确说明材料仅供参考，不构成直接投资建议。",
                    target_sections=["页脚", "免责声明"],
                )
            )
        if absolute_hit:
            score = min(score, 5.0)
            blocking_issues.append("absolute_claim")
            findings.append(
                ReviewFinding(
                    severity="critical",
                    title="存在绝对化判断",
                    detail="报告使用了不适合研究文档的绝对确定性表述。",
                    recommendation="把绝对预测改成条件式、概率式表达，并绑定可观察前提。",
                    evidence=["检测到绝对化表述。"],
                    target_sections=["摘要", "结论"],
                )
            )
            actions.append(
                ImprovementAction(
                    priority=1,
                    title="去除绝对化预测用语",
                    action="把确定性表达改为条件判断，并明确对应的前提假设。",
                    target_sections=["摘要", "结论"],
                )
            )
        if advice_hit:
            score = min(score, 4.0)
            blocking_issues.append("direct_investment_advice")
            findings.append(
                ReviewFinding(
                    severity="critical",
                    title="检测到直接投资建议",
                    detail="报告中出现了明确的买卖或仓位建议，不符合客观评审文档要求。",
                    recommendation="将直接指令改写为情景分析、影响因素或决策参考点。",
                    evidence=["检测到直接投资建议用语。"],
                    target_sections=["摘要", "结论"],
                )
            )
            actions.append(
                ImprovementAction(
                    priority=1,
                    title="去除直接买卖指令",
                    action="把命令式建议改成情景分析或决策因素说明。",
                    target_sections=["摘要", "结论"],
                )
            )
        return round(max(0.0, min(score, RUBRIC["compliance_objectivity"]["max_score"])), 1)

    def _resolve_status(self, overall_score: float, blocking_issues: list[str]) -> str:
        if blocking_issues or overall_score < config.REVISE_THRESHOLD:
            return "fail"
        if overall_score < config.PASS_THRESHOLD:
            return "revise"
        return "pass"

    def _build_summary(self, overall_score: float, status: str, findings: list[ReviewFinding]) -> str:
        if status == "pass":
            return (
                f"这份报告经过少量修改后即可复用，当前得分为 {overall_score:.1f}/100。"
                f"整体来看，结构、证据或合规层面具备较好的基础。"
            )
        top_issue = findings[0].title if findings else "若干重要问题"
        return (
            f"这份报告在复用前需要先修订，当前得分为 {overall_score:.1f}/100，"
            f"首要问题是“{top_issue}”。"
        )

    def _dedupe_findings(self, findings: list[ReviewFinding]) -> list[ReviewFinding]:
        seen: set[tuple[str, str]] = set()
        unique: list[ReviewFinding] = []
        for item in findings:
            key = (item.severity, item.title)
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        severity_rank = {"critical": 0, "major": 1, "minor": 2}
        return sorted(unique, key=lambda item: (severity_rank[item.severity], item.title))

    def _dedupe_actions(self, actions: list[ImprovementAction]) -> list[ImprovementAction]:
        seen: set[str] = set()
        unique: list[ImprovementAction] = []
        for item in actions:
            if item.title in seen:
                continue
            seen.add(item.title)
            unique.append(item)
        return sorted(unique, key=lambda item: (item.priority, item.title))
