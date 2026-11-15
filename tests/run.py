#!/usr/bin/env python3
"""Tests for bin/stelow-host.

Run: python3 tests/run.py

Every test names the bug it catches. Live Multica calls are replaced by an
in-process double, so the suite never touches a workspace or the network; the
commands the tool *would* run are recorded and asserted instead.
"""

import hashlib
import importlib.machinery
import importlib.util
import json
import re
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LOADER = importlib.machinery.SourceFileLoader("stelow_host", str(REPO / "bin" / "stelow-host"))
SPEC = importlib.util.spec_from_loader("stelow_host", LOADER)
HOST = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(HOST)
REAL_MULTICA = HOST.Multica  # setUp() swaps HOST.Multica for the fake; keep the real one

INTENTS = {
    "new-product": ["triage", "select", "setup", "context", "shape", "critique", "gate", "scope",
                    "interface", "int-gate", "selection", "architecture", "planning", "plan-gate",
                    "execution", "verification", "diff-gate", "audit"],
    "feature": ["triage", "select", "setup", "context", "shape", "critique", "gate", "scope",
                "interface", "int-gate", "selection", "architecture", "planning", "plan-gate",
                "execution", "verification", "diff-gate", "audit"],
    "bugfix": ["triage", "select", "setup", "context", "shape", "critique", "gate",
               "execution", "verification", "audit"],
    "refactor": ["triage", "select", "setup", "context", "planning", "plan-gate",
                 "execution", "verification", "audit"],
    "investigate": ["triage", "select", "setup", "context", "audit"],
}


STAGE_CATALOG = {
    "version": 1,
    "stages": [
        {"id": "triage", "skill": "stelow-workflow-orchestrator"},
        {"id": "select", "skill": "stelow-workflow-orchestrator"},
        {"id": "setup", "skill": "stelow-workflow-orchestrator"},
        {"id": "context", "skill": "stelow-workflow-orchestrator"},
        {"id": "shape", "skill": "stelow-workflow-shape-up"},
        {"id": "critique", "skill": "stelow-workflow-plan-critique"},
        {"id": "gate", "skill": "stelow-workflow-orchestrator", "requires_approval": True},
        {"id": "scope", "skill": "stelow-product-scope-mapping"},
        {"id": "interface", "skill": "stelow-workflow-interface-contrast"},
        {"id": "int-gate", "skill": "stelow-workflow-orchestrator", "requires_approval": True},
        {"id": "selection", "skill": "stelow-workflow-orchestrator"},
        {"id": "architecture", "skill": "stelow-workflow-orchestrator"},
        {"id": "planning", "skill": "stelow-workflow-tech-planning"},
        {"id": "plan-gate", "skill": "stelow-workflow-orchestrator", "requires_approval": True},
        {"id": "execution", "skill": "stelow-workflow-scope-executor"},
        {"id": "verification", "skill": "stelow-workflow-testing-execution"},
        {"id": "diff-gate", "skill": "stelow-workflow-orchestrator", "requires_approval": True},
        {"id": "audit", "skill": "stelow-workflow-execution-critique"},
    ],
}


def transitions_md(intents=INTENTS):
    """The mirror upstream generates: a forward chain plus the four gate rejects."""
    edges = {}
    for route in intents.values():
        for earlier, later in zip(route, route[1:]):
            edges.setdefault(earlier, {"next": [], "reject": []})["next"].append(later)
    for gate, target in (("gate", "shape"), ("int-gate", "interface"),
                         ("plan-gate", "planning"), ("diff-gate", "execution")):
        edges.setdefault(gate, {"next": [], "reject": []})["reject"].append(target)
    lines = []
    for stage, rows in edges.items():
        lines += ["### " + stage, "", "```",
                  "next:      " + (", ".join(rows["next"]) or "(none)"),
                  "reject:    " + (", ".join(rows["reject"]) or "(none)"),
                  "```", ""]
    return "\n".join(lines)


def stages_yaml(intents=INTENTS):
    lines = ["version: 2", "routes:", "  intents:"]
    for name, stages in intents.items():
        lines.append("    %s: [%s]" % (name, ", ".join(stages)))
    lines += ["  # a comment inside the block must not end it", "  review_modes:", "    Auto:",
              "      skipped: [plan-gate, diff-gate]"]
    return "\n".join(lines) + "\n"


