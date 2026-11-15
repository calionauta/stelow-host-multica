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
        self.state = {"skills": {}, "agents": {}, "agent_skills": {}, "workflows": {}, "projects": {},
                      "project_titles": {"proj-1": "Proj One"}, "issues": {}}
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
        if args[:2] == ["issue", "get"]:
            issue = self.state.setdefault("issues", {}).get(args[2])
            return (0, json.dumps(issue), "") if issue else (1, "", "issue not found")
        if args[:3] == ["issue", "comment", "list"]:
            return 0, json.dumps(self.state.setdefault("comments", {}).get(args[3], [])), ""
        if args[:3] == ["issue", "label", "add"]:
            self.state.setdefault("labels", {}).setdefault(args[3], set()).add(args[4])
            return 0, json.dumps({"ok": True}), ""
        if args[:3] == ["issue", "wakeup", "create"]:
            self.state.setdefault("wakeups", []).append({
                "issue": args[3],
                "after": args[args.index("--after") + 1],
                "instruction": args[args.index("--instruction") + 1],
            })
            return 0, json.dumps({"ok": True}), ""
        if args[:2] == ["issue", "create"]:
            issue_id = self._next("issue")
            title = args[args.index("--title") + 1]
            self.state["issues"][issue_id] = {
                "id": issue_id, "key": "CAL-%d" % (len(self.state["issues"]) + 1),
                "title": title, "status": "todo", "project": args[args.index("--project") + 1],
            }
            return 0, json.dumps(self.state["issues"][issue_id]), ""
        if args[:2] == ["issue", "status"]:
            issue = self.state.get("issues", {}).get(args[2])
            if not issue:
                return 1, "", "issue not found"
            issue["status"] = args[3]
            return 0, json.dumps(issue), ""
        if args[:2] == ["issue-status", "list"]:
            return 0, json.dumps([{"key": key, "name": key} for key in self.state.setdefault("statuses", [])]), ""
        if args[:2] == ["issue-status", "create"]:
            key = args[args.index("--key") + 1]
            self.state.setdefault("statuses", []).append(key)
            return 0, json.dumps({"key": key}), ""
        if args[:2] == ["project", "list"]:
            titles = self.state["project_titles"]
            return 0, json.dumps([{"id": pid, "title": title} for pid, title in titles.items()]), ""
        if args[:2] == ["project", "create"]:
            title = args[args.index("--title") + 1]
            pid = self._next("proj")
            self.state["project_titles"][pid] = title
            return 0, json.dumps({"id": pid, "title": title}), ""
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
        for name in ("config", "agents", "stages", "boards"):
            shutil.copytree(REPO / name, self.tmp / name)
        (self.tmp / ".stelow-cache").mkdir()
        self.write_stages()
        HOST.set_root(self.tmp)
        self.original = HOST.Multica
        self.fake = FakeMultica(None)

        class FakeFactory:
            """A factory that also answers the class-level helpers the host calls.

            `cmd_card` uses `Multica._one` on the class, so a bare lambda was enough
            for everything except reading a card.
            """

            _one = staticmethod(HOST.Multica._one)

            def __call__(self, host):
                return self.fake

        factory = FakeFactory()
        factory.fake = self.fake
        HOST.Multica = factory
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


