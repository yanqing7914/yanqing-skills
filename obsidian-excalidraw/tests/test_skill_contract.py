import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
CLI = SKILL_DIR / "scripts" / "excalidraw.mjs"
FIXTURE = SKILL_DIR / "tests" / "fixtures" / "runtime-flow.excalidraw.md"
CONTRACT = SKILL_DIR / "tests" / "skill_contract.json"
CREATOR_VALIDATE = Path.home() / ".agents" / "skills" / "skill-creator" / "scripts" / "quick_validate.py"
NODE = shutil.which("node")
NODE_READY = NODE is not None and (SKILL_DIR / "scripts" / "node_modules" / "lz-string").is_dir()

SPEC = {
    "title": "Test flow",
    "nodes": [
        {"id": "req", "label": "需求", "kind": "process"},
        {"id": "gate", "label": "需要发布?", "kind": "decision"},
        {"id": "rel", "label": "发布"},
        {"id": "done", "label": "完成", "kind": "terminal"},
    ],
    "edges": [
        {"from": "req", "to": "gate"},
        {"from": "gate", "to": "rel", "label": "是"},
        {"from": "gate", "to": "done", "label": "否"},
        {"from": "rel", "to": "done"},
        {"from": "rel", "to": "req", "label": "返工", "style": "rework"},
    ],
}


