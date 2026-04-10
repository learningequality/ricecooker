"""Tests for curriculum nodes and learning objectives."""

import json
import re
import uuid

import pytest
from le_utils.constants import content_kinds
from le_utils.constants import licenses
from le_utils.constants import modalities

from ricecooker.classes.curriculum import LEARNING_OBJECTIVE_NAMESPACE
from ricecooker.classes.curriculum import LearningObjective
from ricecooker.classes.nodes import ChannelNode
from ricecooker.classes.nodes import CourseNode
from ricecooker.classes.nodes import LessonNode
from ricecooker.classes.nodes import TopicNode
from ricecooker.classes.nodes import UnitNode
from ricecooker.classes.nodes import VideoNode
from ricecooker.classes.questions import VARIANT_A
from ricecooker.classes.questions import VARIANT_B
from ricecooker.classes.questions import SingleSelectQuestion
from ricecooker.exceptions import InvalidNodeException


def make_question(question_id):
    """Helper to create a simple question for testing."""
    return SingleSelectQuestion(
        id=question_id,
        question="What is 1 + 1?",
        correct_answer="2",
        all_answers=["1", "2", "3", "4"],
    )


class TestLearningObjective:
    """Tests for the LearningObjective class."""

    def test_creates_with_text(self):
        """LearningObjective can be created with just text."""
        lo = LearningObjective("Understand addition")
        assert lo.text == "Understand addition"

    def test_generates_uuid5_from_text(self):
        """LearningObjective generates a deterministic UUID5 from text."""
        lo = LearningObjective("Understand addition")
        expected_id = uuid.uuid5(LEARNING_OBJECTIVE_NAMESPACE, "Understand addition").hex
        assert lo.id == expected_id

    def test_id_is_compact_hex_format(self):
        """LearningObjective ID must be compact hex (32 chars, no dashes) per le_utils schema."""
        lo = LearningObjective("Understand addition")
        # Must match le_utils schema pattern: ^[0-9a-f]{32}$
        assert re.match(r"^[0-9a-f]{32}$", lo.id), f"ID '{lo.id}' is not compact hex format"

    def test_same_text_produces_same_id(self):
        """Identical text produces identical IDs (deterministic)."""
        lo1 = LearningObjective("Understand addition")
        lo2 = LearningObjective("Understand addition")
        assert lo1.id == lo2.id

    def test_different_text_produces_different_id(self):
        """Different text produces different IDs."""
        lo1 = LearningObjective("Understand addition")
        lo2 = LearningObjective("Understand subtraction")
        assert lo1.id != lo2.id

    def test_metadata_defaults_to_empty_dict(self):
        """Metadata defaults to empty dict if not provided."""
        lo = LearningObjective("Understand addition")
        assert lo.metadata == {}

    def test_metadata_can_be_provided(self):
        """Metadata can be passed at construction."""
        metadata = {"difficulty": "easy", "grade": 3}
        lo = LearningObjective("Understand addition", metadata=metadata)
        assert lo.metadata == metadata

    def test_to_dict_returns_correct_structure(self):
        """to_dict returns the expected structure for serialization."""
        metadata = {"difficulty": "easy"}
        lo = LearningObjective("Understand addition", metadata=metadata)
        result = lo.to_dict()

        assert result["id"] == lo.id
        assert result["text"] == "Understand addition"
        assert result["metadata"] == metadata

    def test_rejects_empty_text(self):
        """LearningObjective raises ValueError for empty text."""
        with pytest.raises(ValueError, match="text must be non-empty"):
            LearningObjective("")

    def test_rejects_whitespace_only_text(self):
        """LearningObjective raises ValueError for whitespace-only text."""
        with pytest.raises(ValueError, match="text must be non-empty"):
            LearningObjective("   ")

    def test_rejects_none_text(self):
        """LearningObjective raises ValueError for None text."""
        with pytest.raises(ValueError, match="text must be non-empty"):
            LearningObjective(None)