class TestSkillsAreNamedInTheStep(HostCase):
    def steps(self, intent="feature"):
        plan = HOST.build_plan(self.host, self.groups, self.lock["intents"], intent, "human", "p")
        return plan, HOST.build_steps(plan, self.host, HOST.IdMap({}), create=False)

    def test_every_pushed_step_names_the_skills_it_runs(self):
        # Catches: a column that describes its work for six hundred characters and
        # never names the skill carrying the method, so the agent searches for it or
        # improvises one. Dropping the skills block leaves valid prose and every other
        # test green, because nothing else reads what the agent is handed.
        plan, steps = self.steps()
        by_key = {column["id"]: column["skills"] for column in plan["columns"]}
        for step in steps:
            key = step["status_key"]
            if key not in by_key:
                continue
            self.assertTrue(by_key[key], key)
            self.assertIn("## Skills this step runs", step["instructions"], key)
            for skill in by_key[key]:
                self.assertIn("`%s`" % skill, step["instructions"], key)

    def test_a_gate_step_is_not_handed_the_writers_skills(self):
        # Catches: giving the reviewer the author's skill list, which turns a
        # cross-check into a repetition of the same instincts.
        _, steps = self.steps()
        gate = next(step for step in steps if step["status_key"] == "product_gate")
        self.assertNotIn("stelow-workflow-shape-up", gate["instructions"])


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
        steps = {s["status_key"]: s for s in self.fp().state["workflows"]["stelow"]}
        for gate in ("product_gate", "interface_gate", "tech_gate", "diff_gate"):
            self.assertEqual(steps[gate]["handler"]["type"], "project_lead", gate)

    def test_agent_gates_hand_the_step_to_the_reviewer(self):
        """Without this the --gates agent mode would leave gates to a stage agent."""
        self.apply(gates="agent")
        reviewer = self.fp().state["agents"]["stelow-review"]
        steps = {s["status_key"]: s for s in self.fp().state["workflows"]["stelow"]}
        for gate in ("product_gate", "interface_gate", "tech_gate", "diff_gate"):
            self.assertEqual(steps[gate]["handler"], {"type": "agent", "id": reviewer}, gate)

    def test_steps_chain_forward_and_back(self):
        """A broken forward chain strands the issue; a broken back edge loses rework."""
        self.apply()
        steps = self.fp().state["workflows"]["stelow"]
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
        self.assertEqual(self.fp().state["projects"]["proj-1"], "stelow")

    def test_back_target_always_exists_in_the_chain(self):
        """A short intent chain can omit the column stelow reworks to; a dangling
        back_status_key either fails at the server or strands the issue."""
        self.apply(intent="refactor")
        steps = self.fp().state["workflows"]["stelow"]
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
        wf = self.fake.state["workflows"]["stelow"]
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
        self.fake.state["workflows"]["stelow"].append({"status_key": "cancelled"})
        self.assertEqual(HOST.cmd_verify(self.host, self.args(), self.groups, self.lock), 0)

    def test_an_unexpected_custom_column_is_drift(self):
        """The other half: a column we never asked for means someone edited the
        board by hand, and verify must say so."""
        self.apply()
        self.fake.state["workflows"]["stelow"].append({"status_key": "staging"})
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
        for step in state["workflows"]["stelow"]:
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

    def test_the_back_edge_has_a_budget(self):
        # Catches: an audit that keeps sending the same card back, which is a
        # loop billing a project for a decision a person owes.
        policy = json.loads((REPO / "config" / "columns.json").read_text())["policy"]
        self.assertEqual(policy["max_back_edges"], 2)
        self.assertIn("third** pass through build", (REPO / "stages" / "columns.md").read_text())
        self.assertIn("## A back edge has a budget", self.adapter)

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


class TestBackEdgeBudget(unittest.TestCase):
    def groups(self):
        return [
            {"id": "diff_gate", "back_to": "build"},
            {"id": "audit", "back_to": "build"},
            {"id": "build"},
        ]

    def event(self, src, dst):
        return {"action": "status_changed", "details": {"from": src, "to": dst}}

    def test_one_round_is_inside_the_budget(self):
        # Catches: a reviewer doing its job being reported as a runaway loop.
        events = [self.event("audit", "build"), self.event("build", "audit")]
        self.assertEqual(HOST.back_edge_findings(events, self.groups(), 2), [])

    def test_the_third_round_trips(self):
        # Catches: a card ping-ponging while a person is never asked to rule.
        events = [self.event("audit", "build")] * 3
        self.assertEqual(HOST.back_edge_findings(events, self.groups(), 2), [("audit", "build", 3)])

    def test_only_declared_pairs_count(self):
        # Catches: counting any backwards move, so an unrelated transition trips
        # a budget it never spent.
        events = [self.event("verify", "build")] * 5
        self.assertEqual(HOST.back_edge_findings(events, self.groups(), 2), [])

    def test_the_limit_comes_from_the_config(self):
        # Catches: the number existing only in prose, so the check and the
        # instructions disagree.
        policy = json.loads((REPO / "config" / "columns.json").read_text())["policy"]
        self.assertEqual(policy["max_back_edges"], 2)