class FakeMultica:
    """Records the calls the tool would make, against dict state."""

    _rows = staticmethod(HOST.Multica._rows)
    _one = staticmethod(HOST.Multica._one)
    last = None

    def __init__(self, host):
        self.calls = []
        self.state = {"skills": {}, "agents": {}, "agent_skills": {}, "workflows": {}, "projects": {}}
        self.seq = 0
        FakeMultica.last = self

    def _next(self, prefix):
        self.seq += 1
        return "%s-gen%d" % (prefix, self.seq)

    def argv(self, args):
        return ["multica"] + args

    def run(self, args, can_fail=False):
        self.calls.append(list(args))
        args = list(args)
        if args[:2] == ["runtime", "list"]:
            return 0, json.dumps([{
                "id": self.state.get("runtime_id", "rt-test"),
                "name": "test-runtime",
                "status": self.state.get("runtime_status", "online"),
            }]), ""
        if args[:2] == ["skill", "list"]:
            return 0, json.dumps([{"id": v, "name": k} for k, v in self.state["skills"].items()]), ""
        if args[:2] == ["skill", "import"]:
            url = args[args.index("--url") + 1]
            name = url.rstrip("/").split("/")[-1]
            if name not in self.state["skills"]:
                self.state["skills"][name] = self._next("skill")
            return 0, json.dumps({"id": self.state["skills"][name], "name": name}), ""
        if args[:2] == ["skill", "refresh"]:
            return 0, json.dumps({"id": args[2]}), ""
        if args[:2] == ["agent", "list"]:
            return 0, json.dumps([{"id": v, "name": k} for k, v in self.state["agents"].items()]), ""
        if args[:2] == ["agent", "create"]:
            name = args[args.index("--name") + 1]
            agent_id = self._next("agent")
            self.state["agents"][name] = agent_id
            self.state["agent_skills"][name] = []
            return 0, json.dumps({"id": agent_id, "name": name}), ""
        if args[:2] == ["agent", "update"]:
            if args[2] not in self.state["agents"].values():
                return 1, "", "agent not found"
            return 0, json.dumps({"id": args[2]}), ""
        if args[:3] == ["agent", "skills", "list"]:
            for name, agent_id in self.state["agents"].items():
                if agent_id == args[3]:
                    ids = self.state["agent_skills"][name]
                    return 0, json.dumps([{"id": i, "name": i} for i in ids]), ""
            return 1, "", "agent not found"
        if args[:3] == ["agent", "skills", "set"]:
            for name, agent_id in self.state["agents"].items():
                if agent_id == args[3]:
                    self.state["agent_skills"][name] = [s for s in args[args.index("--skill-ids") + 1].split(",") if s]
                    return 0, json.dumps({"agent_id": agent_id}), ""
            return 1, "", "agent not found"
        if args[:2] == ["workflow", "list"]:
            return 0, json.dumps([{"id": k, "name": k} for k in self.state["workflows"]]), ""
        if args[:2] == ["workflow", "get"]:
            if args[2] not in self.state["workflows"]:
                return 1, "", "workflow not found"
            return 0, json.dumps({"name": args[2], "steps": self.state["workflows"][args[2]]}), ""
        if args[:2] in (["workflow", "create"], ["workflow", "update"]):
            name = args[args.index("--name") + 1] if args[0] == "workflow" and args[1] == "create" else args[2]
            steps = json.loads(Path(args[args.index("--steps-file") + 1]).read_text())
            if args[1] == "create":
                live = {}
            else:
                live = {s["status_key"]: s for s in self.state["workflows"][name]}
            normalized = []
            for step in steps:
                key = step.get("status_key") or HOST.re.sub(r"[^a-z0-9]+", "_", step["new_status"]["name"].lower()).strip("_")
                entry = {"status_key": key, "name": live.get(key, {}).get("name", key)}
                for field in ("handler", "instructions", "next_status_key", "back_status_key"):
                    if field in step:
                        entry[field] = step[field]
                normalized.append(entry)
            self.state["workflows"][name] = normalized
            return 0, json.dumps({"name": name, "steps": normalized}), ""
        if args[:3] == ["project", "workflow", "get"]:
            return 0, json.dumps({"project_id": args[3], "workflow": self.state["projects"].get(args[3], "default")}), ""
        if args[:3] == ["project", "workflow", "set"]:
            self.state["projects"][args[3]] = args[4]
            return 0, json.dumps({"ok": True}), ""
        raise AssertionError("unexpected command: %s" % args)

    def json(self, args):
        code, out, err = self.run(args)
        if code != 0:
            raise HOST.Fail("fake: %s" % err, code=1)
        return json.loads(out)

    def runtimes(self):
        return self._rows(self.json(["runtime", "list"]), "runtime list")

    def skills(self):
        return dict(self.state["skills"])

    def agents(self):
        return dict(self.state["agents"])

    def agent_skill_ids(self, agent_id):
        for name, value in self.state["agents"].items():
            if value == agent_id:
                return list(self.state["agent_skills"][name])
        return []

    def workflows(self):
        return {k: k for k in self.state["workflows"]}

    def workflow(self, name):
        if name not in self.state["workflows"]:
            return None
        return {"name": name, "steps": self.state["workflows"][name]}

    def project_workflow(self, project_id):
        return {"project_id": project_id, "workflow": self.state["projects"].get(project_id, "default")}


class HostCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="stelow-host-test-"))
        for name in ("config", "agents", "stages"):
            shutil.copytree(REPO / name, self.tmp / name)
        (self.tmp / ".stelow-cache").mkdir()
        self.write_stages()
        HOST.set_root(self.tmp)
        self.original = HOST.Multica
        self.fake = FakeMultica(None)
        HOST.Multica = lambda host: self.fake
        self.host = HOST.load_host(self.tmp / "config" / "host.json")
        self.host["multica"]["runtime_id"] = "rt-test"
        self.host["multica"]["workspace_id"] = "ws-test"
        self.groups = HOST.load_groups(self.tmp / "config" / "columns.json")
        self.lock = HOST.ensure_stages(self.host)

    def tearDown(self):
        HOST.Multica = self.original
        HOST.set_root(REPO)
        shutil.rmtree(self.tmp, ignore_errors=True)

    # helpers -----------------------------------------------------------

    def write_stages(self, intents=INTENTS, catalog=STAGE_CATALOG):
        text = stages_yaml(intents)
        cat_text = json.dumps(catalog)
        tr_text = transitions_md()
        cache = self.tmp / ".stelow-cache"
        (cache / "stages.yaml").write_text(text, encoding="utf-8")
        (cache / "stage-catalog.json").write_text(cat_text, encoding="utf-8")
        (cache / "transitions.md").write_text(tr_text, encoding="utf-8")
        (self.tmp / "stelow.lock.json").write_text(json.dumps({
            "repo": self.host_repo(),
            "ref": self.host_ref(),
            "stages_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "catalog_sha256": hashlib.sha256(cat_text.encode()).hexdigest(),
            "transitions_sha256": hashlib.sha256(tr_text.encode()).hexdigest(),
            "owners": {s["id"]: s["skill"] for s in catalog["stages"] if s.get("skill")},
            "rejects": {s: [target] for s, target in (
                ("gate", "shape"), ("int-gate", "interface"), ("plan-gate", "planning"),
                ("diff-gate", "execution"), ("audit", "execution"),
            )},
        }), encoding="utf-8")

    def host_repo(self):
        return json.loads((self.tmp / "config" / "host.json").read_text())["stelow"]["repo"]

    def host_ref(self):
        return json.loads((self.tmp / "config" / "host.json").read_text())["stelow"]["ref"]

    def args(self, intent="feature", gates="human", project="proj-1", migrate=False, refresh=False, offline=False):
        return types.SimpleNamespace(intent=intent, gates=gates, project=project,
                                     migrate=migrate, refresh_skills=refresh, json=False,
                                     offline=offline)

    def apply(self, **kwargs):
        return HOST.cmd_apply(self.host, self.args(**kwargs), self.groups, self.lock)

    def fp(self):
        return self.fake


class TestMapping(HostCase):
    def test_every_stage_in_every_intent_is_mapped(self):
        """A stage added to stages.yaml with no column would be silently dropped."""
        universe = HOST.stage_universe(self.groups)
        for intent, stages in self.lock["intents"].items():
            for stage in stages:
                self.assertIn(stage, universe, "%s stage %r has no column" % (intent, stage))

    def test_unmapped_stage_is_refused(self):
        """Silently dropping an unknown stage is worse than refusing to provision."""
        broken = dict(INTENTS)
        broken["bugfix"] = INTENTS["bugfix"] + ["brand-new-stage"]
        self.write_stages(broken)
        lock = HOST.ensure_stages(self.host)
        with self.assertRaises(HOST.Fail) as caught:
            HOST.build_plan(self.host, self.groups, lock["intents"], "bugfix", "human", "p")
        self.assertIn("brand-new-stage", str(caught.exception))

    def test_unknown_intent_lists_what_is_valid(self):
        """An intent typo must name the alternatives instead of guessing."""
        with self.assertRaises(HOST.Fail) as caught:
            HOST.build_plan(self.host, self.groups, self.lock["intents"], "bugfixx", "human", "p")
        self.assertIn("bugfix", str(caught.exception))

    def test_label_must_slugify_to_column_id(self):
        """Multica derives a status key from the label; a mismatch breaks updates forever."""
        path = self.tmp / "config" / "columns.json"
        doc = json.loads(path.read_text())
        doc["groups"][0]["label"] = "Front door"
        path.write_text(json.dumps(doc))
        with self.assertRaises(HOST.Fail) as caught:
            HOST.load_groups(path)
        self.assertIn("slugifies", str(caught.exception))

    def test_column_without_instructions_is_refused(self):
        """A column nobody wrote instructions for would run an empty step."""
        path = self.tmp / "stages" / "columns.md"
        text = path.read_text()
        path.write_text(text.split("## audit")[0])
        with self.assertRaises(HOST.Fail) as caught:
            HOST.build_plan(self.host, self.groups, self.lock["intents"], "feature", "human", "p")
        self.assertIn("audit", str(caught.exception))


class TestPlanShape(HostCase):
    def test_feature_traverses_all_eleven_columns(self):
        """A collapsed group losing a stage changes what the board asks of a worker."""
        plan = HOST.build_plan(self.host, self.groups, self.lock["intents"], "feature", "human", "p")
        self.assertEqual([c["id"] for c in plan["columns"]],
                         ["intake", "framing", "product_gate", "design", "interface_gate",
                          "tech", "tech_gate", "build", "verify", "diff_gate", "audit"])

    def test_bugfix_skips_the_design_and_tech_chain(self):
        """bugfix must not hand a worker interview/interface/architecture work."""
        plan = HOST.build_plan(self.host, self.groups, self.lock["intents"], "bugfix", "human", "p")
        self.assertEqual([c["id"] for c in plan["columns"]],
                         ["intake", "framing", "product_gate", "build", "verify", "audit"])

    def test_investigate_has_no_gate_and_no_gatekeeper(self):
        """An intent with no gate must not provision a gatekeeper agent."""
        plan = HOST.build_plan(self.host, self.groups, self.lock["intents"], "investigate", "agent", "p")
        self.assertNotIn("gatekeeper", [a["agent"] for a in plan["agents"]])

    def test_plan_reads_only_the_skills_it_needs(self):
        """Attaching all 32 skills to one agent is the noise we are avoiding."""
        plan = HOST.build_plan(self.host, self.groups, self.lock["intents"], "bugfix", "human", "p")
        self.assertLessEqual(len(plan["skills"]), 12)
        self.assertNotIn("stelow-workflow-interface-contrast", plan["skills"])