class TestCourseNode:
    """Tests for the CourseNode class."""

    def test_creates_with_required_fields(self):
        """CourseNode can be created with source_id and title."""
        course = CourseNode(source_id="course-1", title="Math Course")
        assert course.title == "Math Course"
        assert course.source_id == "course-1"

    def test_sets_modality_to_course(self):
        """CourseNode sets modality to COURSE in extra_fields."""
        course = CourseNode(source_id="course-1", title="Math Course")
        assert course.extra_fields["options"]["modality"] == modalities.COURSE

    def test_kind_is_topic(self):
        """CourseNode has kind TOPIC (it's a subclass of TopicNode)."""
        course = CourseNode(source_id="course-1", title="Math Course")
        assert course.kind == content_kinds.TOPIC

    def test_accepts_unit_node_as_child(self):
        """CourseNode accepts UnitNode as child."""
        course = CourseNode(source_id="course-1", title="Math Course")
        unit = UnitNode(source_id="unit-1", title="Unit 1")
        course.add_child(unit)
        assert unit in course.children

    def test_rejects_topic_node_as_child(self):
        """CourseNode rejects TopicNode as child."""
        course = CourseNode(source_id="course-1", title="Math Course")
        topic = TopicNode(source_id="topic-1", title="Topic 1")
        with pytest.raises(InvalidNodeException):
            course.add_child(topic)

    def test_rejects_lesson_node_as_child(self):
        """CourseNode rejects LessonNode as direct child."""
        course = CourseNode(source_id="course-1", title="Math Course")
        lesson = LessonNode(source_id="lesson-1", title="Lesson 1")
        with pytest.raises(InvalidNodeException):
            course.add_child(lesson)

    def test_rejects_content_node_as_child(self):
        """CourseNode rejects ContentNode (e.g., VideoNode) as child."""
        course = CourseNode(source_id="course-1", title="Math Course")
        video = VideoNode(
            source_id="video-1",
            title="Video 1",
            license=licenses.PUBLIC_DOMAIN,
        )
        with pytest.raises(InvalidNodeException):
            course.add_child(video)


class TestLessonNode:
    """Tests for the LessonNode class."""

    def test_creates_with_required_fields(self):
        """LessonNode can be created with source_id and title."""
        lesson = LessonNode(source_id="lesson-1", title="Addition Lesson")
        assert lesson.title == "Addition Lesson"
        assert lesson.source_id == "lesson-1"

    def test_sets_modality_to_lesson(self):
        """LessonNode sets modality to LESSON in extra_fields."""
        lesson = LessonNode(source_id="lesson-1", title="Addition Lesson")
        assert lesson.extra_fields["options"]["modality"] == modalities.LESSON

    def test_kind_is_topic(self):
        """LessonNode has kind TOPIC (it's a subclass of TopicNode)."""
        lesson = LessonNode(source_id="lesson-1", title="Addition Lesson")
        assert lesson.kind == content_kinds.TOPIC

    def test_accepts_video_node_as_child(self):
        """LessonNode accepts VideoNode (ContentNode) as child."""
        lesson = LessonNode(source_id="lesson-1", title="Addition Lesson")
        video = VideoNode(
            source_id="video-1",
            title="Video 1",
            license=licenses.PUBLIC_DOMAIN,
        )
        lesson.add_child(video)
        assert video in lesson.children

    def test_rejects_topic_node_as_child(self):
        """LessonNode rejects TopicNode as child."""
        lesson = LessonNode(source_id="lesson-1", title="Addition Lesson")
        topic = TopicNode(source_id="topic-1", title="Topic 1")
        with pytest.raises(InvalidNodeException):
            lesson.add_child(topic)

    def test_rejects_unit_node_as_child(self):
        """LessonNode rejects UnitNode as child."""
        lesson = LessonNode(source_id="lesson-1", title="Addition Lesson")
        unit = UnitNode(source_id="unit-1", title="Unit 1")
        with pytest.raises(InvalidNodeException):
            lesson.add_child(unit)

    def test_rejects_course_node_as_child(self):
        """LessonNode rejects CourseNode as child."""
        lesson = LessonNode(source_id="lesson-1", title="Addition Lesson")
        course = CourseNode(source_id="course-1", title="Course 1")
        with pytest.raises(InvalidNodeException):
            lesson.add_child(course)

    def test_rejects_lesson_node_as_child(self):
        """LessonNode rejects another LessonNode as child."""
        lesson1 = LessonNode(source_id="lesson-1", title="Lesson 1")
        lesson2 = LessonNode(source_id="lesson-2", title="Lesson 2")
        with pytest.raises(InvalidNodeException):
            lesson1.add_child(lesson2)