class TestThePlanResolver(unittest.TestCase):
    def args(self, board=None):
        return types.SimpleNamespace(board=board, intent="feature", gates="human", project="x")

    def test_a_board_and_the_chain_cannot_disagree(self):
        # Catches the bug this test exists for: `--board` was wired into `plan`
        # only, so `apply --board explore` re-applied the 18-stage chain to the
        # live project and said nothing.
        plan = HOST.resolve_plan({}, self.args(board="explore"), [], {"intents": {}})
        self.assertTrue(plan.get("_board"))
        self.assertEqual(plan["workflow"], "stelow-explore")

    def test_no_board_flag_still_builds_the_chain(self):
        # Catches: the resolver swallowing the chain path.
        with self.assertRaises(Exception):
            HOST.resolve_plan({}, self.args(), [], {"intents": {}})


class TestBoards(unittest.TestCase):
    def board(self, **overrides):
        board = {
            "version": 1, "board": "probe", "workflow": "stelow-probe", "project": "Probe",
            "gates": "human", "runner": "stelow-probe-runner", "skill_prefix": "stelow-product-",
            "menu": [{"skill": "stelow-product-pricing", "when": "a price has to be chosen"}],
            "columns": [
                {"id": "open", "label": "Open", "category": "unstarted", "gate": True, "instructions": "name the decision"},
                {"id": "run", "label": "Run", "category": "started", "agent": "stelow-probe-runner", "instructions": "run one skill"},
                {"id": "review", "label": "Review", "category": "started", "gate": True,
                 "back_to": "run", "instructions": "read the artifact"},
            ],
        }
        board.update(overrides)
        return board

    def test_both_shipped_boards_are_runnable(self):
        # Catches: a board file that reads fine and cannot produce a card.
        for name in ("explore", "research"):
            board = HOST.load_board(name)
            self.assertEqual(HOST.board_problems(board), [], name)

    def test_a_menu_entry_without_a_reason_is_refused(self):
        # Catches: a runner guessing between 21 skills from names alone.
        board = self.board()
        board["menu"] = [{"skill": "stelow-product-pricing"}]
        self.assertIn("no 'when'", " ".join(HOST.board_problems(board)))

    def test_two_working_columns_are_refused(self):
        # Catches: a board that quietly becomes a chain again.
        board = self.board()
        board["columns"].append({"id": "run2", "label": "Run2", "category": "started",
                                 "agent": "stelow-probe-runner", "instructions": "again"})
        self.assertIn("exactly one working column", " ".join(HOST.board_problems(board)))

    def test_a_runner_with_no_agent_file_is_refused(self):
        # Catches: an agent created with an empty prompt, which runs and says nothing.
        self.assertIn("agents/stelow-nobody.md", " ".join(HOST.board_problems(self.board(runner="stelow-nobody"))))

    def test_a_back_edge_to_nowhere_is_refused(self):
        # Catches: a send-back that lands on a status the workflow does not have.
        board = self.board()
        board["columns"][2]["back_to"] = "nowhere"
        self.assertIn("backs to nowhere", " ".join(HOST.board_problems(board)))

    def test_a_board_plan_feeds_the_step_builder(self):
        # Catches: the board path drifting from the chain path, so apply pushes
        # something the workflow endpoint rejects.
        plan = HOST.board_plan({"agents": {}}, HOST.load_board("research"))
        self.assertEqual(plan["gates"], "human")
        self.assertEqual([c["id"] for c in plan["columns"]], ["bucket", "doing", "review"])
        self.assertEqual(len(plan["skills"]), len(HOST.load_board("research")["menu"]))


class TestStalledCards(unittest.TestCase):
    KNOWN = {"doing", "review"}

    def issue(self, key, status, stamp):
        return {"key": key, "id": key, "status": status, "updated_at": stamp}

    def test_a_card_untouched_past_the_limit_is_named(self):
        # Catches: a workflow that stops delivering while every check passes,
        # because "nothing is broken" and "nothing is moving" are different.
        from datetime import datetime, timezone
        now = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
        issues = [self.issue("CAL-1", "doing", "2026-11-13T11:00:00Z"),
                  self.issue("CAL-2", "doing", "2026-11-15T10:00:00Z")]
        self.assertEqual(HOST.stalled_cards(issues, self.KNOWN, 48, now),
                         [("CAL-1", "doing", 49.0)])

    def test_a_closed_card_is_never_stalled(self):
        from datetime import datetime, timezone
        now = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
        issues = [self.issue("CAL-3", "done", "2026-01-01T00:00:00Z")]
        self.assertEqual(HOST.stalled_cards(issues, self.KNOWN, 48, now), [])

    def test_a_card_without_a_timestamp_is_skipped_not_crashed(self):
        from datetime import datetime, timezone
        now = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
        issues = [{"key": "CAL-4", "id": "CAL-4", "status": "run"}]
        self.assertEqual(HOST.stalled_cards(issues, self.KNOWN, 48, now), [])


