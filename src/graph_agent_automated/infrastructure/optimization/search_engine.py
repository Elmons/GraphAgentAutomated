from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from uuid import uuid4

from graph_agent_automated.domain.enums import TaskIntent, TopologyPattern
from graph_agent_automated.domain.models import (
    ActionSpec,
    EvaluationSummary,
    ExpertBlueprint,
    OperatorBlueprint,
    PromptVariant,
    SearchConfig,
    SearchNode,
    SearchRoundTrace,
    SyntheticCase,
    SyntheticDataset,
    ToolSpec,
    WorkflowBlueprint,
)
from graph_agent_automated.domain.protocols import PromptOptimizer, ToolSelector, WorkflowEvaluator
from graph_agent_automated.infrastructure.optimization.prompt_optimizer import (
    CandidatePromptOptimizer,
)


@dataclass
class SearchResult:
    """Optimization output for orchestration and reporting layers."""

    best_blueprint: WorkflowBlueprint
    best_evaluation: EvaluationSummary
    validation_evaluation: EvaluationSummary | None
    test_evaluation: EvaluationSummary | None
    history: list[EvaluationSummary]
    round_traces: list[SearchRoundTrace]
    prompt_variants: list[PromptVariant]
    historical_tool_gain: dict[str, float]


class AFlowXSearchEngine:
    """MCTS-style search for prompt/tool/topology co-optimization with holdout control."""

    def __init__(
        self,
        evaluator: WorkflowEvaluator,
        prompt_optimizer: PromptOptimizer,
        tool_selector: ToolSelector,
        config: SearchConfig | None = None,
    ):
        self._evaluator = evaluator
        self._prompt_optimizer = prompt_optimizer
        self._tool_selector = tool_selector
        self._config = config or SearchConfig()

    def optimize(
        self,
        root_blueprint: WorkflowBlueprint,
        dataset: SyntheticDataset,
        intents: list[TaskIntent],
        tool_catalog: list[ToolSpec],
    ) -> SearchResult:
        train_cases = self._slice_cases(dataset.train_cases or dataset.cases, self._config.evaluation_budget)
        if self._config.use_holdout:
            val_cases = self._slice_cases(dataset.val_cases or dataset.cases, self._config.validation_budget)
            test_cases = self._slice_cases(dataset.test_cases or dataset.cases, self._config.test_budget)
        else:
            val_cases = train_cases
            test_cases = []

        if not train_cases:
            raise ValueError("train cases must not be empty")

        nodes: dict[str, SearchNode] = {}
        parent_map: dict[str, str | None] = {}
        eval_train_map: dict[str, EvaluationSummary] = {}
        eval_val_map: dict[str, EvaluationSummary] = {}

        history: list[EvaluationSummary] = []
        round_traces: list[SearchRoundTrace] = []
        historical_tool_gain: dict[str, float] = {}

        root_node = SearchNode(node_id=self._new_node_id(), blueprint=root_blueprint)
        nodes[root_node.node_id] = root_node
        parent_map[root_node.node_id] = None

        root_train_eval = self._evaluate(root_blueprint, train_cases, split="train")
        if self._config.use_holdout:
            root_val_eval = self._evaluate(root_blueprint, val_cases, split="val")
            history.extend([root_train_eval, root_val_eval])
        else:
            root_val_eval = root_train_eval
            history.append(root_train_eval)
        eval_train_map[root_blueprint.blueprint_id] = root_train_eval
        eval_val_map[root_blueprint.blueprint_id] = root_val_eval

        root_objective = self._objective(root_train_eval, root_blueprint)
        self._backpropagate(root_node.node_id, root_objective, nodes, parent_map)

        best_by_train_eval = root_train_eval
        best_by_train_objective = root_objective

        best_by_val_blueprint = root_blueprint
        best_by_val_eval = root_val_eval
        best_by_val_objective = self._model_selection_objective(
            train_summary=root_train_eval,
            val_summary=root_val_eval,
            blueprint=root_blueprint,
        )

        no_improve_rounds = 0
        trace_idx = 0

        for round_idx in range(1, self._config.rounds + 1):
            selected = self._select(nodes)
            selected_train_eval = eval_train_map[selected.blueprint.blueprint_id]
            selected_train_objective = self._objective(selected_train_eval, selected.blueprint)

            round_best_before = best_by_val_objective

            for expansion_idx in range(self._config.expansions_per_round):
                candidate_blueprint, mutation = self._mutate(
                    parent_blueprint=selected.blueprint,
                    parent_eval=selected_train_eval,
                    intents=intents,
                    tool_catalog=tool_catalog,
                    historical_tool_gain=historical_tool_gain,
                    round_idx=round_idx,
                    expansion_idx=expansion_idx,
                )
                candidate_blueprint.parent_id = selected.blueprint.blueprint_id
                candidate_blueprint.mutation_trace.append(mutation)

                child = SearchNode(
                    node_id=self._new_node_id(),
                    blueprint=candidate_blueprint,
                    parent_id=selected.node_id,
                )
                nodes[child.node_id] = child
                parent_map[child.node_id] = selected.node_id
                selected.children_ids.append(child.node_id)

                child_train_eval = self._evaluate(candidate_blueprint, train_cases, split="train")
                if self._config.use_holdout:
                    child_val_eval = self._evaluate(candidate_blueprint, val_cases, split="val")
                    history.extend([child_train_eval, child_val_eval])
                else:
                    child_val_eval = child_train_eval
                    history.append(child_train_eval)
                eval_train_map[candidate_blueprint.blueprint_id] = child_train_eval
                eval_val_map[candidate_blueprint.blueprint_id] = child_val_eval

                child_train_objective = self._objective(child_train_eval, candidate_blueprint)
                child_val_objective = self._model_selection_objective(
                    train_summary=child_train_eval,
                    val_summary=child_val_eval,
                    blueprint=candidate_blueprint,
                )
                self._backpropagate(child.node_id, child_train_objective, nodes, parent_map)

                if child_train_objective > best_by_train_objective:
                    best_by_train_objective = child_train_objective
                    best_by_train_eval = child_train_eval

                if child_val_objective > best_by_val_objective:
                    best_by_val_objective = child_val_objective
                    best_by_val_blueprint = candidate_blueprint
                    best_by_val_eval = child_val_eval

                improvement = child_train_objective - selected_train_objective
                self._update_tool_gain(
                    mutation=mutation,
                    improvement=improvement,
                    historical_tool_gain=historical_tool_gain,
                )

                regret = max(0.0, best_by_val_objective - child_val_objective)
                generalization_gap = (
                    self._generalization_gap(child_train_eval, child_val_eval)
                    if self._config.use_holdout
                    else 0.0
                )
                trace_idx += 1
                round_traces.append(
                    SearchRoundTrace(
                        round_num=trace_idx,
                        selected_node_id=selected.node_id,
                        selected_blueprint_id=selected.blueprint.blueprint_id,
                        mutation=mutation,
                        train_objective=child_train_objective,
                        val_objective=child_val_objective,
                        best_train_objective=best_by_train_objective,
                        best_val_objective=best_by_val_objective,
                        improvement=improvement,
                        regret=regret,
                        uncertainty=self._uncertainty(child_val_eval),
                        generalization_gap=generalization_gap,
                    )
                )

            round_improvement = best_by_val_objective - round_best_before
            if round_improvement < self._config.min_improvement:
                no_improve_rounds += 1
            else:
                no_improve_rounds = 0

            if no_improve_rounds >= self._config.patience:
                break

        validation_eval = best_by_val_eval if self._config.use_holdout else None
        test_eval: EvaluationSummary | None = None
        if self._config.use_holdout and test_cases:
            test_eval = self._evaluate(best_by_val_blueprint, test_cases, split="test")
            history.append(test_eval)

        prompt_variants = self._extract_prompt_variants()
        return SearchResult(
            best_blueprint=best_by_val_blueprint,
            best_evaluation=best_by_train_eval,
            validation_evaluation=validation_eval,
            test_evaluation=test_eval,
            history=history,
            round_traces=round_traces,
            prompt_variants=prompt_variants,
            historical_tool_gain=historical_tool_gain,
        )

    def _extract_prompt_variants(self) -> list[PromptVariant]:
        registry = getattr(self._prompt_optimizer, "registry", None)
        if registry is None:
            return []
        variants = getattr(registry, "list", None)
        if callable(variants):
            raw = variants()
            if isinstance(raw, list):
                return [item for item in raw if isinstance(item, PromptVariant)]
        return []

    def _select(self, nodes: dict[str, SearchNode]) -> SearchNode:
        total_visits = sum(node.visits for node in nodes.values()) + 1
        best_node: SearchNode | None = None
        best_ucb = -1e9

        for node in nodes.values():
            if node.visits == 0:
                return node
            exploration = self._config.exploration_weight * math.sqrt(
                math.log(total_visits) / max(node.visits, 1)
            )
            novelty = self._config.novelty_weight * self._novelty_bonus(node)
            score = node.mean_value + exploration + novelty
            if score > best_ucb:
                best_ucb = score
                best_node = node

        if best_node is None:
            raise RuntimeError("select failed on empty node set")
        return best_node

    def _mutate(
        self,
        parent_blueprint: WorkflowBlueprint,
        parent_eval: EvaluationSummary,
        intents: list[TaskIntent],
        tool_catalog: list[ToolSpec],
        historical_tool_gain: dict[str, float],
        round_idx: int,
        expansion_idx: int,
    ) -> tuple[WorkflowBlueprint, str]:
        modes: list[str] = []
        if self._config.enable_prompt_mutation:
            modes.append("prompt")
        if self._config.enable_tool_mutation and tool_catalog:
            modes.append("tool")
        if self._config.enable_topology_mutation:
            modes.append("topology")

        if not modes:
            candidate = copy.deepcopy(parent_blueprint)
            candidate.blueprint_id = self._new_blueprint_id()
            return candidate, "mutation:disabled"

        mode = modes[(round_idx + expansion_idx) % len(modes)]
        if mode == "prompt":
            return self._mutate_prompt(parent_blueprint, parent_eval)
        if mode == "tool":
            gain_source = historical_tool_gain if self._config.enable_tool_historical_gain else {}
            return self._mutate_tools(parent_blueprint, intents, tool_catalog, gain_source)
        return self._mutate_topology(parent_blueprint)

    def _mutate_prompt(
        self,
        parent_blueprint: WorkflowBlueprint,
        parent_eval: EvaluationSummary,
    ) -> tuple[WorkflowBlueprint, str]:
        candidate = copy.deepcopy(parent_blueprint)
        if not candidate.experts or not candidate.experts[0].operators:
            candidate.blueprint_id = self._new_blueprint_id()
            return candidate, "prompt:skip-empty"

        failures = [result for result in parent_eval.case_results if result.score < 0.6]
        first_operator = candidate.experts[0].operators[0]

        if isinstance(self._prompt_optimizer, CandidatePromptOptimizer):
            first_operator.instruction = self._prompt_optimizer.optimize(
                prompt=first_operator.instruction,
                failures=failures,
                task_desc=candidate.task_desc,
            )
        else:
            first_operator.instruction = self._prompt_optimizer.optimize(
                first_operator.instruction,
                failures,
                candidate.task_desc,
            )

        candidate.blueprint_id = self._new_blueprint_id()
        return candidate, f"prompt:optimize({first_operator.name})"

    def _mutate_tools(
        self,
        parent_blueprint: WorkflowBlueprint,
        intents: list[TaskIntent],
        tool_catalog: list[ToolSpec],
        historical_tool_gain: dict[str, float],
    ) -> tuple[WorkflowBlueprint, str]:
        candidate = copy.deepcopy(parent_blueprint)

        ranked_tools = self._tool_selector.rank(
            task_desc=candidate.task_desc,
            intents=[intent.value for intent in intents],
            catalog=tool_catalog,
            top_k=max(1, len(candidate.tools) + 1),
            historical_gain=historical_tool_gain,
        )

        existing = {tool.name for tool in candidate.tools}
        new_tool = next((tool for tool in ranked_tools if tool.name not in existing), None)
        if new_tool is not None:
            candidate.tools.append(new_tool)
            action_name = f"use_{new_tool.name.lower()}"
            candidate.actions.append(
                ActionSpec(
                    name=action_name,
                    description=f"Use {new_tool.name} to ground graph reasoning.",
                    tools=[new_tool.name],
                )
            )
            for expert in candidate.experts:
                for operator in expert.operators:
                    if action_name not in operator.actions:
                        operator.actions.append(action_name)
                        break
            candidate.blueprint_id = self._new_blueprint_id()
            return candidate, f"tool:add({new_tool.name})"

        removable = [action for action in candidate.actions if action.name not in candidate.leader_actions]
        if removable:
            removed = removable[-1]
            candidate.actions = [action for action in candidate.actions if action.name != removed.name]
            for expert in candidate.experts:
                for operator in expert.operators:
                    operator.actions = [name for name in operator.actions if name != removed.name]
            candidate.blueprint_id = self._new_blueprint_id()
            return candidate, f"tool:remove({removed.name})"

        candidate.blueprint_id = self._new_blueprint_id()
        return candidate, "tool:noop"

    def _mutate_topology(self, parent_blueprint: WorkflowBlueprint) -> tuple[WorkflowBlueprint, str]:
        candidate = copy.deepcopy(parent_blueprint)
        order = [
            TopologyPattern.LINEAR,
            TopologyPattern.PLANNER_WORKER_REVIEWER,
            TopologyPattern.ROUTER_PARALLEL,
        ]
        next_idx = (order.index(candidate.topology) + 1) % len(order)
        candidate.topology = order[next_idx]

        for expert in candidate.experts:
            seed_actions = expert.operators[0].actions if expert.operators else []
            expert.operators = build_topology_operators(candidate.topology, seed_actions)

        candidate.blueprint_id = self._new_blueprint_id()
        return candidate, f"topology:switch({candidate.topology.value})"

    def _evaluate(
        self,
        blueprint: WorkflowBlueprint,
        cases: list[SyntheticCase],
        split: str,
    ) -> EvaluationSummary:
        return self._evaluator.evaluate(blueprint, cases, split=split)

    def _objective(self, summary: EvaluationSummary, blueprint: WorkflowBlueprint) -> float:
        complexity = len(blueprint.actions) + sum(len(expert.operators) for expert in blueprint.experts)
        confidence = self._mean_confidence(summary)
        uncertainty = self._uncertainty(summary)
        return (
            summary.mean_score
            + self._config.confidence_weight * confidence
            - self._config.latency_penalty * (summary.mean_latency_ms / 1000.0)
            - self._config.cost_penalty * summary.mean_token_cost
            - self._config.complexity_penalty * (complexity / 10.0)
            - self._config.uncertainty_penalty * uncertainty
        )

    def _model_selection_objective(
        self,
        train_summary: EvaluationSummary,
        val_summary: EvaluationSummary,
        blueprint: WorkflowBlueprint,
    ) -> float:
        base = self._objective(val_summary, blueprint)
        if not self._config.use_holdout:
            return base
        gap = self._generalization_gap(train_summary, val_summary)
        return base - self._config.generalization_penalty * gap

    def _uncertainty(self, summary: EvaluationSummary) -> float:
        agreement_gap = 1.0 - max(0.0, min(1.0, summary.judge_agreement))
        score_spread = max(0.0, summary.score_std)
        return agreement_gap + score_spread

    def _generalization_gap(
        self,
        train_summary: EvaluationSummary,
        val_summary: EvaluationSummary,
    ) -> float:
        return max(0.0, train_summary.mean_score - val_summary.mean_score)

    def _mean_confidence(self, summary: EvaluationSummary) -> float:
        if not summary.case_results:
            return 0.0
        confidences = [result.confidence for result in summary.case_results]
        return sum(confidences) / len(confidences)

    def _novelty_bonus(self, node: SearchNode) -> float:
        unique_mutations = len(set(node.blueprint.mutation_trace))
        topology_bonus = {
            TopologyPattern.LINEAR: 0.1,
            TopologyPattern.PLANNER_WORKER_REVIEWER: 0.4,
            TopologyPattern.ROUTER_PARALLEL: 0.6,
        }[node.blueprint.topology]
        return unique_mutations + topology_bonus

    def _backpropagate(
        self,
        node_id: str,
        reward: float,
        nodes: dict[str, SearchNode],
        parent_map: dict[str, str | None],
    ) -> None:
        cursor: str | None = node_id
        while cursor is not None:
            node = nodes[cursor]
            node.visits += 1
            node.value_sum += reward
            node.best_score = max(node.best_score, reward)
            cursor = parent_map[cursor]

    def _update_tool_gain(
        self,
        mutation: str,
        improvement: float,
        historical_tool_gain: dict[str, float],
    ) -> None:
        if not self._config.enable_tool_historical_gain:
            return
        if not mutation.startswith("tool:add("):
            return
        tool_name = mutation[len("tool:add(") : -1]
        old = historical_tool_gain.get(tool_name, 0.0)
        # Exponential moving average.
        historical_tool_gain[tool_name] = 0.7 * old + 0.3 * improvement

    def _slice_cases(self, cases: list[SyntheticCase], budget: int) -> list[SyntheticCase]:
        return list(cases[: max(1, budget)])

    def _new_node_id(self) -> str:
        return f"node-{uuid4().hex[:10]}"

    def _new_blueprint_id(self) -> str:
        return f"bp-{uuid4().hex[:12]}"