class TestUnitNode:
    """Tests for the UnitNode class."""

    def test_creates_with_required_fields(self):
        """UnitNode can be created with source_id and title."""
        unit = UnitNode(source_id="unit-1", title="Math Unit")
        assert unit.title == "Math Unit"
        assert unit.source_id == "unit-1"

    def test_sets_modality_to_unit(self):
        """UnitNode sets modality to UNIT in extra_fields."""
        unit = UnitNode(source_id="unit-1", title="Math Unit")
        assert unit.extra_fields["options"]["modality"] == modalities.UNIT

    def test_kind_is_topic(self):
        """UnitNode has kind TOPIC (it's a subclass of TopicNode)."""
        unit = UnitNode(source_id="unit-1", title="Math Unit")
        assert unit.kind == content_kinds.TOPIC

    def test_has_empty_test_questions(self):
        """UnitNode initializes with empty test_questions list."""
        unit = UnitNode(source_id="unit-1", title="Math Unit")
        assert unit.test_questions == []

    def test_has_empty_lesson_objectives(self):
        """UnitNode initializes with empty lesson_objectives dict."""
        unit = UnitNode(source_id="unit-1", title="Math Unit")
        assert unit.lesson_objectives == {}


class TestUnitNodeAddChild:
    """Tests for UnitNode.add_child with learning_objectives."""

    def test_requires_learning_objectives_parameter(self):
        """UnitNode.add_child requires learning_objectives — unlike other _CurriculumNodes.

        This documents the intentional API difference: UnitNode.add_child has a
        different signature from CourseNode/LessonNode. Code that polymorphically
        calls node.add_child(child) will get TypeError on a UnitNode.
        """
        unit = UnitNode(source_id="unit-1", title="Math Unit")
        lesson = LessonNode(source_id="lesson-1", title="Lesson 1")
        with pytest.raises(TypeError, match="learning_objectives"):
            unit.add_child(lesson)

    def test_accepts_lesson_node_with_learning_objectives(self):
        """UnitNode accepts LessonNode with learning_objectives."""
        unit = UnitNode(source_id="unit-1", title="Math Unit")
        lesson = LessonNode(source_id="lesson-1", title="Lesson 1")
        lo = LearningObjective("Understand addition")
        unit.add_child(lesson, [lo])
        assert lesson in unit.children

    def test_stores_lesson_objectives_by_source_id(self):
        """UnitNode stores learning objectives keyed by source_id, not object identity."""
        unit = UnitNode(source_id="unit-1", title="Math Unit")
        lesson = LessonNode(source_id="lesson-1", title="Lesson 1")
        lo = LearningObjective("Understand addition")
        unit.add_child(lesson, [lo])
        assert unit.lesson_objectives["lesson-1"] == [lo]

    def test_rejects_lesson_without_learning_objectives(self):
        """UnitNode rejects LessonNode without learning_objectives."""
        unit = UnitNode(source_id="unit-1", title="Math Unit")
        lesson = LessonNode(source_id="lesson-1", title="Lesson 1")
        with pytest.raises(InvalidNodeException, match="Must have at least one learning objective"):
            unit.add_child(lesson, [])

    def test_rejects_lesson_with_none_learning_objectives(self):
        """UnitNode rejects LessonNode with None learning_objectives."""
        unit = UnitNode(source_id="unit-1", title="Math Unit")
        lesson = LessonNode(source_id="lesson-1", title="Lesson 1")
        with pytest.raises(InvalidNodeException, match="Must have at least one learning objective"):
            unit.add_child(lesson, None)

    def test_rejects_topic_node_as_child(self):
        """UnitNode rejects TopicNode as child."""
        unit = UnitNode(source_id="unit-1", title="Math Unit")
        topic = TopicNode(source_id="topic-1", title="Topic 1")
        lo = LearningObjective("Understand addition")
        with pytest.raises(InvalidNodeException):
            unit.add_child(topic, [lo])

    def test_rejects_content_node_as_child(self):
        """UnitNode rejects ContentNode as child."""
        unit = UnitNode(source_id="unit-1", title="Math Unit")
        video = VideoNode(
            source_id="video-1",
            title="Video 1",
            license=licenses.PUBLIC_DOMAIN,
        )
        lo = LearningObjective("Understand addition")
        with pytest.raises(InvalidNodeException):
            unit.add_child(video, [lo])

    def test_rejects_non_learning_objective_in_list(self):
        """UnitNode rejects non-LearningObjective items in learning_objectives."""
        unit = UnitNode(source_id="unit-1", title="Math Unit")
        lesson = LessonNode(source_id="lesson-1", title="Lesson 1")
        with pytest.raises(InvalidNodeException):
            unit.add_child(lesson, ["not a LearningObjective"])

    def test_rejects_invalid_learning_objective(self):
        """LearningObjective with empty text cannot be constructed."""
        with pytest.raises(ValueError, match="text must be non-empty"):
            LearningObjective("")

    def test_rejects_duplicate_source_id(self):
        """UnitNode rejects a second LessonNode with the same source_id."""
        unit = UnitNode(source_id="unit-1", title="Math Unit")
        lo = LearningObjective("Understand addition")
        lesson1 = LessonNode(source_id="lesson-1", title="Lesson 1")
        lesson2 = LessonNode(source_id="lesson-1", title="Lesson 1 copy")
        unit.add_child(lesson1, [lo])
        with pytest.raises(InvalidNodeException):
            unit.add_child(lesson2, [lo])