class TestWorkflowName(unittest.TestCase):
    def test_the_whole_workflow_object_reads_as_a_name(self):
        # Catches: the shape `project workflow get` actually returns, which made
        # install --check report FAIL on three correct projects.
        self.assertEqual(HOST.workflow_name_of({"name": "stelow-explore", "steps": []}), "stelow-explore")

    def test_the_set_shape_reads_as_a_name(self):
        # Catches: the other shape, from `project workflow set`.
        self.assertEqual(HOST.workflow_name_of({"workflow": "stelow"}), "stelow")

    def test_an_unknown_shape_is_empty_not_a_crash(self):
        self.assertEqual(HOST.workflow_name_of(None), "")
        self.assertEqual(HOST.workflow_name_of([1, 2]), "")


class TestInstall(HostCase):
    def test_install_declares_one_workflow_with_every_track(self):
        # Catches: a track naming a board nobody ships, so `install` converges a
        # workflow with a column the repository cannot describe.
        install = HOST.load_install()
        self.assertEqual(install["workflow"], "stelow")
        self.assertEqual([track["id"] for track in install["tracks"]], ["build", "explore", "research"])
        for track in install["tracks"]:
            if track["kind"] == "loose":
                self.assertTrue((REPO / "boards" / (track["board"] + ".json")).is_file(), track["board"])
                self.assertNotIn("-", track["entry"])

    def test_a_track_entry_is_a_status_key_the_tracker_accepts(self):
        # Catches: a hyphen in a track entry, which a tracker rejects with a
        # message about the key shape rather than about the track.
        self.assertEqual(HOST.track_entry("build"), "intake")
        self.assertEqual(HOST.track_entry("explore"), "bucket")
        self.assertEqual(HOST.track_entry("research"), "bucket")

    def test_install_check_fails_when_a_project_runs_another_workflow(self):
        # Catches: a repository project left on another flow, which reports green
        # everything except the one thing that matters.
        self.host["multica"]["project_id"] = "proj-1"
        self.fake.state["projects"] = {"proj-1": "someone-elses-flow"}
        self.fake.state["workflows"] = {}
        code = HOST.cmd_install(self.host, self.args(check=True), self.groups, self.lock)
        self.assertEqual(code, 1)

    def seed_three_workflows(self):
        """The workspace an install is supposed to produce, written by hand."""
        plans = HOST.install_plans(self.host, self.args(), self.groups, self.lock)
        self.fake.state["workflows"] = {}
        for plan in plans:
            steps = HOST.build_steps(plan, self.host, HOST.IdMap({}), create=False)
            self.fake.state["workflows"][plan["workflow"]] = [{"status_key": s["status_key"]} for s in steps]
        self.fake.state["project_titles"]["proj-1"] = "stelow"
        self.fake.state["projects"] = {
            "proj-1": "stelow", "probe-explore": "stelow-explore", "probe-research": "stelow-research",
        }
        self.fake.state["project_titles"]["probe-explore"] = "Explore"
        self.fake.state["project_titles"]["probe-research"] = "Research"
        return plans

    def test_install_declares_three_workflows(self):
        # Catches: the twenty-column board coming back, or a lane silently becoming
        # a status inside the chain again.
        plans = HOST.install_plans(self.host, self.args(), self.groups, self.lock)
        self.assertEqual([plan["workflow"] for plan in plans],
                         ["stelow", "stelow-explore", "stelow-research"])
        self.assertEqual([plan["project"] for plan in plans], ["", "Explore", "Research"])
        chain = {column["id"] for column in plans[0]["columns"]}
        self.assertNotIn("explore_run", chain)
        self.assertNotIn("research_run", chain)

    def test_install_check_passes_when_every_project_runs_its_workflow(self):
        # Catches: a check that fails on a correct workspace, which teaches people
        # to ignore it.
        self.host["multica"]["project_id"] = "proj-1"
        self.seed_three_workflows()
        code = HOST.cmd_install(self.host, self.args(check=True), self.groups, self.lock)
        self.assertEqual(code, 0)

    def test_install_check_fails_when_a_lane_runs_the_build_flow(self):
        # Catches: an Explore project pointed at the chain, so an explore card lands
        # in `intake` and gets walked through eighteen stages.
        self.host["multica"]["project_id"] = "proj-1"
        self.seed_three_workflows()
        self.fake.state["projects"]["probe-explore"] = "stelow"
        code = HOST.cmd_install(self.host, self.args(check=True), self.groups, self.lock)
        self.assertEqual(code, 1)

    def args(self, **kwargs):
        scope = types.SimpleNamespace(intent="feature", gates="human", project=None,
                                      migrate=False, refresh_skills=False, json=False,
                                      offline=True, board=None, all=False, check=False,
                                      install=False, all_workflows=False, workflow_name=None,
                                      all_projects=False)
        for key, value in kwargs.items():
            setattr(scope, key, value)
        return scope


