"""Unit tests for UserApprovalInterface."""

from pathlib import Path
from unittest.mock import patch

import pytest

from secuority.models.config import ConfigChange, Conflict, ConflictResolution
from secuority.utils.user_interface import UserApprovalInterface


class TestUserApprovalInterface:
    """Test UserApprovalInterface functionality."""

    @pytest.fixture
    def ui(self) -> UserApprovalInterface:
        """Create UserApprovalInterface instance."""
        return UserApprovalInterface()

    @pytest.fixture
    def sample_change(self) -> ConfigChange:
        """Sample configuration change."""
        return ConfigChange.merge_file_change(
            file_path=Path("test.txt"),
            old_content="old content\n",
            new_content="new content\n",
            description="Test change",
            conflicts=[],
        )

    @pytest.fixture
    def sample_conflict(self) -> Conflict:
        """Sample conflict."""
        return Conflict(
            file_path=Path("config.yaml"),
            section="section.key",
            existing_value="value1",
            template_value="value2",
            description="Test conflict",
        )

    def test_get_change_approval_yes(
        self,
        ui: UserApprovalInterface,
        sample_change: ConfigChange,
    ) -> None:
        """Test approving a change."""
        with patch("builtins.input", return_value="y"):
            result = ui.get_change_approval(sample_change)

        assert result is True

    def test_get_change_approval_no(
        self,
        ui: UserApprovalInterface,
        sample_change: ConfigChange,
    ) -> None:
        """Test rejecting a change."""
        with patch("builtins.input", return_value="n"):
            result = ui.get_change_approval(sample_change)

        assert result is False

    def test_get_change_approval_with_conflicts(
        self,
        ui: UserApprovalInterface,
    ) -> None:
        """Test that changes with conflicts are automatically rejected."""
        change = ConfigChange.merge_file_change(
            file_path=Path("test.txt"),
            old_content="old",
            new_content="new",
            description="Test",
            conflicts=[
                Conflict(
                    file_path=Path("test.txt"),
                    section="section",
                    existing_value="val1",
                    template_value="val2",
                    description="conflict",
                ),
            ],
        )

        result = ui.get_change_approval(change)

        assert result is False

    def test_get_change_approval_show_content(
        self,
        ui: UserApprovalInterface,
        sample_change: ConfigChange,
    ) -> None:
        """Test showing full content before approval."""
        with patch("builtins.input", side_effect=["s", "y"]):
            result = ui.get_change_approval(sample_change)

        assert result is True

    def test_get_change_approval_quit(
        self,
        ui: UserApprovalInterface,
        sample_change: ConfigChange,
    ) -> None:
        """Test quitting during approval."""
        with patch("builtins.input", return_value="q"), pytest.raises(SystemExit):
            ui.get_change_approval(sample_change)

    def test_get_change_approval_invalid_then_valid(
        self,
        ui: UserApprovalInterface,
        sample_change: ConfigChange,
    ) -> None:
        """Test invalid input followed by valid input."""
        with patch("builtins.input", side_effect=["invalid", "y"]):
            result = ui.get_change_approval(sample_change)

        assert result is True

    def test_get_change_approval_new_file(
        self,
        ui: UserApprovalInterface,
    ) -> None:
        """Test approving a new file creation."""
        change = ConfigChange.create_file_change(
            file_path=Path("new.txt"),
            content="new file content\n" * 20,  # More than 15 lines
            description="Create new file",
        )

        with patch("builtins.input", return_value="y"):
            result = ui.get_change_approval(change)

        assert result is True

    def test_get_batch_approval_yes(
        self,
        ui: UserApprovalInterface,
        sample_change: ConfigChange,
    ) -> None:
        """Test batch approval with yes."""
        changes = [sample_change]

        with patch("builtins.input", return_value="y"):
            approvals = ui.get_batch_approval(changes)

        assert approvals[sample_change.file_path] is True

    def test_get_batch_approval_no(
        self,
        ui: UserApprovalInterface,
        sample_change: ConfigChange,
    ) -> None:
        """Test batch approval with no."""
        changes = [sample_change]

        with patch("builtins.input", return_value="n"):
            approvals = ui.get_batch_approval(changes)

        assert approvals[sample_change.file_path] is False

    def test_get_batch_approval_review_individually(
        self,
        ui: UserApprovalInterface,
        sample_change: ConfigChange,
    ) -> None:
        """Test reviewing changes individually."""
        changes = [sample_change]

        with patch("builtins.input", side_effect=["r", "y"]):
            approvals = ui.get_batch_approval(changes)

        assert approvals[sample_change.file_path] is True

    def test_get_batch_approval_quit(
        self,
        ui: UserApprovalInterface,
        sample_change: ConfigChange,
    ) -> None:
        """Test quitting during batch approval."""
        changes = [sample_change]

        with patch("builtins.input", return_value="q"), pytest.raises(SystemExit):
            ui.get_batch_approval(changes)

    def test_get_batch_approval_with_conflicts(
        self,
        ui: UserApprovalInterface,
    ) -> None:
        """Test batch approval with conflicted changes."""
        change_with_conflict = ConfigChange.merge_file_change(
            file_path=Path("test.txt"),
            old_content="old",
            new_content="new",
            description="Test",
            conflicts=[
                Conflict(
                    file_path=Path("test.txt"),
                    section="section",
                    existing_value="val1",
                    template_value="val2",
                    description="conflict",
                ),
            ],
        )

        changes = [change_with_conflict]

        with patch("builtins.input", return_value="y"):
            approvals = ui.get_batch_approval(changes)

        # Changes with conflicts should not be approved
        assert approvals[change_with_conflict.file_path] is False

    def test_resolve_conflicts_interactively_keep(
        self,
        ui: UserApprovalInterface,
        sample_conflict: Conflict,
    ) -> None:
        """Test resolving conflict by keeping existing."""
        with patch("builtins.input", return_value="k"):
            resolved = ui.resolve_conflicts_interactively([sample_conflict])

        assert len(resolved) == 1
        assert resolved[0].resolution == ConflictResolution.KEEP_EXISTING

    def test_resolve_conflicts_interactively_use_template(
        self,
        ui: UserApprovalInterface,
        sample_conflict: Conflict,
    ) -> None:
        """Test resolving conflict by using template."""
        with patch("builtins.input", return_value="u"):
            resolved = ui.resolve_conflicts_interactively([sample_conflict])

        assert len(resolved) == 1
        assert resolved[0].resolution == ConflictResolution.USE_TEMPLATE

    def test_resolve_conflicts_interactively_manual(
        self,
        ui: UserApprovalInterface,
        sample_conflict: Conflict,
    ) -> None:
        """Test resolving conflict manually."""
        with patch("builtins.input", return_value="m"):
            resolved = ui.resolve_conflicts_interactively([sample_conflict])

        assert len(resolved) == 1
        assert resolved[0].resolution == ConflictResolution.MANUAL

    def test_resolve_conflicts_interactively_skip(
        self,
        ui: UserApprovalInterface,
        sample_conflict: Conflict,
    ) -> None:
        """Test skipping conflict resolution."""
        with patch("builtins.input", return_value="s"):
            resolved = ui.resolve_conflicts_interactively([sample_conflict])

        assert len(resolved) == 1
        assert resolved[0].resolution == ConflictResolution.KEEP_EXISTING

    def test_resolve_conflicts_interactively_invalid_then_valid(
        self,
        ui: UserApprovalInterface,
        sample_conflict: Conflict,
    ) -> None:
        """Test invalid input followed by valid input."""
        with patch("builtins.input", side_effect=["invalid", "k"]):
            resolved = ui.resolve_conflicts_interactively([sample_conflict])

        assert len(resolved) == 1
        assert resolved[0].resolution == ConflictResolution.KEEP_EXISTING

    def test_resolve_conflicts_interactively_multiple(
        self,
        ui: UserApprovalInterface,
    ) -> None:
        """Test resolving multiple conflicts."""
        conflicts = [
            Conflict(
                file_path=Path("config1.yaml"),
                section="section1",
                existing_value="val1",
                template_value="val2",
                description="conflict 1",
            ),
            Conflict(
                file_path=Path("config2.yaml"),
                section="section2",
                existing_value="val3",
                template_value="val4",
                description="conflict 2",
            ),
        ]

        with patch("builtins.input", side_effect=["k", "u"]):
            resolved = ui.resolve_conflicts_interactively(conflicts)

        assert len(resolved) == 2
        assert resolved[0].resolution == ConflictResolution.KEEP_EXISTING
        assert resolved[1].resolution == ConflictResolution.USE_TEMPLATE

    def test_show_apply_summary(
        self,
        ui: UserApprovalInterface,
        sample_change: ConfigChange,
    ) -> None:
        """Test showing apply summary."""
        approved = [sample_change]
        rejected: list[ConfigChange] = []
        conflicted: list[ConfigChange] = []

        # Should not raise any exceptions
        ui.show_apply_summary(approved, rejected, conflicted)

    def test_show_apply_summary_with_all_types(
        self,
        ui: UserApprovalInterface,
    ) -> None:
        """Test showing apply summary with all change types."""
        approved = [
            ConfigChange.create_file_change(
                file_path=Path("new.txt"),
                content="content",
                description="new file",
            ),
        ]

        rejected = [
            ConfigChange.merge_file_change(
                file_path=Path("rejected.txt"),
                old_content="old",
                new_content="new",
                description="rejected",
                conflicts=[],
            ),
        ]

        conflicted = [
            ConfigChange.merge_file_change(
                file_path=Path("conflict.txt"),
                old_content="old",
                new_content="new",
                description="conflicted",
                conflicts=[
                    Conflict(
                        file_path=Path("conflict.txt"),
                        section="section",
                        existing_value="val1",
                        template_value="val2",
                        description="conflict",
                    ),
                ],
            ),
        ]

        # Should not raise any exceptions
        ui.show_apply_summary(approved, rejected, conflicted)

    def test_confirm_final_application_yes(
        self,
        ui: UserApprovalInterface,
        sample_change: ConfigChange,
    ) -> None:
        """Test confirming final application."""
        with patch("builtins.input", return_value="y"):
            result = ui.confirm_final_application([sample_change])

        assert result is True

    def test_confirm_final_application_no(
        self,
        ui: UserApprovalInterface,
        sample_change: ConfigChange,
    ) -> None:
        """Test rejecting final application."""
        with patch("builtins.input", return_value="n"):
            result = ui.confirm_final_application([sample_change])

        assert result is False

    def test_confirm_final_application_no_changes(
        self,
        ui: UserApprovalInterface,
    ) -> None:
        """Test confirming with no changes."""
        result = ui.confirm_final_application([])

        assert result is False

    def test_confirm_final_application_invalid_then_valid(
        self,
        ui: UserApprovalInterface,
        sample_change: ConfigChange,
    ) -> None:
        """Test invalid input followed by valid input."""
        with patch("builtins.input", side_effect=["invalid", "y"]):
            result = ui.confirm_final_application([sample_change])

        assert result is True

    def test_show_dry_run_results_no_changes(
        self,
        ui: UserApprovalInterface,
    ) -> None:
        """Test showing dry run results with no changes."""
        # Should not raise any exceptions
        ui.show_dry_run_results([])

    def test_show_dry_run_results_with_changes(
        self,
        ui: UserApprovalInterface,
        sample_change: ConfigChange,
    ) -> None:
        """Test showing dry run results with changes."""
        # Should not raise any exceptions
        ui.show_dry_run_results([sample_change])

    def test_show_dry_run_results_new_file(
        self,
        ui: UserApprovalInterface,
    ) -> None:
        """Test showing dry run results for new file."""
        change = ConfigChange.create_file_change(
            file_path=Path("new.txt"),
            content="new content\n",
            description="Create new file",
        )

        # Should not raise any exceptions
        ui.show_dry_run_results([change])

    def test_show_dry_run_results_with_conflicts(
        self,
        ui: UserApprovalInterface,
    ) -> None:
        """Test showing dry run results with conflicts."""
        change = ConfigChange.merge_file_change(
            file_path=Path("test.txt"),
            old_content="old",
            new_content="new",
            description="Test",
            conflicts=[
                Conflict(
                    file_path=Path("test.txt"),
                    section="section",
                    existing_value="val1",
                    template_value="val2",
                    description="conflict",
                ),
            ],
        )

        # Should not raise any exceptions
        ui.show_dry_run_results([change])

    def test_show_full_content(
        self,
        ui: UserApprovalInterface,
        sample_change: ConfigChange,
    ) -> None:
        """Test showing full content."""
        # Should not raise any exceptions
        ui._show_full_content(sample_change)

    def test_show_full_content_new_file(
        self,
        ui: UserApprovalInterface,
    ) -> None:
        """Test showing full content for new file."""
        change = ConfigChange.create_file_change(
            file_path=Path("new.txt"),
            content="new content\n",
            description="Create new file",
        )

        # Should not raise any exceptions
        ui._show_full_content(change)

    def test_resolve_conflicts_with_diff(
        self,
        ui: UserApprovalInterface,
    ) -> None:
        """Test resolving conflicts shows diff."""
        conflict = Conflict(
            file_path=Path("config.yaml"),
            section="section.key",
            existing_value="old value\nwith multiple lines",
            template_value="new value\nwith different lines",
            description="Test conflict with diff",
        )

        with patch("builtins.input", return_value="k"):
            resolved = ui.resolve_conflicts_interactively([conflict])

        assert len(resolved) == 1

    def test_get_batch_approval_invalid_then_valid(
        self,
        ui: UserApprovalInterface,
        sample_change: ConfigChange,
    ) -> None:
        """Test invalid input followed by valid input in batch approval."""
        changes = [sample_change]

        with patch("builtins.input", side_effect=["invalid", "y"]):
            approvals = ui.get_batch_approval(changes)

        assert approvals[sample_change.file_path] is True

    def test_confirm_final_application_with_backups(
        self,
        ui: UserApprovalInterface,
    ) -> None:
        """Test confirming application with backup changes."""
        change = ConfigChange.merge_file_change(
            file_path=Path("test.txt"),
            old_content="old content",
            new_content="new content",
            description="Test change with backup",
            conflicts=[],
        )

        with patch("builtins.input", return_value="y"):
            result = ui.confirm_final_application([change])

        assert result is True