class TestUnitNodeAddQuestion:
    """Tests for UnitNode.add_question method."""

    def test_adds_question_with_variant_a(self):
        """UnitNode accepts question with VARIANT_A."""
        unit = UnitNode(source_id="unit-1", title="Math Unit")
        lo = LearningObjective("Understand addition")
        q = make_question("q1")
        unit.add_question(q, VARIANT_A, [lo])
        assert len(unit.test_questions) == 1
        assert unit.test_questions[0] == (q, VARIANT_A, [lo])

    def test_adds_question_with_variant_b(self):
        """UnitNode accepts question with VARIANT_B."""
        unit = UnitNode(source_id="unit-1", title="Math Unit")
        lo = LearningObjective("Understand addition")
        q = make_question("q1")
        unit.add_question(q, VARIANT_B, [lo])
        assert len(unit.test_questions) == 1
        assert unit.test_questions[0] == (q, VARIANT_B, [lo])

    def test_rejects_invalid_variant(self):
        """UnitNode rejects question with invalid variant."""
        unit = UnitNode(source_id="unit-1", title="Math Unit")
        lo = LearningObjective("Understand addition")
        q = make_question("q1")
        with pytest.raises(InvalidNodeException):
            unit.add_question(q, "C", [lo])

    def test_rejects_question_without_learning_objectives(self):
        """UnitNode rejects question without learning objectives."""
        unit = UnitNode(source_id="unit-1", title="Math Unit")
        q = make_question("q1")
        with pytest.raises(InvalidNodeException, match="Must have at least one learning objective"):
            unit.add_question(q, VARIANT_A, [])

    def test_rejects_non_learning_objective_in_question(self):
        """UnitNode rejects non-LearningObjective items in add_question."""
        unit = UnitNode(source_id="unit-1", title="Math Unit")
        q = make_question("q1")
        with pytest.raises(InvalidNodeException, match="Expected LearningObjective, got str"):
            unit.add_question(q, VARIANT_A, ["not a LearningObjective"])

    def test_rejects_invalid_learning_objective_in_question(self):
        """UnitNode rejects invalid LearningObjective in add_question."""
        with pytest.raises(ValueError, match="text must be non-empty"):
            LearningObjective("")  # Empty text is invalid