class TestApply(HostCase):
    def test_apply_then_reapply_creates_nothing(self):
        """Re-running apply must converge, not duplicate agents and workflows."""
        self.apply()
        first = list(self.fp().calls)
        self.assertTrue(any("create" in call for call in first))
        self.fp().calls.clear()
        self.apply()
        second = self.fp().calls
        self.assertFalse([c for c in second if "create" in c], "second apply created something: %s" % second)
        self.assertTrue([c for c in second if "update" in c])

    def test_human_gates_hand_the_step_to_the_project_lead(self):
        """A human gate that silently runs an agent is the worst possible failure."""
        self.apply(gates="human")
        steps = {s["status_key"]: s for s in self.fp().state["workflows"]["stelow-feature-human"]}
        for gate in ("product_gate", "interface_gate", "tech_gate", "diff_gate"):
            self.assertEqual(steps[gate]["handler"]["type"], "project_lead", gate)

    def test_agent_gates_hand_the_step_to_the_reviewer(self):
        """Without this the --gates agent mode would leave gates to a stage agent."""
        self.apply(gates="agent")
        reviewer = self.fp().state["agents"]["stelow-review"]
        steps = {s["status_key"]: s for s in self.fp().state["workflows"]["stelow-feature"]}
        for gate in ("product_gate", "interface_gate", "tech_gate", "diff_gate"):
            self.assertEqual(steps[gate]["handler"], {"type": "agent", "id": reviewer}, gate)

    def test_steps_chain_forward_and_back(self):
        """A broken forward chain strands the issue; a broken back edge loses rework."""
        self.apply()
        steps = self.fp().state["workflows"]["stelow-feature-human"]
        keys = [s["status_key"] for s in steps]
        self.assertEqual(keys[0], "todo")
        self.assertEqual(keys[-1], "done")
        for index in range(1, len(steps) - 1):
            self.assertEqual(steps[index]["next_status_key"], keys[index + 1], keys[index])
        build = next(s for s in steps if s["status_key"] == "build")
        self.assertEqual(build["back_status_key"], "framing")
        self.assertEqual(steps[0]["next_status_key"], "intake")

    def test_agent_receives_adapter_rules_and_only_its_skills(self):
        """Without the adapter preamble the agent duplicates board state in a file."""
        self.apply()
        fake = self.fp()
        instructions = [call[call.index("--instructions") + 1] for call in fake.calls
                        if call[:2] == ["agent", "create"]][0]
        self.assertIn("never duplicate it", instructions)
        # 3 agents, and each carries exactly the skills its own columns name.
        self.assertEqual(sorted(fake.state["agents"]), ["stelow-build", "stelow-plan", "stelow-review"])
        self.assertEqual(len(fake.state["agent_skills"]["stelow-build"]), 4)
        self.assertEqual(len(fake.state["agent_skills"]["stelow-plan"]), 11)
        self.assertEqual(len(fake.state["agent_skills"]["stelow-review"]), 4)

    def test_project_is_pointed_at_the_workflow(self):
        """Provisioning without the project binding leaves the board unchanged."""
        self.apply(project="proj-1")
        self.assertEqual(self.fp().state["projects"]["proj-1"], "stelow-feature-human")

    def test_back_target_always_exists_in_the_chain(self):
        """A short intent chain can omit the column stelow reworks to; a dangling
        back_status_key either fails at the server or strands the issue."""
        self.apply(intent="refactor")
        steps = self.fp().state["workflows"]["stelow-refactor-human"]
        keys = {step["status_key"] for step in steps}
        for step in steps:
            for field in ("next_status_key", "back_status_key"):
                if field in step:
                    self.assertIn(step[field], keys, "%s points outside the chain" % field)

    def test_apply_refuses_a_half_filled_config(self):
        """Writing with no runtime_id half-provisions a workspace nobody can undo."""
        self.host["multica"]["runtime_id"] = ""
        with self.assertRaises(HOST.Fail) as caught:
            self.apply()
        self.assertIn("runtime_id", str(caught.exception))
        self.assertEqual(self.fp().calls, [], "preflight must run before any write")


class TestDoctor(HostCase):
    def test_doctor_passes_offline_on_a_clean_config(self):
        """The clean case must be green, or nobody reads the red one."""
        self.host["multica"]["bin"] = sys.executable
        code = HOST.cmd_doctor(self.host, self.args(offline=True), self.groups, self.lock)
        self.assertEqual(code, 0)

    def test_doctor_fails_without_a_runtime_id(self):
        """A missing runtime id only shows up when the first agent tries to start."""
        self.host["multica"]["bin"] = sys.executable
        self.host["multica"]["runtime_id"] = ""
        code = HOST.cmd_doctor(self.host, self.args(offline=True), self.groups, self.lock)
        self.assertEqual(code, 1)


