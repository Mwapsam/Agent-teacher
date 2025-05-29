from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponse
from django.core.exceptions import ValidationError
import markdown

from ai.utils import (
    build_prompt,
    generate_lesson_plan,
    normalize_ai_response,
    sanitize_text,
)
from .forms import LessonPlanForm
from .models import LessonPlan
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import io
import logging

logger = logging.getLogger(__name__)

def create_lesson_plan(request):
    if request.method == "POST":
        form = LessonPlanForm(request.POST)
        if form.is_valid():
            lesson_plan = form.save()
            return generate_pdf(request, lesson_plan.id)
    else:
        form = LessonPlanForm()
    return render(request, "lesson_plan/form.html", {"form": form})


def generate_pdf(request, lesson_plan_id):
    lesson_plan = LessonPlan.objects.get(id=lesson_plan_id)

    # Create a PDF response
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    # Custom styles
    title_style = ParagraphStyle(name="Title", fontSize=14, alignment=1, spaceAfter=12)
    heading_style = ParagraphStyle(name="Heading", fontSize=12, spaceAfter=10)
    body_style = ParagraphStyle(name="Body", fontSize=10, spaceAfter=8)

    # Add title
    elements.append(
        Paragraph("MINISTRY OF GENERAL EDUCATION BOARD<br/>LESSON PLAN", title_style)
    )
    elements.append(Spacer(1, 12))

    # Add basic details
    data = [
        [
            "NAME:",
            lesson_plan.teacher_name,
            "DATE:",
            lesson_plan.date.strftime("%d %B, %Y"),
        ],
        ["SCHOOL:", lesson_plan.school, "TIME:", lesson_plan.time],
        ["GRADE:", lesson_plan.grade, "DURATION:", lesson_plan.duration],
        ["SUBJECT:", lesson_plan.subject, "NO OF PUPILS:", str(lesson_plan.num_pupils)],
        ["TOPIC:", lesson_plan.topic, "GENDER:", lesson_plan.gender],
        ["SUB-TOPIC:", lesson_plan.sub_topic, "", ""],
    ]
    table = Table(data, colWidths=[100, 200, 100, 200])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("FONT", (0, 0), (-1, -1), "Helvetica", 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elements.append(table)
    elements.append(Spacer(1, 12))

    # Add objectives
    elements.append(Paragraph("OBJECTIVES", heading_style))
    elements.append(
        Paragraph(lesson_plan.objectives.replace("\n", "<br/>"), body_style)
    )
    elements.append(Spacer(1, 12))

    # Add teaching and reference materials
    elements.append(Paragraph("TEACHING MATERIAL", heading_style))
    elements.append(
        Paragraph(lesson_plan.teaching_materials.replace("\n", "<br/>"), body_style)
    )
    elements.append(Paragraph("REFERENCE MATERIALS", heading_style))
    elements.append(
        Paragraph(lesson_plan.reference_materials.replace("\n", "<br/>"), body_style)
    )
    elements.append(Spacer(1, 12))

    # Add introduction
    elements.append(Paragraph("INTRODUCTION", heading_style))
    elements.append(
        Paragraph(lesson_plan.introduction.replace("\n", "<br/>"), body_style)
    )
    elements.append(Spacer(1, 12))

    # Add lesson development
    elements.append(Paragraph("LESSON DEVELOPMENT", heading_style))
    elements.append(
        Paragraph(lesson_plan.lesson_development.replace("\n", "<br/>"), body_style)
    )
    elements.append(Spacer(1, 12))

    # Add conclusion, recapitulation, evaluation, and teacher evaluation
    elements.append(Paragraph("CONCLUSION", heading_style))
    elements.append(
        Paragraph(lesson_plan.conclusion.replace("\n", "<br/>"), body_style)
    )
    elements.append(Paragraph("RECAPITULATION", heading_style))
    elements.append(
        Paragraph(lesson_plan.recapitulation.replace("\n", "<br/>"), body_style)
    )
    elements.append(Paragraph("EVALUATION", heading_style))
    elements.append(
        Paragraph(lesson_plan.evaluation.replace("\n", "<br/>"), body_style)
    )
    elements.append(Paragraph("TEACHER EVALUATION", heading_style))
    elements.append(
        Paragraph(lesson_plan.teacher_evaluation.replace("\n", "<br/>"), body_style)
    )
    elements.append(Spacer(1, 12))

    # Add homework
    elements.append(Paragraph("HOMEWORK", heading_style))
    elements.append(Paragraph(lesson_plan.homework.replace("\n", "<br/>"), body_style))

    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="lesson_plan_{lesson_plan.id}.pdf"'
    )
    response.write(buffer.getvalue())
    buffer.close()
    return response