def run(*args):
    return subprocess.run([NODE, str(CLI), *map(str, args)], capture_output=True, text=True, check=False)


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_contract_schema(self):
        c = self.contract
        self.assertEqual(c["schema_version"], 1)
        self.assertEqual(c["skill"], "obsidian-excalidraw")
        self.assertEqual(set(c["sections"]), {"routing", "behavior", "completion"})
        kinds = [r["kind"] for r in c["sections"]["routing"]]
        self.assertGreaterEqual(kinds.count("positive"), 3)
        self.assertGreaterEqual(kinds.count("nonstandard_positive"), 2)
        self.assertGreaterEqual(kinds.count("negative"), 2)
        self.assertGreaterEqual(kinds.count("adjacent"), 2)
        self.assertEqual(
            {b["kind"] for b in c["sections"]["behavior"]},
            {"success", "invalid_input", "tool_or_permission_failure", "idempotence"},
        )
        for item in c["sections"]["completion"]:
            self.assertTrue(item["artifact"])
            self.assertTrue(item["assertions"])
        for rel in c["source_of_truth"]:
            self.assertTrue((SKILL_DIR / rel).is_file(), rel)

    def test_evidence_tests_exist(self):
        source = Path(__file__).read_text(encoding="utf-8")
        for section in self.contract["sections"].values():
            for item in section:
                for ev in item.get("evidence", []):
                    m = re.match(r"tests/test_skill_contract\.py::(\w+)", ev)
                    if m:
                        self.assertIn(f"def {m.group(1)}(", source, ev)

    def test_gotcha_assertions_exist(self):
        source = Path(__file__).read_text(encoding="utf-8")
        gotchas = (SKILL_DIR / "references" / "gotchas.md").read_text(encoding="utf-8")
        names = set(re.findall(r"`(test_\w+)`", gotchas))
        self.assertTrue(names)
        for name in names:
            self.assertIn(f"def {name}(", source, name)

    def test_boundaries(self):
        ids = {r["id"] for r in self.contract["sections"]["routing"] if r["kind"] in ("negative", "adjacent")}
        self.assertTrue({"neg-plain-note", "neg-mermaid", "adj-lark-whiteboard", "adj-vault-manager"} <= ids)
        text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        for word in ("obsidian-vault", "lark-whiteboard", "visualize", "--force"):
            self.assertIn(word, text)

    def test_markdown_links_resolve(self):
        for md in [SKILL_DIR / "SKILL.md", *(SKILL_DIR / "references").glob("*.md")]:
            for target in re.findall(r"\]\(([^)\s]+)\)", md.read_text(encoding="utf-8")):
                if target.startswith(("http://", "https://")):
                    continue
                path = target.split("#", 1)[0]
                if path:
                    self.assertTrue((md.parent / path).exists(), f"{md.name}: {target}")

    @unittest.skipUnless(CREATOR_VALIDATE.is_file(), "skill-creator not installed")
    def test_creator_require_contract(self):
        r = subprocess.run(
            ["python3", str(CREATOR_VALIDATE), "--require-contract", str(SKILL_DIR)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


@unittest.skipUnless(NODE_READY, "node or scripts/node_modules missing; run npm ci --no-bin-links in scripts/")
class CliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def decode(self, path):
        r = run("decode", path)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def encode(self, scene, header_from=FIXTURE):
        scene_path = self.tmp / "scene.json"
        out = self.tmp / "out.excalidraw.md"
        scene_path.write_text(json.dumps(scene), encoding="utf-8")
        r = run("encode", scene_path, out, "--header-from", header_from, "--force")
        self.assertEqual(r.returncode, 0, r.stderr)
        return out

    def write_spec(self, spec=SPEC, name="spec.json"):
        p = self.tmp / name
        p.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        return p

    def test_usage_exit_2(self):
        self.assertEqual(run().returncode, 2)
        self.assertEqual(run("bogus").returncode, 2)

    def test_validate_fixture_idempotent(self):
        a, b = run("validate", FIXTURE), run("validate", FIXTURE)
        self.assertEqual(a.returncode, 0, a.stdout + a.stderr)
        self.assertIn("OK ", a.stdout)
        self.assertEqual(a.stdout, b.stdout)

    def test_decode_encode_roundtrip(self):
        scene = self.decode(FIXTURE)
        out = self.encode(scene)
        self.assertEqual(self.decode(out), scene)
        self.assertEqual(run("validate", out).returncode, 0)

    def test_broken_binding_fails(self):
        scene = self.decode(FIXTURE)
        by_id = {e["id"]: e for e in scene["elements"]}
        arrow = next(e for e in scene["elements"] if e["type"] == "arrow" and e.get("endBinding"))
        target = by_id[arrow["endBinding"]["elementId"]]
        target["boundElements"] = [b for b in target["boundElements"] if b["id"] != arrow["id"]]
        r = run("validate", self.encode(scene))
        self.assertEqual(r.returncode, 1)
        self.assertIn("one-way", r.stdout + r.stderr)

    def test_stale_text_section_fails(self):
        text = FIXTURE.read_text(encoding="utf-8")
        m = re.search(r"^(.+?) \^(\S+)$", text, re.M)
        self.assertIsNotNone(m)
        broken = text.replace(m.group(0), f"{m.group(1)}XYZ ^{m.group(2)}", 1)
        p = self.tmp / "stale.excalidraw.md"
        p.write_text(broken, encoding="utf-8")
        r = run("validate", p)
        self.assertEqual(r.returncode, 1)
        self.assertIn("stale", r.stdout + r.stderr)

    def test_absolute_points_fail(self):
        scene = self.decode(FIXTURE)
        arrow = next(e for e in scene["elements"] if e["type"] == "arrow")
        arrow["points"] = [[arrow["x"], arrow["y"]], *arrow["points"][1:]]
        r = run("validate", self.encode(scene))
        self.assertEqual(r.returncode, 1)
        self.assertIn("points[0] must be [0,0]", r.stdout + r.stderr)

    def test_layout_strict_valid(self):
        out = self.tmp / "flow.excalidraw.md"
        r = run("layout", self.write_spec(), out, "--tags", "excalidraw,test")
        self.assertEqual(r.returncode, 0, r.stderr)
        v = run("validate", out, "--strict")
        self.assertEqual(v.returncode, 0, v.stdout + v.stderr)
        scene = self.decode(out)
        ids = {e["id"] for e in scene["elements"]}
        self.assertTrue({"req", "gate", "rel", "done", "req-t", "title"} <= ids)
        self.assertEqual(sum(e["type"] == "arrow" for e in scene["elements"]), len(SPEC["edges"]))

    def test_layout_deterministic(self):
        spec = self.write_spec()
        a, b = self.tmp / "a.excalidraw.md", self.tmp / "b.excalidraw.md"
        self.assertEqual(run("layout", spec, a, "--tags", "excalidraw,test").returncode, 0)
        self.assertEqual(run("layout", spec, b, "--tags", "excalidraw,test").returncode, 0)
        self.assertEqual(a.read_bytes(), b.read_bytes())

    def test_layout_refuses_overwrite(self):
        out = self.tmp / "flow.excalidraw.md"
        out.write_text("keep me", encoding="utf-8")
        r = run("layout", self.write_spec(), out)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--force", r.stderr + r.stdout)
        self.assertEqual(out.read_text(encoding="utf-8"), "keep me")
        self.assertEqual(run("layout", self.write_spec(), out, "--force").returncode, 0)

    def test_bad_layout_spec_exit_2(self):
        cases = [
            ({"nodes": []}, "nodes"),
            ({"nodes": [{"id": "a"}], "edges": []}, "id and label"),
            ({"nodes": [{"id": "a", "label": "A"}, {"id": "a", "label": "B"}], "edges": []}, "duplicate node id"),
            ({"nodes": [{"id": "a", "label": "A"}], "edges": [{"from": "a", "to": "z"}]}, "unknown node"),
            ({"nodes": [{"id": "a", "label": "A", "kind": "hexagon"}], "edges": []}, "unknown node kind"),
        ]
        for i, (spec, msg) in enumerate(cases):
            r = run("layout", self.write_spec(spec, f"bad{i}.json"), self.tmp / f"bad{i}.excalidraw.md")
            self.assertEqual(r.returncode, 2, spec)
            self.assertIn(msg, r.stderr + r.stdout)
            self.assertFalse((self.tmp / f"bad{i}.excalidraw.md").exists())


if __name__ == "__main__":
    unittest.main()