class TestRedProof(HostCase):
    def test_rows_refuses_an_ambiguous_payload(self):
        """Two lists in one payload: picking one blindly decides create-vs-update
        against the wrong rows, which duplicates every agent on the next run."""
        with self.assertRaises(HOST.Fail):
            REAL_MULTICA._rows({"rows": [{"id": "a"}], "meta": [{"id": "b"}]}, "agent list")

    def test_rows_refuses_non_object_rows(self):
        with self.assertRaises(HOST.Fail):
            REAL_MULTICA._rows(["not-a-row"], "skill list")

    def test_duplicate_names_are_refused(self):
        """Last-wins on a name collision silently targets the wrong agent."""
        with self.assertRaises(HOST.Fail):
            REAL_MULTICA._by_name(
                [{"id": "1", "name": "stelow:build"}, {"id": "2", "name": "stelow:build"}],
                "agent list",
            )

    def test_a_stage_with_no_catalog_owner_is_reported(self):
        """Column skills are derived from the catalog, so a stage the catalog
        forgets runs on column prose alone — the instructions nobody wrote."""
        plan = HOST.build_plan(self.host, self.groups, self.lock["intents"], "feature", "human", "")
        owners = dict(self.lock["owners"])
        self.assertEqual(HOST.owner_gaps(plan, owners), [])
        del owners["shape"]
        gaps = HOST.owner_gaps(plan, owners)
        self.assertEqual(len(gaps), 1, gaps)
        self.assertIn("shape", gaps[0])

    def test_agent_run_gates_load_the_gate_skill(self):
        """With --gates agent the gate step is handed to an agent: it must have
        read the gate's own instructions, which the catalog names."""
        plan = HOST.build_plan(self.host, self.groups, self.lock["intents"], "feature", "agent", "")
        review = next(a for a in plan["agents"] if a["agent"] == "review")
        for stage in ("gate", "int-gate", "plan-gate", "diff-gate"):
            self.assertIn(self.lock["owners"][stage], review["skills"], stage)


class TestFlowBackEdges(HostCase):
    def test_a_back_edge_that_skips_the_owning_column_is_reported(self):
        """A rejected diff review must land on execution. Pointing it at verify
        skips the re-execution and turns the promised loop into a forward move."""
        plan = HOST.build_plan(self.host, self.groups, self.lock["intents"], "feature", "human", "")
        edges = HOST.parse_transitions(transitions_md())
        universe = HOST.stage_universe(self.groups)
        self.assertEqual(HOST.flow_gaps(plan, edges, universe), [])
        for col in plan["columns"]:
            if col["id"] == "diff_gate":
                col["back_to"] = "verify"
        gaps = HOST.flow_gaps(plan, edges, universe)
        self.assertEqual(len(gaps), 1, gaps)
        self.assertIn("diff-gate", gaps[0])

    def test_transitions_parser_stops_at_the_target_list(self):
        """Real lines carry prose after the targets; reading it as a stage name
        would invent edges that do not exist."""
        text = ("### gate\n\n```\nnext:      scope, execution\nreject:    shape\n```\n\n"
                "### context\n\n```\nreject:    context:5 - a gate id, not a stage\n```\n")
        edges = HOST.parse_transitions(text)
        self.assertEqual(edges["gate"]["reject"], ["shape"])
        self.assertEqual(edges["gate"]["next"], ["scope", "execution"])
        self.assertNotIn("context", edges, "a gate id is not a stage and must not survive parsing")


    def test_two_columns_may_share_one_agent(self):
        """A broad agent must get the union of both columns' skills.

        Keeping only the first column's list leaves the second column's stages
        owned by a skill the agent never loads — a stage dispatched unguarded,
        and owner_gaps only notices when the primary catalog is complete.
        """
        groups = list(self.groups)
        for group in groups:
            if group["id"] in ("intake", "framing"):
                group["agent"] = "stelow-plan"
        plan = HOST.build_plan(self.host, groups, self.lock["intents"], "feature", "human", "")
        shared = [a for a in plan["agents"] if a["agent"] == "stelow-plan"]
        self.assertEqual(len(shared), 1, "one agent entry, not two")
        wanted = set()
        for group in groups:
            if group.get("agent") == "stelow-plan":
                wanted |= set(group["skills"])
                wanted |= {self.lock["owners"][s] for s in group["stages"] if s in self.lock["owners"]}
        self.assertEqual(set(shared[0]["skills"]), wanted)

    def test_the_lock_carries_the_owners_and_the_rejects(self):
        """plan derives skills from owners and doctor checks back-edges against
        rejects, both read from this file. Leaving them out makes both checks
        pass while checking nothing — which is exactly what shipped once."""
        lock = HOST.read_json(HOST.LOCK, "stelow.lock.json")
        self.assertEqual(lock["owners"]["shape"], "stelow-workflow-shape-up")
        self.assertEqual(lock["rejects"]["diff-gate"], ["execution"])

    def test_a_create_payload_with_several_lists_yields_its_object(self):
        """agent create returns skills, env and labels as their own lists; taking
        "the first list of dicts" picked none of them and failed the run after
        every skill had already been imported."""
        payload = {"id": "agent-1", "name": "stelow-plan", "skills": [{"id": "s1"}], "env": [{"k": "v"}]}
        self.assertEqual(REAL_MULTICA._one(payload, "agent create")["id"], "agent-1")
        with self.assertRaises(HOST.Fail):
            REAL_MULTICA._one({"skills": [], "env": []}, "agent create")