REQUIRED_FORM_FIELDS = [
    "teacher_name",
    "date",
    "school",
    "time",
    "grade",
    "duration",
    "subject",
    "num_pupils",
    "topic",
    "sub_topic",
    "gender",
]


def generate_and_save_lesson_plan(request):
    if request.method == "POST":
        try:
            data = request.POST.dict()
            missing_fields = [
                field for field in REQUIRED_FORM_FIELDS if not data.get(field)
            ]

            if missing_fields:
                raise ValidationError(
                    f"Missing required fields: {', '.join(missing_fields)}"
                )

            try:
                data["num_pupils"] = int(data["num_pupils"])
                if data["num_pupils"] <= 0:
                    raise ValidationError("Number of pupils must be positive")
            except (ValueError, TypeError):
                raise ValidationError("Invalid number of pupils")

            # Generate lesson plan
            logger.info(
                f"Generating lesson plan for {data['teacher_name']} - {data['subject']}"
            )
            prompt = build_prompt(data)
            ai_response_raw = generate_lesson_plan(prompt)
            ai_response = normalize_ai_response(ai_response_raw)

            # Sanitize all text inputs
            sanitized_data = {
                key: sanitize_text(value)
                for key, value in {**data, **ai_response}.items()
            }

            # Create and save lesson plan
            lesson = LessonPlan.objects.create(
                teacher_name=sanitized_data["teacher_name"],
                date=sanitized_data["date"],
                school=sanitized_data["school"],
                time=sanitized_data["time"],
                grade=sanitized_data["grade"],
                duration=sanitized_data["duration"],
                subject=sanitized_data["subject"],
                num_pupils=sanitized_data["num_pupils"],
                topic=sanitized_data["topic"],
                sub_topic=sanitized_data["sub_topic"],
                gender=sanitized_data["gender"],
                objectives=sanitized_data["objectives"],
                teaching_materials=sanitized_data["teaching_materials"],
                reference_materials=sanitized_data["reference_materials"],
                introduction=sanitized_data["introduction"],
                lesson_development=sanitized_data["lesson_development"],
                conclusion=sanitized_data["conclusion"],
                recapitulation=sanitized_data["recapitulation"],
                evaluation=sanitized_data["evaluation"],
                teacher_evaluation=sanitized_data["teacher_evaluation"],
                homework=sanitized_data["homework"],
            )

            logger.info(f"Successfully created lesson plan ID {lesson.id}")

            sections = [
                "objectives",
                "teaching_materials",
                "reference_materials",
                "introduction",
                "lesson_development",
                "conclusion",
                "recapitulation",
                "evaluation",
                "teacher_evaluation",
                "homework",
            ]

            return render(
                request,
                "lesson_plan/plan_created.html",
                {"lesson": lesson, "sections": sections, "success": True},
            )

        except ValidationError as e:
            logger.warning(f"Validation error: {str(e)}")
            messages.error(request, f"Validation error: {str(e)}")
            return render(
                request,
                "lesson_plan/form.html",
                {"form_data": request.POST, "error": str(e)},
            )

        except Exception as e:
            logger.error(f"Error generating lesson plan: {str(e)}", exc_info=True)
            messages.error(
                request,
                "An error occurred while generating the lesson plan. Please try again.",
            )
            return render(
                request,
                "lesson_plan/form.html",
                {"form_data": request.POST, "error": "An unexpected error occurred"},
            )

    # GET request - show empty form
    return render(request, "lesson_plan/form.html")
