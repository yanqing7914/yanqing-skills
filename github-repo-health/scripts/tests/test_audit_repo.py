import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "audit_repo.py"
SPEC = importlib.util.spec_from_file_location("audit_repo", SCRIPT)
audit_repo = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(audit_repo)


class AuditRepoTests(unittest.TestCase):
    def make_repo(self, files: dict[str, str], tracked: tuple[str, ...] = ()) -> Path:
        directory = Path(tempfile.mkdtemp())
        for name, content in files.items():
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        if tracked:
            subprocess.run(["git", "init", "-q"], cwd=directory, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=directory, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=directory, check=True)
            subprocess.run(["git", "add", *tracked], cwd=directory, check=True)
            subprocess.run(["git", "commit", "-qm", "fixture"], cwd=directory, check=True)
        return directory

    @staticmethod
    def titles(result):
        return [item["title"] for item in result["findings"]]

    def test_digest_pinning_supports_multistage_and_build_args(self):
        digest = "a" * 64
        root = self.make_repo(
            {"Dockerfile": f"FROM --platform=linux/amd64 python:3.12@sha256:{digest} AS build\nFROM alpine@sha256:{digest}\nUSER app\nHEALTHCHECK CMD true\n"},
            ("Dockerfile",),
        )
        result = audit_repo.audit(root)
        self.assertNotIn("Docker base image is not digest-pinned", self.titles(result))
        self.assertNotIn("Docker image does not declare a non-root user", self.titles(result))

    def test_root_user_is_not_accepted_and_comments_do_not_count(self):
        root = self.make_repo(
            {"Dockerfile": "# USER nobody\nFROM python:3.12\nUSER root\n"},
            ("Dockerfile",),
        )
        result = audit_repo.audit(root)
        titles = self.titles(result)
        self.assertIn("Docker base image is not digest-pinned", titles)
        self.assertIn("Docker image does not declare a non-root user", titles)

    def test_final_stage_does_not_inherit_user_from_build_stage(self):
        digest = "b" * 64
        root = self.make_repo(
            {
                "Dockerfile": (
                    f"FROM builder@sha256:{digest} AS build\n"
                    "USER builder\n"
                    f"FROM runtime@sha256:{digest}\n"
                )
            },
            ("Dockerfile",),
        )
        result = audit_repo.audit(root)
        self.assertIn("Docker image does not declare a non-root user", self.titles(result))

    def test_unpinned_action_and_realistic_secret_are_reported(self):
        secret = "github_pat_" + "A" * 82
        root = self.make_repo(
            {
                ".github/workflows/ci.yml": (
                    "name: CI\n"
                    "on: [push]\n"
                    "jobs:\n"
                    "  test:\n"
                    "    runs-on: ubuntu-latest\n"
                    "    steps:\n"
                    "      - name: Checkout\n"
                    "        uses: actions/checkout@v4\n"
                    f"      - run: echo {secret}\n"
                )
            },
            (".github/workflows/ci.yml",),
        )
        result = audit_repo.audit(root)
        titles = self.titles(result)
        self.assertIn("At least one Action is not pinned", titles)
        self.assertIn("Possible credential material is tracked", titles)

    def test_only_tracked_files_are_scanned_for_docker_and_secrets(self):
        root = self.make_repo(
            {
                "README.md": "tracked\n",
                "notes.md": "ghp_" + "A" * 40,
                "Dockerfile": "FROM python:3.12\n",
            },
            ("README.md",),
        )
        result = audit_repo.audit(root)
        titles = self.titles(result)
        self.assertNotIn("Docker base image is not digest-pinned", titles)
        self.assertNotIn("Possible credential material is tracked", titles)
        self.assertIn("1 tracked file(s) inspected", result["positive_checks"])

    def test_only_tracked_workflows_are_audited(self):
        root = self.make_repo(
            {"README.md": "tracked\n", ".github/workflows/ci.yml": "uses: actions/checkout@v4\n"},
            ("README.md",),
        )
        result = audit_repo.audit(root)
        self.assertEqual(result["workflow_count"], 0)
        self.assertNotIn("At least one Action is not pinned", self.titles(result))

    def test_docker_container_actions_are_not_treated_as_unpinned_third_party_actions(self):
        root = self.make_repo(
            {
                ".github/workflows/ci.yml": (
                    "name: CI\n"
                    "permissions: {}\n"
                    "on: [push]\n"
                    "jobs:\n"
                    "  test:\n"
                    "    runs-on: ubuntu-latest\n"
                    "    steps:\n"
                    "      - uses: docker://alpine:3.20\n"
                )
            },
            (".github/workflows/ci.yml",),
        )
        result = audit_repo.audit(root)
        self.assertNotIn("At least one Action is not pinned", self.titles(result))

    def test_multiline_healthcheck_is_parsed_and_none_disables_check(self):
        digest = "c" * 64
        root = self.make_repo(
            {
                "Dockerfile": (
                    f"FROM runtime@sha256:{digest}\n"
                    "USER app\n"
                    "HEALTHCHECK --interval=30s \\\n+"
                    "  CMD wget --spider http://127.0.0.1:8080/health\n"
                )
            },
            ("Dockerfile",),
        )
        result = audit_repo.audit(root)
        self.assertNotIn("Docker image has no HEALTHCHECK", self.titles(result))

        (root / "Dockerfile").write_text(
            f"FROM runtime@sha256:{digest}\nUSER app\nHEALTHCHECK NONE\n",
            encoding="utf-8",
        )
        result = audit_repo.audit(root)
        self.assertIn("Docker image has no HEALTHCHECK", self.titles(result))


if __name__ == "__main__":
    unittest.main()