class TestVerify(HostCase):
    def test_a_stale_runtime_id_is_reported(self):
        """apply succeeds and every card sits there when the id belongs to a
        machine that is not this one; doctor must say so."""
        ok, detail = HOST.runtime_check(self.host, self.fake)
        self.assertTrue(ok, detail)
        self.fake.state["runtime_status"] = "offline"
        ok, detail = HOST.runtime_check(self.host, self.fake)
        self.assertFalse(ok)
        self.assertIn("offline", detail)
        self.host["multica"]["runtime_id"] = "not-this-daemon"
        ok, detail = HOST.runtime_check(self.host, self.fake)
        self.assertFalse(ok)
        self.assertIn("missing", detail)

    def test_a_bookend_step_with_no_handler_is_not_drift(self):
        """The API spells "nothing happens" as {"type":"none"} and our bookends
        omit the field; comparing raw values reported drift on todo and done."""
        self.apply()
        wf = self.fake.state["workflows"]["stelow-feature-human"]
        for step in wf:
            step.setdefault("handler", {"type": "none"})
        self.assertEqual(HOST.cmd_verify(self.host, self.args(), self.groups, self.lock), 0)

    def test_status_prints_a_pinned_digest(self):
        """status crashed on a KeyError after the lock gained its own sha keys."""
        self.apply()
        self.assertEqual(HOST.cmd_status(self.host, self.args(), self.groups, self.lock), 0)

    def test_a_builtin_terminal_column_is_not_drift(self):
        """Multica appends its own `cancelled` column to every workflow. An exact
        list compare made verify fail forever on a converged workspace — the
        check that is supposed to be runnable stopped being runnable."""
        self.apply()
        self.fake.state["workflows"]["stelow-feature-human"].append({"status_key": "cancelled"})
        self.assertEqual(HOST.cmd_verify(self.host, self.args(), self.groups, self.lock), 0)

    def test_an_unexpected_custom_column_is_drift(self):
        """The other half: a column we never asked for means someone edited the
        board by hand, and verify must say so."""
        self.apply()
        self.fake.state["workflows"]["stelow-feature-human"].append({"status_key": "staging"})
        self.assertEqual(HOST.cmd_verify(self.host, self.args(), self.groups, self.lock), 1)

    def test_verify_passes_right_after_apply(self):
        """A verify that fails on a fresh apply is a verify nobody will keep running."""
        self.apply()
        state = json.loads(json.dumps(self.fp().state))
        HOST.Multica = lambda host: self.seeded(state)
        self.assertEqual(HOST.cmd_verify(self.host, self.args(), self.groups, self.lock), 0)

    def test_verify_catches_a_removed_skill(self):
        """Drift between the plan and the workspace is the only thing verify is for."""
        self.apply()
        state = json.loads(json.dumps(self.fp().state))
        state["skills"].pop("stelow-workflow-shape-up")
        HOST.Multica = lambda host: self.seeded(state)
        self.assertEqual(HOST.cmd_verify(self.host, self.args(), self.groups, self.lock), 1)

    def test_verify_catches_a_repointed_handler(self):
        """A gate quietly reassigned to an agent must be reported, not tolerated."""
        self.apply()
        state = json.loads(json.dumps(self.fp().state))
        for step in state["workflows"]["stelow-feature-human"]:
            if step["status_key"] == "product_gate":
                step["handler"] = {"type": "project_lead"}
                step["next_status_key"] = "design"
                step["handler"] = {"type": "agent", "id": state["agents"]["stelow-build"]}
        HOST.Multica = lambda host: self.seeded(state)
        self.assertEqual(HOST.cmd_verify(self.host, self.args(), self.groups, self.lock), 1)

    # helpers -----------------------------------------------------------

    def applied(self):
        return self.seeded(json.loads(json.dumps(self.fp().state)))

    def seeded(self, state):
        fake = FakeMultica(self.host)
        fake.state = state
        return fake


class TestStageInstructionGuards(unittest.TestCase):
    """The instructions are the contract; these keep it from being edited away.

    Each test names what it catches when someone rewrites the prose.
    """

    def setUp(self):
        self.adapter = (REPO / "agents" / "_adapter.md").read_text()
        self.columns = (REPO / "stages" / "columns.md").read_text()

    def section(self, name):
        body = self.columns.split("\n## " + name + "\n", 1)[1]
        return body.split("\n## ", 1)[0]

    def test_artifacts_leave_as_attachments(self):
        # Catches: an edit that lets a stage paste its artifact into the comment
        # body again. The smoke card shipped wireframes, a contrast table and a
        # scope map as prose, and nothing downstream could download them.
        self.assertIn("--attachment", self.adapter)
        self.assertIn("Artifacts leave as files", self.adapter)
        self.assertIn("attached", self.section("framing"))
        self.assertIn("attached", self.section("build"))
        self.assertIn("18-audit-table.md", self.section("audit"))
        for gate in ("product_gate", "interface_gate"):
            self.assertIn("attached", self.section(gate), gate)

    def test_verify_does_not_run_the_whole_suite(self):
        # Catches: restoring "Run the full test suite" in the verify column,
        # which held one card for fifty minutes and reported what the narrow
        # run already knew.
        body = self.section("verify")
        self.assertNotIn("Run the full test suite", body)
        self.assertIn("CI's job", body)
        self.assertIn("which command you ran", body)

    def test_every_card_message_is_english(self):
        # Catches: the adapter losing the language rule, which is how one card
        # ended up with an English plan and Portuguese gate answers.
        self.assertIn("Everything you write on the card is English", self.adapter)

    def test_no_command_outlives_the_turn(self):
        # Catches: dropping the command cap. Verify once sat fifty minutes inside
        # one uncapped suite and could not read the steering message it was sent.
        self.assertIn("No command outlives your turn", self.adapter)
        self.assertIn("timeout 300", self.adapter)
        self.assertIn("timeout 300", self.section("verify"))

    def test_a_long_stage_reports_liveness(self):
        # Catches: dropping the interim-line rule. Design once ran 28 minutes
        # with nothing on the card, and the reviewer had to ask if it was alive.
        self.assertIn("Silence has a limit", self.adapter)
        self.assertIn("interim line", self.adapter)


