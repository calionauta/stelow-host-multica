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
import shutil
import tempfile
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LOADER = importlib.machinery.SourceFileLoader("stelow_host", str(REPO / "bin" / "stelow-host"))
SPEC = importlib.util.spec_from_loader("stelow_host", LOADER)
HOST = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(HOST)

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

    def write_stages(self, intents=INTENTS):
        text = stages_yaml(intents)
        cache = self.tmp / ".stelow-cache" / "stages.yaml"
        cache.write_text(text, encoding="utf-8")
        (self.tmp / "stelow.lock.json").write_text(json.dumps({
            "repo": self.host_repo(),
            "ref": self.host_ref(),
            "stages_sha256": hashlib.sha256(text.encode()).hexdigest(),
        }), encoding="utf-8")

    def host_repo(self):
        return json.loads((self.tmp / "config" / "host.json").read_text())["stelow"]["repo"]

    def host_ref(self):
        return json.loads((self.tmp / "config" / "host.json").read_text())["stelow"]["ref"]

    def args(self, intent="feature", gates="human", project="proj-1", migrate=False, refresh=False):
        return types.SimpleNamespace(intent=intent, gates=gates, project=project,
                                     migrate=migrate, refresh_skills=refresh, json=False)

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

    def test_agent_gates_hand_the_step_to_the_gatekeeper(self):
        """Without this the --gates agent mode would leave gates to a stage agent."""
        self.apply(gates="agent")
        gatekeeper = self.fp().state["agents"]["stelow-gatekeeper"]
        steps = {s["status_key"]: s for s in self.fp().state["workflows"]["stelow-feature"]}
        for gate in ("product_gate", "interface_gate", "tech_gate", "diff_gate"):
            self.assertEqual(steps[gate]["handler"], {"type": "agent", "id": gatekeeper}, gate)

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
        self.assertEqual(len(fake.state["agent_skills"]["stelow-build"]), 3)

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


class TestVerify(HostCase):
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
