"""Unit tests for DiffGenerator."""

from pathlib import Path

import pytest

from secuority.models.config import ConfigChange
from secuority.models.interfaces import ChangeType
from secuority.utils.diff import DiffGenerator


class TestDiffGenerator:
    """Test DiffGenerator functionality."""

    @pytest.fixture
    def diff_generator(self) -> DiffGenerator:
        """Create DiffGenerator instance."""
        return DiffGenerator(context_lines=3)

    @pytest.fixture
    def old_content(self) -> str:
        """Sample old content."""
        return """line 1
line 2
line 3
line 4
line 5
"""

    @pytest.fixture
    def new_content(self) -> str:
        """Sample new content with changes."""
        return """line 1
line 2 modified
line 3
line 4
line 5
line 6 added
"""

    def test_generate_unified_diff(
        self,
        diff_generator: DiffGenerator,
        old_content: str,
        new_content: str,
    ) -> None:
        """Test generating unified diff."""
        diff = diff_generator.generate_unified_diff(
            old_content,
            new_content,
            Path("test.txt"),
        )

        assert "---" in diff
        assert "+++" in diff
        assert "@@" in diff
        assert "-line 2" in diff
        assert "+line 2 modified" in diff
        assert "+line 6 added" in diff

    def test_generate_unified_diff_with_custom_labels(
        self,
        diff_generator: DiffGenerator,
        old_content: str,
        new_content: str,
    ) -> None:
        """Test generating unified diff with custom labels."""
        diff = diff_generator.generate_unified_diff(
            old_content,
            new_content,
            Path("test.txt"),
            old_label="original",
            new_label="modified",
        )

        assert "--- original" in diff
        assert "+++ modified" in diff

    def test_generate_side_by_side_diff(
        self,
        diff_generator: DiffGenerator,
        old_content: str,
        new_content: str,
    ) -> None:
        """Test generating side-by-side diff."""
        diff = diff_generator.generate_side_by_side_diff(
            old_content,
            new_content,
            width=80,
        )

        # Currently returns unified diff
        assert "---" in diff or "line" in diff

    def test_generate_change_summary_with_old_content(
        self,
        diff_generator: DiffGenerator,
        old_content: str,
        new_content: str,
    ) -> None:
        """Test generating change summary with old content."""
        change = ConfigChange.merge_file_change(
            file_path=Path("test.txt"),
            old_content=old_content,
            new_content=new_content,
            description="Test change",
            conflicts=[],
        )

        summary = diff_generator.generate_change_summary(change)

        assert "File: test.txt" in summary
        assert "Change Type: Merge" in summary
        assert "Description: Test change" in summary
        assert "Changes:" in summary

    def test_generate_change_summary_new_file(
        self,
        diff_generator: DiffGenerator,
        new_content: str,
    ) -> None:
        """Test generating change summary for new file."""
        change = ConfigChange.create_file_change(
            file_path=Path("new.txt"),
            content=new_content,
            description="Create new file",
        )

        summary = diff_generator.generate_change_summary(change)

        assert "File: new.txt" in summary
        assert "Change Type: Create" in summary
        assert "New file content (preview):" in summary

    def test_generate_conflict_diff(
        self,
        diff_generator: DiffGenerator,
    ) -> None:
        """Test generating conflict diff."""
        existing_value = "value1"
        template_value = "value2"

        diff = diff_generator.generate_conflict_diff(
            existing_value,
            template_value,
            "config.section",
        )

        assert "existing [config.section]" in diff
        assert "template [config.section]" in diff

    def test_get_diff_stats(
        self,
        diff_generator: DiffGenerator,
        old_content: str,
        new_content: str,
    ) -> None:
        """Test getting diff statistics."""
        stats = diff_generator.get_diff_stats(old_content, new_content)

        assert "total_old_lines" in stats
        assert "total_new_lines" in stats
        assert "additions" in stats
        assert "deletions" in stats
        assert "modifications" in stats
        assert "similarity_ratio" in stats

        assert stats["total_old_lines"] == 5
        assert stats["total_new_lines"] == 6
        assert stats["additions"] > 0
        assert stats["modifications"] > 0
        assert 0 <= stats["similarity_ratio"] <= 1

    def test_get_diff_stats_identical_content(
        self,
        diff_generator: DiffGenerator,
        old_content: str,
    ) -> None:
        """Test diff stats for identical content."""
        stats = diff_generator.get_diff_stats(old_content, old_content)

        assert stats["additions"] == 0
        assert stats["deletions"] == 0
        assert stats["modifications"] == 0
        assert stats["similarity_ratio"] == 1.0

    def test_format_diff_for_display(
        self,
        diff_generator: DiffGenerator,
    ) -> None:
        """Test formatting diff for display."""
        diff = """--- a/test.txt
+++ b/test.txt
@@ -1,3 +1,3 @@
 line 1
-line 2
+line 2 modified
 line 3
"""

        formatted = diff_generator.format_diff_for_display(diff, max_width=80)

        assert "---" in formatted
        assert "+++" in formatted
        assert "line 2 modified" in formatted

    def test_format_diff_for_display_long_lines(
        self,
        diff_generator: DiffGenerator,
    ) -> None:
        """Test formatting diff with long lines."""
        long_line = "+" + "x" * 150
        diff = f"""--- a/test.txt
+++ b/test.txt
@@ -1,1 +1,1 @@
{long_line}
"""

        formatted = diff_generator.format_diff_for_display(diff, max_width=80)

        # Long lines should be wrapped or truncated
        lines = formatted.splitlines()
        for line in lines:
            if not line.startswith(("+++", "---", "@@")):
                assert len(line) <= 80

    def test_highlight_changes(
        self,
        diff_generator: DiffGenerator,
    ) -> None:
        """Test highlighting diff changes."""
        diff = """--- a/test.txt
+++ b/test.txt
@@ -1,3 +1,3 @@
 line 1
-line 2
+line 2 modified
 line 3
"""

        highlighted = diff_generator.highlight_changes(diff)

        # Should contain ANSI color codes
        assert "\033[" in highlighted
        assert "\033[0m" in highlighted  # Reset code

    def test_highlight_changes_additions(
        self,
        diff_generator: DiffGenerator,
    ) -> None:
        """Test highlighting additions."""
        diff = "+added line"

        highlighted = diff_generator.highlight_changes(diff)

        # Green color for additions
        assert "\033[32m" in highlighted

    def test_highlight_changes_deletions(
        self,
        diff_generator: DiffGenerator,
    ) -> None:
        """Test highlighting deletions."""
        diff = "-deleted line"

        highlighted = diff_generator.highlight_changes(diff)

        # Red color for deletions
        assert "\033[31m" in highlighted

    def test_highlight_changes_headers(
        self,
        diff_generator: DiffGenerator,
    ) -> None:
        """Test highlighting diff headers."""
        diff = """--- a/test.txt
+++ b/test.txt
@@ -1,1 +1,1 @@
"""

        highlighted = diff_generator.highlight_changes(diff)

        # Cyan color for headers
        assert "\033[36m" in highlighted

    def test_diff_generator_custom_context_lines(self) -> None:
        """Test DiffGenerator with custom context lines."""
        generator = DiffGenerator(context_lines=5)

        assert generator.context_lines == 5

    def test_generate_unified_diff_empty_content(
        self,
        diff_generator: DiffGenerator,
    ) -> None:
        """Test generating diff with empty content."""
        diff = diff_generator.generate_unified_diff(
            "",
            "new content",
            Path("test.txt"),
        )

        assert "+new content" in diff

    def test_generate_unified_diff_no_changes(
        self,
        diff_generator: DiffGenerator,
        old_content: str,
    ) -> None:
        """Test generating diff with no changes."""
        diff = diff_generator.generate_unified_diff(
            old_content,
            old_content,
            Path("test.txt"),
        )

        # No diff output for identical content
        assert diff == ""

    def test_generate_conflict_diff_with_complex_values(
        self,
        diff_generator: DiffGenerator,
    ) -> None:
        """Test generating conflict diff with complex values."""
        existing_value = {"key1": "value1", "key2": "value2"}
        template_value = {"key1": "value1", "key2": "modified"}

        diff = diff_generator.generate_conflict_diff(
            str(existing_value),
            str(template_value),
            "config.section",
        )

        assert "config.section" in diff

    def test_get_diff_stats_only_additions(
        self,
        diff_generator: DiffGenerator,
    ) -> None:
        """Test diff stats with only additions."""
        old_content = "line 1\nline 2\n"
        new_content = "line 1\nline 2\nline 3\nline 4\n"

        stats = diff_generator.get_diff_stats(old_content, new_content)

        assert stats["additions"] > 0
        assert stats["deletions"] == 0

    def test_get_diff_stats_only_deletions(
        self,
        diff_generator: DiffGenerator,
    ) -> None:
        """Test diff stats with only deletions."""
        old_content = "line 1\nline 2\nline 3\nline 4\n"
        new_content = "line 1\nline 2\n"

        stats = diff_generator.get_diff_stats(old_content, new_content)

        assert stats["additions"] == 0
        assert stats["deletions"] > 0

    def test_format_diff_for_display_preserves_prefixes(
        self,
        diff_generator: DiffGenerator,
    ) -> None:
        """Test that formatting preserves diff prefixes."""
        diff = "+added line\n-deleted line\n context line"

        formatted = diff_generator.format_diff_for_display(diff, max_width=80)

        assert "+added line" in formatted
        assert "-deleted line" in formatted
        assert " context line" in formatted