class TestUpstreamCheck(unittest.TestCase):
    def test_a_transport_error_is_not_a_missing_skill(self):
        # Catches: a network blip reported as "not at the pinned path", which
        # blocked apply on the live workspace and named a skill that was fine.
        import urllib.request
        from unittest import mock

        with mock.patch.object(urllib.request, "urlopen", side_effect=OSError("timed out")):
            with self.assertRaises(HOST.Fail) as caught:
                HOST.upstream_status("https://example.invalid/SKILL.md")
        self.assertIn("cannot reach", str(caught.exception))

    def test_a_404_means_the_skill_is_missing(self):
        import urllib.error
        import urllib.request
        from unittest import mock

        not_found = urllib.error.HTTPError("https://x/SKILL.md", 404, "Not Found", {}, None)
        with mock.patch.object(urllib.request, "urlopen", side_effect=not_found):
            self.assertEqual(HOST.upstream_status("https://x/SKILL.md"), 404)


class TestArtifactsAndParking(unittest.TestCase):
    def setUp(self):
        self.columns = json.loads((REPO / "config" / "columns.json").read_text())
        self.md = (REPO / "stages" / "columns.md").read_text()
        self.adapter = (REPO / "agents" / "_adapter.md").read_text()

    def test_every_column_declares_its_artifacts(self):
        # Catches: a new column that names no artifact, which lets its stage hand
        # nothing over while still looking finished.
        for group in self.columns["groups"]:
            self.assertIn("artifacts", group, f"{group['id']} declares no artifacts")
            if group["id"] != "intake":
                self.assertTrue(group["artifacts"], f"{group['id']} declares an empty artifact list")

    def test_artifact_names_sort_by_stage_and_kind(self):
        # Catches: `DECISION.md`, `spec-tech` and `spec-product_v2.md` on one
        # card, where nothing sorts and prose mixes with data.
        pattern = re.compile(r"^\d{2}-[a-z0-9-]+\.(md|json)$")
        seen = set()
        for group in self.columns["groups"]:
            for name in group["artifacts"]:
                self.assertRegex(name, pattern)
                self.assertNotIn(name, seen, f"{name} is declared twice")
                seen.add(name)

    def test_columns_md_lists_the_same_artifacts(self):        # Catches: the two files drifting apart, which is how the artifact list
        # stops matching what the agent is actually told to attach.
        for group in self.columns["groups"]:
            for name in group["artifacts"]:
                self.assertIn(name, self.md, f"{name} is in columns.json but not in columns.md")
        declared = {name for group in self.columns["groups"] for name in group["artifacts"]}
        for name in re.findall(r"`(\d{2}-[a-z0-9-]+\.(?:md|json))`", self.md):
            self.assertIn(name, declared, f"{name} is in columns.md but not in columns.json")


class TestAskingLeavesATrace(unittest.TestCase):
    """A parked card has to look parked, and the instructions have to say so.

    On the second smoke run a card parked for a human ruling sat in its column
    with no run for forty minutes: nothing marked it, nothing woke it, and the
    person reading it assumed the agent was still working.
    """

    def setUp(self):
        self.adapter = (REPO / "agents" / "_adapter.md").read_text()

    def test_parking_marks_the_card_and_arms_a_wakeup(self):
        for command in (
            "multica issue label add",
            "needs-human",
            "multica issue wakeup create",
            "multica issue label remove",
        ):
            self.assertIn(command, self.adapter, f"the adapter no longer teaches {command!r}")

    def test_parking_is_reserved_for_rulings(self):
        # Catches: an agent parking on a finding it could close by reading the
        # code, which hands the human engineering work and stops the card.
        self.assertIn("Park only when the answer changes what ships", self.adapter)

    def test_a_gate_column_tells_the_agent_to_mark_the_wait(self):
        # Catches: a card parked for a ruling with nothing on it saying so,
        # which is how CAL-52 sat in diff_gate until someone noticed.
        section = (REPO / "stages" / "columns.md").read_text()
        self.assertIn("## When the card waits on a person", section)
        self.assertIn("issue label add <this issue> needs-human", section)
        self.assertIn("issue wakeup create <this issue> --after 45m", section)

    def test_the_adapter_carries_the_density_rules(self):
        for rule in ("<nn>-<kind>.<ext>", "## Tests run once", "## Asking is a state"):
            self.assertIn(rule, self.adapter, f"the adapter dropped {rule!r}")

    def test_artifact_revisions_do_not_multiply_names(self):
        # Catches: `spec-tech_v1.md` and `spec-tech_v2.md` both attached to one
        # card, which is a diff nobody can make.
        self.assertIn("Never put a version suffix", self.adapter)
        self.assertIn("carried forward", self.adapter)

    def test_the_outcome_comment_states_the_position(self):
        # Catches: a card with twenty comments where the reader has to
        # reconstruct the chain before reading the outcome.
        self.assertIn("stage 7/18 - tech", self.adapter)

    def test_requirement_ids_are_minted_once(self):
        # Catches: audit renumbering requirements it cannot trace back to the
        # spec, which turns traceability into a translation exercise.
        md = (REPO / "stages" / "columns.md").read_text()
        self.assertIn("Mint the requirement ids here", md)
        self.assertIn("Cite the spec's ids", md)