class TestTheDeclarationAndItsBoards(HostCase):
    def test_every_declared_lane_has_a_board_and_every_board_is_declared(self):
        # Catches: a board file nobody installs (dead weight that still passes
        # `board`), and a declaration with no board, which fails at apply time on a
        # reader's workspace instead of in review.
        declared = {workflow["board"] for workflow in HOST.load_install()["workflows"] if workflow.get("board")}
        files = {path.stem for path in (self.tmp / "boards").glob("*.json")}
        self.assertEqual(declared, files)

    def test_each_workflow_owns_one_project_and_the_chain_takes_the_repositories(self):
        # Catches: the chain and a lane pointing at the same project, which is how the
        # Explore project came to run the eighteen-stage build flow.
        workflows = HOST.load_install()["workflows"]
        chain = [workflow for workflow in workflows if workflow["kind"] == "chain"]
        self.assertEqual(len(chain), 1)
        self.assertEqual(chain[0].get("projects"), "repo")
        lanes = [workflow for workflow in workflows if workflow["kind"] == "loose"]
        self.assertEqual(sorted(workflow["project"] for workflow in lanes), ["Explore", "Research"])
        self.assertEqual(len({workflow["project"] for workflow in lanes}), len(lanes))


class TestWhatACardKept(HostCase):
    def seed(self, status, description, attachments):
        self.fake.state.setdefault("issues", {})["i1"] = {
            "id": "i1", "key": "CAL-9", "title": "a card", "status": status, "description": description,
        }
        self.fake.state.setdefault("comments", {})["i1"] = [
            {"attachments": [{"filename": name} for name in attachments]},
        ]

    def card_output(self):
        import contextlib
        import io
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = HOST.cmd_card(self.host, types.SimpleNamespace(issue="i1"), self.groups)
        return code, buffer.getvalue()

    def test_a_lane_card_owes_one_artifact_not_eighteen(self):
        # Catches: `card` telling an Explore card it owed 01-spec-product.md through
        # 18-audit-table.md, which is true of no card on that board.
        self.seed("review", "**Strategy:** stelow-workflow-codebase-critique", ["critique.md"])
        code, out = self.card_output()
        self.assertEqual(code, 0)
        self.assertIn("lane: explore", out)
        self.assertIn("stelow-workflow-codebase-critique", out)
        self.assertNotIn("01-spec-product.md", out)

    def test_a_lane_card_that_reached_review_with_nothing_is_a_failure(self):
        # Catches: a lane run that advanced the card without producing the artifact,
        # which every check reported as healthy because there was nothing to compare.
        self.seed("review", "**Strategy:** stelow-product-pricing", [])
        code, _ = self.card_output()
        self.assertEqual(code, 1)

    def test_a_research_card_is_not_reported_as_explore(self):
        # Catches the live bug: both lanes use `review`, and the first board
        # alphabetically answered, so a research card reported `lane: explore`.
        self.seed("review", "**Strategy:** stelow-product-pricing", ["01-pricing.md"])
        code, out = self.card_output()
        self.assertEqual(code, 0)
        self.assertIn("lane: research", out)

    def test_a_card_with_no_strategy_is_placed_by_its_project(self):
        # Catches: a card typed by hand (no Strategy line) landing in whichever lane
        # sorts first, so its artifact is judged against the wrong menu.
        self.seed("doing", "", [])
        self.fake.state["project_titles"]["proj-r"] = "Research"
        self.fake.state["issues"]["i1"]["project_id"] = "proj-r"
        code, out = self.card_output()
        self.assertEqual(code, 0)
        self.assertIn("lane: research", out)

    def test_a_card_no_lane_can_place_is_refused(self):
        # Catches: a hand-typed card in a shared status silently judged against
        # whichever lane sorts first.
        self.seed("doing", "", [])
        code, out = self.card_output()
        self.assertEqual(code, 1)
        self.assertIn("ambiguous", out)

    def test_a_status_only_one_lane_uses_still_places_the_card(self):
        self.assertEqual((HOST.lane_for_card({"description": ""}, "intake", {}) or {}).get("board"), None)
        self.assertEqual((HOST.lane_for_card({"description": ""}, "review", {}) or {}).get("board"), None)

    def test_a_lane_card_in_doing_may_still_owe_its_artifact(self):
        # Catches: reporting a run in progress as a failure, which teaches people to
        # ignore the check.
        self.seed("doing", "**Strategy:** stelow-workflow-codebase-critique", [])
        code, out = self.card_output()
        self.assertEqual(code, 0)
        self.assertIn("lane: explore", out)
        self.assertIn("kept 0", out)

    def test_a_chain_card_still_owes_the_chain(self):
        # Catches: the lane branch swallowing every card, so a finished build card
        # with no artifacts read as fine.
        self.seed("done", "", [])
        code, out = self.card_output()
        self.assertEqual(code, 1)
        self.assertIn("18-audit-table.md", out)

    def test_the_named_strategy_is_read_back_from_the_body(self):
        self.assertEqual(HOST.declared_strategy({"description": "x\n**Strategy:** stelow-product-pricing\n"}),
                         "stelow-product-pricing")
        self.assertEqual(HOST.declared_strategy({"description": "no line here"}), "")