class TestUnitNodeValidation:
    """Tests for UnitNode validation rules."""

    def _create_valid_unit(self):
        """Helper to create a valid unit with balanced questions."""
        unit = UnitNode(source_id="unit-1", title="Math Unit")
        lo = LearningObjective("Understand addition")
        lesson = LessonNode(source_id="lesson-1", title="Lesson 1")
        unit.add_child(lesson, [lo])

        # Add 2 questions per variant for the same LO
        unit.add_question(make_question("q1"), VARIANT_A, [lo])
        unit.add_question(make_question("q2"), VARIANT_A, [lo])
        unit.add_question(make_question("q3"), VARIANT_B, [lo])
        unit.add_question(make_question("q4"), VARIANT_B, [lo])
        return unit

    def test_validates_valid_unit(self):
        """Valid unit passes validation."""
        unit = self._create_valid_unit()
        assert unit.validate() is True

    def test_fails_with_less_than_2_variant_a_questions(self):
        """Unit fails validation with less than 2 VARIANT_A questions."""
        unit = UnitNode(source_id="unit-1", title="Math Unit")
        lo = LearningObjective("Understand addition")
        lesson = LessonNode(source_id="lesson-1", title="Lesson 1")
        unit.add_child(lesson, [lo])

        # Only 1 VARIANT_A question
        unit.add_question(make_question("q1"), VARIANT_A, [lo])
        unit.add_question(make_question("q2"), VARIANT_B, [lo])
        unit.add_question(make_question("q3"), VARIANT_B, [lo])

        with pytest.raises(InvalidNodeException, match="Must have at least 2 VARIANT_A questions"):
            unit.validate()

    def test_fails_with_less_than_2_variant_b_questions(self):
        """Unit fails validation with less than 2 VARIANT_B questions."""
        unit = UnitNode(source_id="unit-1", title="Math Unit")
        lo = LearningObjective("Understand addition")
        lesson = LessonNode(source_id="lesson-1", title="Lesson 1")
        unit.add_child(lesson, [lo])

        # Only 1 VARIANT_B question
        unit.add_question(make_question("q1"), VARIANT_A, [lo])
        unit.add_question(make_question("q2"), VARIANT_A, [lo])
        unit.add_question(make_question("q3"), VARIANT_B, [lo])

        with pytest.raises(InvalidNodeException, match="Must have at least 2 VARIANT_B questions"):
            unit.validate()

    def test_fails_with_unequal_variant_counts(self):
        """Unit fails validation when variant counts are unequal."""
        unit = UnitNode(source_id="unit-1", title="Math Unit")
        lo = LearningObjective("Understand addition")
        lesson = LessonNode(source_id="lesson-1", title="Lesson 1")
        unit.add_child(lesson, [lo])

        # 3 VARIANT_A, 2 VARIANT_B
        unit.add_question(make_question("q1"), VARIANT_A, [lo])
        unit.add_question(make_question("q2"), VARIANT_A, [lo])
        unit.add_question(make_question("q3"), VARIANT_A, [lo])
        unit.add_question(make_question("q4"), VARIANT_B, [lo])
        unit.add_question(make_question("q5"), VARIANT_B, [lo])

        with pytest.raises(
            InvalidNodeException,
            match="VARIANT_A and VARIANT_B must have equal question counts",
        ):
            unit.validate()

    def test_fails_when_lesson_los_dont_match_question_los(self):
        """Unit fails when lesson LOs don't match question LOs."""
        unit = UnitNode(source_id="unit-1", title="Math Unit")
        lo1 = LearningObjective("Understand addition")
        lo2 = LearningObjective("Understand subtraction")
        lesson = LessonNode(source_id="lesson-1", title="Lesson 1")

        # Lesson has lo1, but questions have lo2
        unit.add_child(lesson, [lo1])
        unit.add_question(make_question("q1"), VARIANT_A, [lo2])
        unit.add_question(make_question("q2"), VARIANT_A, [lo2])
        unit.add_question(make_question("q3"), VARIANT_B, [lo2])
        unit.add_question(make_question("q4"), VARIANT_B, [lo2])

        with pytest.raises(
            InvalidNodeException,
            match="Learning objectives on lessons must match those on questions",
        ):
            unit.validate()

    def test_fails_when_lo_not_balanced_across_variants(self):
        """Unit fails when LO has unequal questions in each variant."""
        unit = UnitNode(source_id="unit-1", title="Math Unit")
        lo1 = LearningObjective("Understand addition")
        lo2 = LearningObjective("Understand subtraction")
        lesson1 = LessonNode(source_id="lesson-1", title="Lesson 1")
        lesson2 = LessonNode(source_id="lesson-2", title="Lesson 2")
        unit.add_child(lesson1, [lo1])
        unit.add_child(lesson2, [lo2])

        # lo1: 2 in A, 1 in B (unbalanced)
        # lo2: 0 in A, 1 in B (unbalanced)
        unit.add_question(make_question("q1"), VARIANT_A, [lo1])
        unit.add_question(make_question("q2"), VARIANT_A, [lo1])
        unit.add_question(make_question("q3"), VARIANT_B, [lo1])
        unit.add_question(make_question("q4"), VARIANT_B, [lo2])

        with pytest.raises(
            InvalidNodeException,
            match="Learning objective must have equal questions in each variant",
        ):
            unit.validate()

    def test_fails_when_los_have_unequal_total_questions(self):
        """Unit fails when LOs have different total question counts.

        Even if per-variant balance is correct for each LO, each LO must
        have the same total number of assessment items across both variants.
        """
        unit = UnitNode(source_id="unit-1", title="Math Unit")
        lo1 = LearningObjective("Understand addition")
        lo2 = LearningObjective("Understand subtraction")
        lesson1 = LessonNode(source_id="lesson-1", title="Lesson 1")
        lesson2 = LessonNode(source_id="lesson-2", title="Lesson 2")
        unit.add_child(lesson1, [lo1])
        unit.add_child(lesson2, [lo2])

        # lo1: 2 in A, 2 in B = 4 total (per-variant balanced)
        # lo2: 1 in A, 1 in B = 2 total (per-variant balanced)
        # But lo1 has 4 questions and lo2 has 2 — unequal across LOs
        unit.add_question(make_question("q1"), VARIANT_A, [lo1])
        unit.add_question(make_question("q2"), VARIANT_A, [lo1])
        unit.add_question(make_question("q3"), VARIANT_A, [lo2])
        unit.add_question(make_question("q4"), VARIANT_B, [lo1])
        unit.add_question(make_question("q5"), VARIANT_B, [lo1])
        unit.add_question(make_question("q6"), VARIANT_B, [lo2])

        with pytest.raises(
            InvalidNodeException,
            match="Each learning objective must have the same total number of questions",
        ):
            unit.validate()