class TestArtifactReport(unittest.TestCase):
    def test_a_card_names_what_it_is_missing(self):
        # Catches: a stage that produced nothing, on a card that closed anyway.
        groups = [
            {"id": "framing", "artifacts": ["01-spec-product.md", "02-critique-report.md"]},
            {"id": "audit", "artifacts": ["18-audit-table.md"]},
        ]
        declared, missing = HOST.artifact_report({"01-spec-product.md", "18-audit-table.md"}, groups)
        self.assertEqual(len(declared), 3)
        self.assertEqual(missing, [("framing", "02-critique-report.md")])

    def test_a_complete_card_misses_nothing(self):
        groups = [{"id": "framing", "artifacts": ["01-spec-product.md"]}]
        self.assertEqual(HOST.artifact_report({"01-spec-product.md"}, groups)[1], [])


class TestBoardFindings(unittest.TestCase):
    """Four card states, three of which look dead on the board."""

    gates = {"product_gate", "diff_gate"}
    known = {"build", "verify", "product_gate", "diff_gate"}

    def findings(self, issues, running=(), labels=None):
        return HOST.board_findings(issues, self.gates, self.known, set(running), labels or {})

    def test_a_gate_card_waiting_on_a_person_unmarked(self):
        # This is CAL-52 in diff_gate: no run, no marker, indistinguishable
        # from a run that died.
        issues = [{"id": "i1", "key": "CAL-52", "status": "diff_gate"}]
        unmarked, orphans, stale = self.findings(issues)
        self.assertEqual(unmarked, ["CAL-52"])
        self.assertEqual((orphans, stale), ([], []))

    def test_a_marked_gate_card_is_the_healthy_state(self):
        issues = [{"id": "i1", "key": "CAL-52", "status": "diff_gate"}]
        unmarked, orphans, stale = self.findings(issues, labels={"i1": {"needs-human"}})
        self.assertEqual((unmarked, orphans, stale), ([], [], []))

    def test_an_agent_column_with_no_run_is_an_orphan(self):
        # The other silent death: the run ended and nothing queued a successor.
        issues = [{"id": "i2", "key": "CAL-53", "status": "build"}]
        unmarked, orphans, _ = self.findings(issues)
        self.assertEqual(orphans, ["CAL-53"])
        self.assertEqual(unmarked, [])

    def test_a_marker_on_a_running_card_is_stale(self):
        issues = [{"id": "i3", "key": "CAL-54", "status": "build"}]
        _, _, stale = self.findings(issues, running={"i3"}, labels={"i3": {"needs-human"}})
        self.assertEqual(stale, ["CAL-54"])

    def test_cards_outside_the_workflow_are_ignored(self):
        # A backlog card is not a stalled stage.
        issues = [{"id": "i4", "key": "CAL-55", "status": "todo"}]
        self.assertEqual(self.findings(issues), ([], [], []))


class TestHostConfigEnvironment(unittest.TestCase):
    def test_ids_and_bin_come_from_the_environment(self):
        # Catches: losing an env override, which pushes a workspace's ids back
        # into the committed config/host.json template.
        import os

        saved = {key: os.environ.get(key) for key in
                 ("MULTICA_WORKSPACE_ID", "MULTICA_RUNTIME_ID", "MULTICA_PROJECT_ID", "MULTICA_BIN")}
        os.environ.update({
            "MULTICA_WORKSPACE_ID": "ws-from-env",
            "MULTICA_RUNTIME_ID": "rt-from-env",
            "MULTICA_PROJECT_ID": "pj-from-env",
            "MULTICA_BIN": "/usr/local/bin/multica",
        })
        try:
            cfg = HOST.load_host(REPO / "config" / "host.json")
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        self.assertEqual(cfg["multica"]["workspace_id"], "ws-from-env")
        self.assertEqual(cfg["multica"]["runtime_id"], "rt-from-env")
        self.assertEqual(cfg["multica"]["project_id"], "pj-from-env")
        self.assertEqual(cfg["multica"]["bin"], "/usr/local/bin/multica")


class TestRepositoryIsEnglish(unittest.TestCase):
    def test_no_portuguese_diacritics(self):
        # Catches: a Portuguese paragraph copied back in. The repository is
        # English end to end; the accented set is what a translation leaves behind.
        # Spelled by codepoint so this file stays ASCII and does not trip itself.
        accents = "".join(chr(code) for code in (
            225, 224, 226, 227, 233, 234, 237, 243, 244, 245, 250, 231,
            193, 192, 194, 195, 201, 202, 205, 211, 212, 213, 218, 199,
        ))
        offenders = []
        for path in sorted(REPO.rglob("*")):
            skip = (".git/", "node_modules", ".stelow-cache")
            if not path.is_file() or any(part in str(path) for part in skip):
                continue
            if path.suffix not in {".md", ".json", ".py", ".yml", ".yaml"} and path.name != "stelow-host":
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if any(ch in accents for ch in text):
                offenders.append(str(path.relative_to(REPO)))
        self.assertEqual(offenders, [], "Portuguese text found in: " + ", ".join(offenders))


if __name__ == "__main__":
    unittest.main(verbosity=2)
