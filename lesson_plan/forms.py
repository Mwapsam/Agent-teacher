from django import forms
from .models import LessonPlan


class LessonPlanForm(forms.ModelForm):
    class Meta:
        model = LessonPlan
        fields = [
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
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "objectives": forms.Textarea(attrs={"rows": 4}),
            "teaching_materials": forms.Textarea(attrs={"rows": 4}),
            "reference_materials": forms.Textarea(attrs={"rows": 4}),
            "introduction": forms.Textarea(attrs={"rows": 4}),
            "lesson_development": forms.Textarea(attrs={"rows": 8}),
            "conclusion": forms.Textarea(attrs={"rows": 4}),
            "recapitulation": forms.Textarea(attrs={"rows": 4}),
            "evaluation": forms.Textarea(attrs={"rows": 4}),
            "teacher_evaluation": forms.Textarea(attrs={"rows": 4}),
            "homework": forms.Textarea(attrs={"rows": 4}),
        }