class TestUnitNodeSerialization:
    """Tests for UnitNode serialization methods."""

    def _create_valid_unit_with_parent_chain(self):
        """Helper to create a valid unit with proper parent chain for node ID generation."""
        # Create parent chain: Channel -> Course -> Unit -> Lesson
        channel = ChannelNode(
            source_id="test-channel",
            source_domain="test.com",
            title="Test Channel",
            language="en",
        )
        course = CourseNode(source_id="course-1", title="Math Course")
        unit = UnitNode(source_id="unit-1", title="Math Unit")
        lesson = LessonNode(source_id="lesson-1", title="Lesson 1")

        lo = LearningObjective("Understand addition")

        # Build hierarchy
        channel.add_child(course)
        course.add_child(unit)
        unit.add_child(lesson, [lo])

        unit.add_question(make_question("q1"), VARIANT_A, [lo])
        unit.add_question(make_question("q2"), VARIANT_A, [lo])
        unit.add_question(make_question("q3"), VARIANT_B, [lo])
        unit.add_question(make_question("q4"), VARIANT_B, [lo])
        return unit, lo, lesson

    def _create_valid_unit(self):
        """Helper to create a valid unit without parent chain (for tests that don't need it)."""
        unit = UnitNode(source_id="unit-1", title="Math Unit")
        lo = LearningObjective("Understand addition")
        lesson = LessonNode(source_id="lesson-1", title="Lesson 1")
        unit.add_child(lesson, [lo])

        unit.add_question(make_question("q1"), VARIANT_A, [lo])
        unit.add_question(make_question("q2"), VARIANT_A, [lo])
        unit.add_question(make_question("q3"), VARIANT_B, [lo])
        unit.add_question(make_question("q4"), VARIANT_B, [lo])
        return unit, lo, lesson

    def test_get_mastery_criteria_returns_correct_structure(self):
        """_get_mastery_criteria returns correct pre_post_test structure."""
        unit, lo, lesson = self._create_valid_unit()
        result = unit._get_mastery_criteria()

        assert result["mastery_model"] == "pre_post_test"
        assert "pre_post_test" in result
        assert len(result["pre_post_test"]["assessment_item_ids"]) == 4
        assert len(result["pre_post_test"]["version_a_item_ids"]) == 2
        assert len(result["pre_post_test"]["version_b_item_ids"]) == 2

    def test_get_learning_objectives_data_returns_correct_structure(self):
        """_get_learning_objectives_data returns correct structure."""
        unit, lo, lesson = self._create_valid_unit_with_parent_chain()
        result = unit._get_learning_objectives_data()

        assert "learning_objectives" in result
        assert len(result["learning_objectives"]) == 1
        assert result["learning_objectives"][0]["id"] == lo.id
        assert result["learning_objectives"][0]["text"] == lo.text

        assert "assessment_objectives" in result
        assert len(result["assessment_objectives"]) == 4

        assert "lesson_objectives" in result
        assert len(result["lesson_objectives"]) == 1

    def test_to_dict_extra_fields_contains_mastery_model_in_options(self):
        """to_dict output includes mastery model data in extra_fields['options']['completion_criteria']."""
        unit, lo, lesson = self._create_valid_unit_with_parent_chain()

        result = unit.to_dict()
        extra_fields = json.loads(result["extra_fields"])
        options = extra_fields.get("options", {})
        completion_criteria = options.get("completion_criteria", {})

        assert completion_criteria.get("model") == "mastery"
        threshold = completion_criteria.get("threshold", {})
        assert threshold.get("mastery_model") == "pre_post_test"
        assert "pre_post_test" in threshold
        assert len(threshold["pre_post_test"]["assessment_item_ids"]) == 4
        assert len(threshold["pre_post_test"]["version_a_item_ids"]) == 2
        assert len(threshold["pre_post_test"]["version_b_item_ids"]) == 2

    def test_to_dict_extra_fields_contains_learning_objectives_in_options(self):
        """to_dict output includes learning objectives data in extra_fields['options']."""
        unit, lo, lesson = self._create_valid_unit_with_parent_chain()

        result = unit.to_dict()
        extra_fields = json.loads(result["extra_fields"])
        options = extra_fields.get("options", {})

        assert "learning_objectives" in options
        assert len(options["learning_objectives"]) == 1
        assert options["learning_objectives"][0]["id"] == lo.id

        assert "assessment_objectives" in options
        assert len(options["assessment_objectives"]) == 4

        assert "lesson_objectives" in options
        assert len(options["lesson_objectives"]) == 1

    def test_get_learning_objectives_data_validates_against_le_utils_schema(self):
        """_get_learning_objectives_data output must conform to le_utils schema."""
        from le_utils.constants.learning_objectives import SCHEMA

        unit, lo, lesson = self._create_valid_unit_with_parent_chain()
        result = unit._get_learning_objectives_data()

        # Validate learning_objectives IDs match hex-uuid pattern
        hex_uuid_pattern = SCHEMA["definitions"]["hex-uuid"]["pattern"]
        for obj in result["learning_objectives"]:
            assert re.match(hex_uuid_pattern, obj["id"]), f"Learning objective ID '{obj['id']}' doesn't match schema pattern {hex_uuid_pattern}"

        # Validate assessment_objectives keys match hex-uuid pattern
        for assessment_id in result["assessment_objectives"].keys():
            assert re.match(hex_uuid_pattern, assessment_id), f"Assessment ID '{assessment_id}' doesn't match schema pattern {hex_uuid_pattern}"

        # Validate lesson_objectives keys match hex-uuid pattern
        for lesson_id in result["lesson_objectives"].keys():
            assert re.match(hex_uuid_pattern, lesson_id), f"Lesson ID '{lesson_id}' doesn't match schema pattern {hex_uuid_pattern}"