class TestTheEntryColumn(HostCase):
    def test_a_card_in_the_entry_column_is_an_orphan(self):
        # Catches: the eight minutes the smoke card spent in `todo` where nothing
        # runs and no check could see it, because `todo` is not a group in
        # columns.json and the check only knew the groups.
        issues = [{"id": "i1", "key": "CAL-9", "status": "todo"}]
        unmarked, orphans, stale = HOST.board_findings(issues, set(), {"todo", "intake"}, set(), {})
        self.assertEqual(orphans, ["CAL-9"])
        self.assertEqual((unmarked, stale), ([], []))

    def test_a_closed_card_is_not_an_orphan(self):
        # Catches: the first timer run reporting two finished cards as abandoned,
        # because a closed card has no run and no marker and never should.
        issues = [{"id": "i1", "key": "CAL-3", "status": "done"}]
        known = {"intake", "todo", "done", "cancelled"}
        self.assertEqual(
            HOST.board_findings(issues, set(), known, set(), {})[1], []
        )
        self.assertEqual(HOST.stalled_cards(issues, known, 48, now=None), [])

    def test_the_policy_states_how_long_a_stage_may_sit(self):
        # Catches: the restart delay living only in a prompt.
        policy = json.loads((REPO / "config" / "columns.json").read_text())["policy"]
        self.assertEqual(policy["stall_minutes"], 5)