def build_initial_blueprint(
    app_name: str,
    task_desc: str,
    selected_tools: list[ToolSpec],
    topology: TopologyPattern = TopologyPattern.PLANNER_WORKER_REVIEWER,
) -> WorkflowBlueprint:
    actions: list[ActionSpec] = []
    leader_actions: list[str] = []

    for idx, tool in enumerate(selected_tools):
        action_name = f"use_{tool.name.lower()}"
        actions.append(
            ActionSpec(
                name=action_name,
                description=f"Use {tool.name} during graph reasoning.",
                tools=[tool.name],
            )
        )
        if idx < 2:
            leader_actions.append(action_name)

    operators = build_topology_operators(topology, leader_actions)
    expert = ExpertBlueprint(
        name="GraphTaskExpert",
        description=(
            "General graph task expert with planning, execution and verification capabilities."
        ),
        operators=operators,
    )

    return WorkflowBlueprint(
        blueprint_id=f"bp-{uuid4().hex[:12]}",
        app_name=app_name,
        task_desc=task_desc,
        topology=topology,
        tools=selected_tools,
        actions=actions,
        experts=[expert],
        leader_actions=leader_actions,
    )


def build_topology_operators(
    topology: TopologyPattern,
    seed_actions: list[str],
) -> list[OperatorBlueprint]:
    if topology == TopologyPattern.LINEAR:
        return [
            OperatorBlueprint(
                name="linear_worker",
                instruction=(
                    "Solve the graph task with minimal steps and explicit evidence references."
                ),
                output_schema="answer: concise factual answer",
                actions=seed_actions,
            )
        ]

    if topology == TopologyPattern.PLANNER_WORKER_REVIEWER:
        return [
            OperatorBlueprint(
                name="planner",
                instruction="Plan required graph operations and tools before execution.",
                output_schema="plan: ordered graph actions",
                actions=seed_actions,
            ),
            OperatorBlueprint(
                name="worker",
                instruction="Execute the plan and collect graph evidence.",
                output_schema="draft_answer: evidence-backed result",
                actions=seed_actions,
            ),
            OperatorBlueprint(
                name="reviewer",
                instruction="Audit draft answer and patch unsupported claims.",
                output_schema="final_answer: corrected result",
                actions=seed_actions,
            ),
        ]

    return [
        OperatorBlueprint(
            name="router",
            instruction="Route request by intent and required capability.",
            output_schema="route: chosen branch",
            actions=seed_actions,
        ),
        OperatorBlueprint(
            name="worker_query",
            instruction="Process query branch with strict schema grounding.",
            output_schema="query_result: branch output",
            actions=seed_actions,
        ),
        OperatorBlueprint(
            name="worker_analysis",
            instruction="Process analytics branch with algorithm rationale.",
            output_schema="analysis_result: branch output",
            actions=seed_actions,
        ),
        OperatorBlueprint(
            name="synthesizer",
            instruction="Merge branch outputs and produce verified final answer.",
            output_schema="final_answer: merged result",
            actions=seed_actions,
        ),
    ]


def infer_intents(cases: list[SyntheticCase]) -> list[TaskIntent]:
    counts: dict[TaskIntent, int] = {}
    for case in cases:
        counts[case.intent] = counts.get(case.intent, 0) + 1

    if not counts:
        return [TaskIntent.QUERY]

    sorted_items = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return [item[0] for item in sorted_items[:2]]
