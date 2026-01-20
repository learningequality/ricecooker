#!/usr/bin/env python
"""
Example sushichef demonstrating curriculum structure nodes (CourseNode, UnitNode, LessonNode).

This script loads course content from content.json and creates a channel with:
- Two courses: Hummingbird Biology and Introductory Computing
- Each course has 3 units with 3 lessons per unit
- Each lesson has a KPUB document and an exercise
- Each unit has pre/post test questions with learning objectives

Run with:
    python sushichef.py --token=YOUR_TOKEN_HERE
"""
import json
import os
import tempfile
import zipfile

from ricecooker.chefs import SushiChef
from ricecooker.classes.curriculum import LearningObjective
from ricecooker.classes.licenses import get_license
from ricecooker.classes.nodes import CourseNode
from ricecooker.classes.nodes import DocumentNode
from ricecooker.classes.nodes import ExerciseNode
from ricecooker.classes.nodes import LessonNode
from ricecooker.classes.nodes import UnitNode
from ricecooker.classes.questions import MultipleSelectQuestion
from ricecooker.classes.questions import SingleSelectQuestion
from ricecooker.classes.questions import VARIANT_A
from ricecooker.classes.questions import VARIANT_B


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONTENT_FILE = os.path.join(SCRIPT_DIR, "content.json")


def load_content():
    """Load course content from JSON file."""
    with open(CONTENT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def create_kpub(html_content, output_path):
    """
    Create a KPUB file (zip archive with index.html).

    Args:
        html_content: HTML string for the lesson content
        output_path: Path where the .kpub file will be created
    """
    full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Lesson</title>
</head>
<body>
{html_content}
</body>
</html>"""

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("index.html", full_html.encode("utf-8"))


def create_question(question_data):
    """
    Create a question object from JSON data.

    Args:
        question_data: Dict with type, id, question, answers, etc.

    Returns:
        SingleSelectQuestion or MultipleSelectQuestion instance
    """
    if question_data["type"] == "single_select":
        return SingleSelectQuestion(
            id=question_data["id"],
            question=question_data["question"],
            correct_answer=question_data["correct_answer"],
            all_answers=question_data["all_answers"],
        )
    elif question_data["type"] == "multiple_select":
        return MultipleSelectQuestion(
            id=question_data["id"],
            question=question_data["question"],
            correct_answers=question_data["correct_answers"],
            all_answers=question_data["all_answers"],
        )
    else:
        raise ValueError(f"Unknown question type: {question_data['type']}")


class CurriculumCoursesChef(SushiChef):
    """
    Sushichef demonstrating curriculum structure with CourseNode, UnitNode, LessonNode.
    """

    channel_info = {
        "CHANNEL_TITLE": "Curriculum Courses Example",
        "CHANNEL_SOURCE_DOMAIN": "learningequality.org",
        "CHANNEL_SOURCE_ID": "curriculum-courses-example",
        "CHANNEL_LANGUAGE": "en",
        "CHANNEL_DESCRIPTION": "Example channel demonstrating curriculum structure nodes",
    }

    def construct_channel(self, **kwargs):
        """Build channel structure from content.json."""
        channel = self.get_channel(**kwargs)
        content = load_content()

        # Create a temp directory for KPUB files
        self.temp_dir = tempfile.mkdtemp(prefix="curriculum_kpub_")

        license = get_license("CC BY", copyright_holder="Learning Equality")

        for course_data in content["courses"]:
            course_node = self._build_course(course_data, license)
            channel.add_child(course_node)

        return channel

    def _build_course(self, course_data, license):
        """Build a CourseNode from JSON data."""
        course = CourseNode(
            source_id=course_data["source_id"],
            title=course_data["title"],
            description=course_data.get("description", ""),
        )

        for unit_data in course_data["units"]:
            unit = self._build_unit(unit_data, license)
            course.add_child(unit)

        return course

    def _build_unit(self, unit_data, license):
        """Build a UnitNode with lessons and pre/post questions."""
        unit = UnitNode(
            source_id=unit_data["source_id"],
            title=unit_data["title"],
            description=unit_data.get("description", ""),
        )

        # Create LearningObjective objects from the text strings
        learning_objectives = [
            LearningObjective(text) for text in unit_data["learning_objectives"]
        ]

        # Add lessons with their associated learning objectives
        for lesson_data in unit_data["lessons"]:
            lesson = self._build_lesson(lesson_data, license)
            # Get the LearningObjective objects for this lesson
            lesson_los = [
                learning_objectives[i]
                for i in lesson_data["learning_objective_indices"]
            ]
            unit.add_child(lesson, lesson_los)

        # Add pre/post test questions
        for q_data in unit_data["prepost_questions"]:
            question = create_question(q_data)
            variant = VARIANT_A if q_data["variant"] == "A" else VARIANT_B
            # Get the LearningObjective for this question
            question_los = [learning_objectives[q_data["lo_index"]]]
            unit.add_question(question, variant, question_los)

        return unit

    def _build_lesson(self, lesson_data, license):
        """Build a LessonNode with content document and exercise."""
        lesson = LessonNode(
            source_id=lesson_data["source_id"],
            title=lesson_data["title"],
        )

        # Create KPUB file for the lesson content
        kpub_path = os.path.join(self.temp_dir, f"{lesson_data['source_id']}.kpub")
        create_kpub(lesson_data["content"], kpub_path)

        # Add document node with KPUB content
        doc_node = DocumentNode(
            source_id=f"{lesson_data['source_id']}-doc",
            title=f"{lesson_data['title']} - Reading",
            license=license,
            language="en",
            uri=kpub_path,
        )
        lesson.add_child(doc_node)

        # Add exercise node with practice questions
        questions = [create_question(q) for q in lesson_data["exercise_questions"]]
        exercise = ExerciseNode(
            source_id=f"{lesson_data['source_id']}-exercise",
            title=f"{lesson_data['title']} - Practice",
            license=license,
            language="en",
            questions=questions,
            exercise_data={
                "mastery_model": "m_of_n",
                "m": min(3, len(questions)),
                "n": len(questions),
                "randomize": True,
            },
        )
        lesson.add_child(exercise)

        return lesson


if __name__ == "__main__":
    chef = CurriculumCoursesChef()
    chef.main()