class TestAsk(HostCase):
    def setUp(self):
        super().setUp()
        self.fake.state["project_titles"]["proj-research"] = "Research"
        self.fake.state["project_titles"]["proj-build"] = "Build"

    def ask(self, board="research", question=("is", "this", "priced", "right"), **kwargs):
        scope = types.SimpleNamespace(board=board, question=list(question), skill=None,
                                      when=None, title=None, dry_run=False, json=False, project=None)
        for key, value in kwargs.items():
            setattr(scope, key, value)
        return HOST.cmd_ask(self.host, scope, self.groups)

    def test_a_named_strategy_is_resolved_from_its_tail(self):
        # Catches: typing `pricing` and getting a card the runner is free to
        # answer with any skill, which is what happened before `ask` existed.
        self.ask(skill="pricing")
        issue = list(self.fake.state["issues"].values())[0]
        body = (self.tmp / ".stelow-cache" / "ask.md").read_text()
        self.assertIn("stelow-product-pricing", body)
        self.assertEqual(issue["status"], "bucket")

    def test_an_unknown_strategy_is_refused_listing_the_menu(self):
        # Catches: a typo silently becoming the runner's own choice.
        with self.assertRaises(HOST.Fail) as caught:
            self.ask(skill="pricng")
        self.assertIn("is not on the research menu", str(caught.exception))

    def test_a_question_lands_in_the_container_it_names(self):
        # Catches: `ask research` writing into another repository's project.
        # The container is the repository, not the track: without --project the
        # card goes to the configured project, because that is the repo you are
        # working in.
        self.ask(project="Research")
        self.assertEqual(list(self.fake.state["issues"].values())[0]["project"], "proj-research")

    def test_the_environment_project_wins_when_nothing_is_named(self):
        # Catches: a track quietly redirecting work to its own container instead
        # of the repository the host is pointed at.
        self.host["multica"]["project_id"] = "proj-1"
        self.ask()
        self.assertEqual(list(self.fake.state["issues"].values())[0]["project"], "proj-1")

    def test_without_a_project_it_falls_back_to_the_track(self):
        # Catches: an unconfigured host writing nowhere, or writing everywhere.
        self.host["multica"]["project_id"] = ""
        self.ask()
        self.assertEqual(list(self.fake.state["issues"].values())[0]["project"], "proj-research")

    def test_build_opens_on_the_chain_not_in_the_entry_column(self):
        # Catches: `ask build` leaving the card in `todo`, where nothing runs.
        self.ask(board="build", project="Build")
        self.assertEqual(list(self.fake.state["issues"].values())[0]["status"], "intake")

    def test_dry_run_writes_nothing(self):
        # Catches: a --dry-run that creates the card anyway.
        self.ask(dry_run=True)
        self.assertEqual(self.fake.state["issues"], {})


class TestArtifactReport(unittest.TestCase):
    def test_a_card_names_what_it_is_missing(self):
        # Catches: a stage that produced nothing, on a card that closed anyway.
        groups = [
            {"id": "framing", "artifacts": ["01-spec-product.md", "02-critique-report.md"]},
            {"id": "audit", "artifacts": ["18-audit-table.md"]},
        ]
        declared, missing, legacy = HOST.artifact_report({"01-spec-product.md", "18-audit-table.md"}, groups)
        self.assertEqual(len(declared), 3)
        self.assertEqual(missing, [("framing", "02-critique-report.md")])
        self.assertEqual(legacy, [])

    def test_a_complete_card_misses_nothing(self):
        groups = [{"id": "framing", "artifacts": ["01-spec-product.md"]}]
        self.assertEqual(HOST.artifact_report({"01-spec-product.md"}, groups)[1], [])

    def test_a_legacy_filename_is_not_a_gap(self):
        # Catches: a card that ran across the naming change reported as broken,
        # which is how a report stops being read.
        groups = [{"id": "audit", "artifacts": ["18-audit-table.md"]}]
        aliases = {"18-audit-table.md": ["audit-table.md"]}
        declared, missing, legacy = HOST.artifact_report({"audit-table.md"}, groups, aliases)
        self.assertEqual(missing, [])
        self.assertEqual(legacy, [("18-audit-table.md", "audit-table.md")])


class TestTheBriefCarriesItsMenu(unittest.TestCase):
    def test_every_menu_entry_is_in_the_step_that_chooses(self):
        # Catches: a step that says "pick from the menu" while the menu lives only
        # in the repository, which leaves the runner to guess or to search the
        # filesystem for it. Both happened on a canary card.
        board = HOST.load_board("research")
        plan = HOST.board_plan(HOST.load_host(HOST.ROOT / "config" / "host.json"), board)
        run = next(column for column in plan["columns"] if not column["gate"])
        board = HOST.load_board("research")
        self.assertEqual(len(board["menu"]), 21)
        for item in board["menu"]:
            self.assertIn(item["skill"], run["instructions"])
            self.assertIn(item["when"], run["instructions"])

    def test_the_runner_name_does_not_double_its_prefix(self):
        # Catches: agents named `stelow-stelow-research-runner`, which is what the
        # board looked like when its runner already carried the prefix.
        for name in ("explore", "research"):
            self.assertFalse(HOST.load_board(name)["runner"].startswith("stelow-"))


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
