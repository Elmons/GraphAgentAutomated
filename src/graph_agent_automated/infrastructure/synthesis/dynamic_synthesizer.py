from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from graph_agent_automated.domain.enums import Difficulty, TaskIntent
from graph_agent_automated.domain.models import SyntheticCase, SyntheticDataset
from graph_agent_automated.domain.protocols import DatasetSynthesizer, RuntimeAdapter


@dataclass(frozen=True)
class SeedTemplate:
    intent: TaskIntent
    question_template: str


class DynamicDatasetSynthesizer(DatasetSynthesizer):
    """Generate a compact, dynamic dataset from task, schema, and intent hints."""

    def __init__(
        self,
        runtime: RuntimeAdapter,
        answer_resolver: Callable[[str], str] | None = None,
        random_seed: int = 7,
        train_ratio: float = 0.6,
        val_ratio: float = 0.2,
        test_ratio: float = 0.2,
    ):
        self._runtime = runtime
        self._answer_resolver = answer_resolver or (lambda _: "UNKNOWN")
        self._random = random.Random(random_seed)
        self._train_ratio = train_ratio
        self._val_ratio = val_ratio
        self._test_ratio = test_ratio

        ratio_sum = train_ratio + val_ratio + test_ratio
        if abs(ratio_sum - 1.0) > 1e-6:
            raise ValueError(
                f"dataset split ratios must sum to 1.0, got {train_ratio}+{val_ratio}+{test_ratio}"
            )

    def synthesize(self, task_desc: str, dataset_name: str, size: int) -> SyntheticDataset:
        bounded_size = max(6, min(size, 30))
        schema = self._runtime.fetch_schema_snapshot()
        intents = self._infer_intents(task_desc)
        labels = self._get_list(schema, "labels", fallback=["Node"])
        relations = self._get_list(schema, "relations", fallback=["RELATED_TO"])

        templates = self._build_templates(intents)
        questions = self._render_questions(templates, labels, relations, target=bounded_size * 2)
        questions.extend(self._hard_negative_questions(questions, labels, relations))
        questions = self._deduplicate(questions)

        cases: list[SyntheticCase] = []
        levels = [Difficulty.L1, Difficulty.L2, Difficulty.L3, Difficulty.L4]
        for idx, question in enumerate(questions[:bounded_size]):
            intent = intents[idx % len(intents)]
            verifier = self._answer_resolver(question)
            cases.append(
                SyntheticCase(
                    case_id=f"{dataset_name}-{idx + 1}",
                    question=question,
                    verifier=verifier,
                    intent=intent,
                    difficulty=levels[idx % len(levels)],
                    metadata={
                        "generated_by": "dynamic_synthesizer",
                        "lineage": {
                            "seed_index": idx,
                            "intent": intent.value,
                            "difficulty": levels[idx % len(levels)].value,
                            "is_hard_negative": "cannot be inferred" in question.lower(),
                        },
                    },
                )
            )

        train_cases, val_cases, test_cases = self._split_cases(cases)
        synthesis_report = {
            "requested_size": size,
            "final_size": len(cases),
            "intents": [intent.value for intent in intents],
            "labels_sampled": labels,
            "relations_sampled": relations,
            "hard_negative_count": len(
                [
                    case
                    for case in cases
                    if case.metadata.get("lineage", {}).get("is_hard_negative", False)
                ]
            ),
            "split_sizes": {
                "train": len(train_cases),
                "val": len(val_cases),
                "test": len(test_cases),
            },
        }

        return SyntheticDataset(
            name=dataset_name,
            task_desc=task_desc,
            cases=cases,
            train_cases=train_cases,
            val_cases=val_cases,
            test_cases=test_cases,
            schema_snapshot=schema,
            synthesis_report=synthesis_report,
        )

    def _infer_intents(self, task_desc: str) -> list[TaskIntent]:
        text = task_desc.lower()
        intents: list[TaskIntent] = []

        def include(intent: TaskIntent, words: Sequence[str]) -> None:
            if any(word in text for word in words):
                intents.append(intent)

        include(TaskIntent.QUERY, ["query", "查询", "cypher", "查找"])
        include(TaskIntent.ANALYTICS, ["analytics", "analysis", "算法", "rank", "社区"])
        include(TaskIntent.MODELING, ["model", "schema", "建模", "实体", "关系"])
        include(TaskIntent.IMPORT, ["import", "导入", "etl", "ingest"])
        include(TaskIntent.QA, ["qa", "问答", "summarize", "explain", "介绍"])

        if not intents:
            intents = [TaskIntent.QUERY, TaskIntent.ANALYTICS]

        return intents[:2]

    def _build_templates(self, intents: Sequence[TaskIntent]) -> list[SeedTemplate]:
        template_map: dict[TaskIntent, list[str]] = {
            TaskIntent.QUERY: [
                "Find {label} entities linked by {relation} and return key properties.",
                "Which {label} nodes satisfy path constraints through {relation}?",
            ],
            TaskIntent.ANALYTICS: [
                "Run graph analytics on {label} using {relation} and explain top findings.",
                "Identify anomalous subgraphs in {label} connected by {relation}.",
            ],
            TaskIntent.MODELING: [
                "Design schema evolution for {label} and relationship {relation}.",
                "Propose constraints for {label} connected via {relation}.",
            ],
            TaskIntent.IMPORT: [
                "Create an ingestion plan for {label} and map edges via {relation}.",
                "Define pre-import validation for {label} with {relation}.",
            ],
            TaskIntent.QA: [
                "Explain the semantic meaning of {label} and {relation} in this graph.",
                "Provide concise domain summary centered on {label}/{relation}.",
            ],
        }

        seeds: list[SeedTemplate] = []
        for intent in intents:
            for template in template_map[intent]:
                seeds.append(SeedTemplate(intent=intent, question_template=template))
        return seeds

    def _render_questions(
        self,
        templates: Sequence[SeedTemplate],
        labels: Sequence[str],
        relations: Sequence[str],
        target: int,
    ) -> list[str]:
        results: list[str] = []
        while len(results) < target:
            seed = self._random.choice(list(templates))
            label = self._random.choice(list(labels))
            relation = self._random.choice(list(relations))
            question = seed.question_template.format(label=label, relation=relation)
            results.append(question)
            results.extend(self._paraphrase(question))
        return results[:target]

    def _paraphrase(self, question: str) -> list[str]:
        candidates = [
            question.replace("Find", "Locate"),
            question.replace("Which", "List"),
            question.replace("Explain", "Summarize"),
        ]
        return [candidate for candidate in candidates if candidate != question]

    def _hard_negative_questions(
        self,
        questions: Sequence[str],
        labels: Sequence[str],
        relations: Sequence[str],
    ) -> list[str]:
        if not questions:
            return []

        negatives: list[str] = []
        sample_size = min(max(2, len(questions) // 4), len(questions))
        sampled = self._random.sample(list(questions), sample_size)
        for idx, question in enumerate(sampled):
            label = labels[idx % len(labels)]
            relation = relations[idx % len(relations)]
            negatives.append(
                f"{question} Also explain why the answer cannot be inferred "
                f"if {label} has no edge of type {relation}."
            )
        return negatives

    def _deduplicate(self, questions: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for question in questions:
            key = " ".join(question.lower().split())
            if key in seen:
                continue
            seen.add(key)
            output.append(question)
        return output

    def _get_list(self, payload: dict[str, object], key: str, fallback: list[str]) -> list[str]:
        value = payload.get(key)
        if isinstance(value, list):
            return [str(item) for item in value if str(item)]
        return fallback

    def _split_cases(
        self,
        cases: list[SyntheticCase],
    ) -> tuple[list[SyntheticCase], list[SyntheticCase], list[SyntheticCase]]:
        shuffled = list(cases)
        self._random.shuffle(shuffled)

        total = len(shuffled)
        train_end = int(total * self._train_ratio)
        val_end = train_end + int(total * self._val_ratio)

        train_cases = shuffled[:train_end]
        val_cases = shuffled[train_end:val_end]
        test_cases = shuffled[val_end:]

        if not train_cases and shuffled:
            train_cases = [shuffled[0]]
        if not val_cases and len(shuffled) > 1:
            val_cases = [shuffled[1]]
            test_cases = [case for case in test_cases if case.case_id != shuffled[1].case_id]
        if not test_cases and len(shuffled) > 2:
            test_cases = [shuffled[2]]
            train_cases = [case for case in train_cases if case.case_id != shuffled[2].case_id]

        return train_cases, val_cases, test_cases
